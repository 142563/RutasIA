"""Casos de uso de las pantallas del despachador: detalle de ruta, Inicio, Monitoreo y Reportes.

Todo es de solo lectura. Definiciones (docs/PLAN.md §7):
- Retraso de una parada: está pendiente y su ETA ya pasó, o se entregó después de
  ETA + LATE_TOLERANCE_MIN (15 min de tolerancia).
- Puntualidad: entregas con delivered_at <= ETA + tolerancia, sobre las entregas hechas.
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from logistics.application.orders import app_orders
from logistics.application.planning import route_payload
from logistics.domain.exceptions import PlanningError
from logistics.models import Incident, Order, RerouteProposal, Route, RouteStop

LATE_TOLERANCE_MIN = 15
ACTIVE_STATUSES = (Route.Status.PLANNED, Route.Status.IN_PROGRESS)
NO_REASON = "Sin motivo"


class RouteNotFound(PlanningError):
    """La vista la traduce a 404."""


def _iso(moment: datetime | None) -> str | None:
    return timezone.localtime(moment).isoformat() if moment else None


def _minutes_between(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / 60, 1)


def _today_range() -> tuple[datetime, datetime]:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def stop_timing(stop: RouteStop, now: datetime) -> str:
    """on_time | late | overdue (pendiente con ETA pasada) | pending | failed."""
    tolerance = timedelta(minutes=LATE_TOLERANCE_MIN)
    if stop.status == RouteStop.Status.FAILED:
        return "failed"
    if stop.status == RouteStop.Status.DELIVERED:
        if stop.delivered_at is None or stop.delivered_at <= stop.eta + tolerance:
            return "on_time"
        return "late"
    return "overdue" if stop.eta < now else "pending"


def _progress(stops: list[RouteStop]) -> dict:
    delivered = sum(1 for s in stops if s.status == RouteStop.Status.DELIVERED)
    failed = sum(1 for s in stops if s.status == RouteStop.Status.FAILED)
    return {"delivered": delivered, "failed": failed, "total": len(stops)}


def _proposal_payload(proposal: RerouteProposal) -> dict:
    return {
        "id": proposal.id,
        "route_id": proposal.route_id,
        "route_code": proposal.route.code,
        "incident_id": proposal.incident_id,
        "summary": proposal.summary,
        "current_minutes": round(proposal.current_minutes, 1),
        "proposed_minutes": round(proposal.proposed_minutes, 1),
        "minutes_saved": round(proposal.minutes_saved, 1),
        "status": proposal.status,
        "status_label": proposal.get_status_display(),
        "created_at": _iso(proposal.created_at),
        "decided_at": _iso(proposal.decided_at),
    }


# --- detalle de ruta -----------------------------------------------------------

def route_detail(route_id: int) -> dict:
    try:
        route = Route.objects.select_related("depot", "driver", "vehicle").get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound("La ruta no existe.") from None
    now = timezone.now()
    payload = route_payload(route)
    stops = {s.id: s for s in route.stops.all()}
    for item in payload["stops"]:
        stop = stops[item["id"]]
        item["timing"] = stop_timing(stop, now)
        item["diff_minutes"] = _minutes_between(stop.delivered_at, stop.eta) if stop.delivered_at else None
    payload["progress"] = _progress(list(stops.values()))
    return {
        "route": payload,
        "legs": route.legs,
        "reroutes": [_proposal_payload(p) for p in route.reroutes.select_related("route")],
        "late_tolerance_min": LATE_TOLERANCE_MIN,
    }


# --- Inicio --------------------------------------------------------------------

def _count_delayed_stops(now: datetime) -> int:
    """Pendientes con ETA pasada (rutas vigentes) + entregadas hoy fuera de la tolerancia."""
    tolerance = timedelta(minutes=LATE_TOLERANCE_MIN)
    start, end = _today_range()
    overdue = RouteStop.objects.filter(
        status=RouteStop.Status.PENDING, eta__lt=now, route__status__in=ACTIVE_STATUSES).count()
    # La comparación delivered_at > eta + tolerancia se hace en Python (portable entre SQLite y PostgreSQL)
    delivered_today = RouteStop.objects.filter(
        status=RouteStop.Status.DELIVERED, delivered_at__gte=start, delivered_at__lt=end).only("eta", "delivered_at")
    late = sum(1 for s in delivered_today if s.delivered_at > s.eta + tolerance)
    return overdue + late


def dashboard() -> dict:
    now = timezone.now()
    start, end = _today_range()
    return {
        "routes_in_progress": Route.objects.filter(status=Route.Status.IN_PROGRESS).count(),
        "routes_planned_today": Route.objects.filter(
            status=Route.Status.PLANNED, departure_at__gte=start, departure_at__lt=end).count(),
        "delayed_stops": _count_delayed_stops(now),
        "unassigned_orders": app_orders().filter(status=Order.Status.PENDING).count(),
        "deliveries_today": RouteStop.objects.filter(
            status=RouteStop.Status.DELIVERED, delivered_at__gte=start, delivered_at__lt=end).count(),
        "late_tolerance_min": LATE_TOLERANCE_MIN,
    }


# --- Monitoreo -----------------------------------------------------------------

def _monitor_route(route: Route, now: datetime) -> dict:
    stops = list(route.stops.select_related("order"))
    pending = [s for s in stops if s.status == RouteStop.Status.PENDING]
    done = [s for s in stops if s.delivered_at]
    nxt = pending[0] if pending else None
    # Retraso estimado: lo que ya se pasó de la ETA de la próxima parada o, si aún no se pasa,
    # el retraso con el que se hizo la última entrega (se asume que se arrastra).
    delay = 0.0
    if nxt and nxt.eta < now:
        delay = _minutes_between(now, nxt.eta)
    if done:
        last = max(done, key=lambda s: s.delivered_at)
        delay = max(delay, _minutes_between(last.delivered_at, last.eta))
    return {
        "id": route.id,
        "code": route.code,
        "status": route.status,
        "status_label": route.get_status_display(),
        "driver": route.driver.name if route.driver else None,
        "vehicle": route.vehicle.plate if route.vehicle else None,
        "departure_at": _iso(route.departure_at),
        "finish_at": _iso(route.finish_at),
        "started_at": _iso(route.started_at),
        "progress": _progress(stops),
        "next_stop": {
            "sequence": nxt.sequence, "order_code": nxt.order.code, "recipient": nxt.order.recipient,
            "address": nxt.order.address, "eta": _iso(nxt.eta),
        } if nxt else None,
        "delay_minutes": max(0.0, round(delay, 1)),
        "pending_reroutes": route.reroutes.filter(status=RerouteProposal.Status.PENDING).count(),
    }


def _incident_payload(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "kind": incident.kind,
        "kind_label": incident.get_kind_display(),
        "blocked": incident.blocked,
        "multiplier": incident.multiplier,
        "starts_at": _iso(incident.starts_at),
        "ends_at": _iso(incident.ends_at),
        "note": incident.note,
        "route_code": incident.route.code if incident.route else None,
        "edges": [f"{e.origin.name} → {e.destination.name}" for e in incident.edges.all()],
    }


def monitoring() -> dict:
    now = timezone.now()
    start, end = _today_range()
    routes = (
        Route.objects.select_related("driver", "vehicle")
        .filter(Q(status=Route.Status.IN_PROGRESS)
                | Q(status=Route.Status.PLANNED, departure_at__gte=start, departure_at__lt=end))
        .order_by("status", "departure_at")  # "in_progress" antes que "planned"
    )
    incidents = (
        Incident.objects.select_related("route").prefetch_related("edges__origin", "edges__destination")
        .filter(resolved_at__isnull=True).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    )
    proposals = RerouteProposal.objects.select_related("route").filter(status=RerouteProposal.Status.PENDING)
    return {
        "routes": [_monitor_route(r, now) for r in routes],
        "incidents": [_incident_payload(i) for i in incidents],
        "proposals": [_proposal_payload(p) for p in proposals],
        "refreshed_at": _iso(now),
    }


# --- Reportes ------------------------------------------------------------------

EXPERIMENT_FILES = {
    "e1": ("e1_correctitud.csv", "E1 · Correctitud (A* = Dijkstra)"),
    "e2": ("e2_eficiencia.csv", "E2 · Eficiencia (nodos expandidos y ms)"),
    "e3": ("e3_impacto_trafico.csv", "E3 · Impacto del tráfico"),
    "e5": ("e5_varias_paradas.csv", "E5 · Varias paradas (2-opt)"),
    "e7": ("e7_escalabilidad.csv", "E7 · Escalabilidad"),
}


def experiments_dir() -> Path:
    """Donde run_experiments deja los CSV por defecto."""
    return Path(settings.BASE_DIR) / "experiments" / "output"


def _mean(rows: list[dict], key: str) -> float:
    return statistics.mean(float(r[key]) for r in rows)


def _truthy(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _summarize(key: str, rows: list[dict]) -> dict:
    """Resumen de un experimento a partir de sus filas. Solo promedia lo que está en el CSV."""
    if key == "e1":
        pairs, equal = sum(int(r["pairs"]) for r in rows), sum(int(r["equal"]) for r in rows)
        return {"queries": pairs, "equal": equal, "pct_equal": round(100 * equal / pairs, 2) if pairs else None}
    if key == "e2":
        d, a = _mean(rows, "dijkstra_expanded"), _mean(rows, "astar_expanded")
        return {"queries": len(rows), "dijkstra_expanded": round(d, 1), "astar_expanded": round(a, 1),
                "reduction_pct": round(100 * (1 - a / d), 1) if d else None,
                "dijkstra_ms": round(_mean(rows, "dijkstra_ms"), 4), "astar_ms": round(_mean(rows, "astar_ms"), 4),
                "same_cost_pct": round(100 * sum(_truthy(r["same_cost"]) for r in rows) / len(rows), 2)}
    if key == "e3":
        return {"cases": len(rows), "route_changes": sum(_truthy(r["route_changes"]) for r in rows),
                "mean_minutes_saved": round(_mean(rows, "minutes_saved"), 2),
                "max_minutes_saved": round(max(float(r["minutes_saved"]) for r in rows), 2)}
    if key == "e5":
        by_stops: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            by_stops[int(r["stops"])].append(r)
        return {"instances": len(rows), "by_stops": [
            {"stops": k, "two_opt_vs_capture_pct": round(_mean(v, "two_opt_vs_capture_pct"), 1),
             "two_opt_vs_nn_pct": round(_mean(v, "two_opt_vs_nn_pct"), 1)} for k, v in sorted(by_stops.items())]}
    by_nodes: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_nodes[(int(r["nodes"]), r["graph"])].append(r)
    return {"queries": len(rows), "by_size": [
        {"nodes": n, "graph": g, "dijkstra_expanded": round(_mean(v, "dijkstra_expanded"), 1),
         "astar_expanded": round(_mean(v, "astar_expanded"), 1),
         "dijkstra_ms": round(_mean(v, "dijkstra_ms"), 3), "astar_ms": round(_mean(v, "astar_ms"), 3)}
        for (n, g), v in sorted(by_nodes.items())]}


def _is_real(sources: list[str]) -> bool:
    return bool(sources) and not any(t in s for s in sources for t in ("estimate", "synthetic", "none"))


def experiment_results(directory: Path | None = None) -> list[dict]:
    """Lee los CSV que dejó run_experiments. Si un archivo no existe o está dañado, se omite."""
    directory = directory or experiments_dir()
    results = []
    for key, (filename, title) in EXPERIMENT_FILES.items():
        path = directory / filename
        try:
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                continue
            summary = _summarize(key, rows)
            updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())
        except (OSError, KeyError, ValueError, ZeroDivisionError, statistics.StatisticsError):
            continue
        sources = sorted({r.get("data_source", "") for r in rows if r.get("data_source")})
        results.append({
            "key": key, "title": title, "file": filename, "rows": len(rows), "summary": summary,
            "updated_at": updated.isoformat(), "data_sources": sources, "is_real_data": _is_real(sources),
        })
    return results


def reports() -> dict:
    tolerance = timedelta(minutes=LATE_TOLERANCE_MIN)
    routes = Route.objects.exclude(status=Route.Status.CANCELED).filter(shortest_minutes__isnull=False)
    saved_by_route = [(r.code, r.shortest_minutes - r.driving_minutes) for r in routes]
    delivered = list(RouteStop.objects.filter(status=RouteStop.Status.DELIVERED, delivered_at__isnull=False)
                     .only("eta", "delivered_at"))
    on_time = sum(1 for s in delivered if s.delivered_at <= s.eta + tolerance)
    failed = Counter(
        (reason or NO_REASON) for reason in
        RouteStop.objects.filter(status=RouteStop.Status.FAILED).values_list("reason", flat=True))
    return {
        "minutes_saved": {
            "total": round(sum(v for _, v in saved_by_route), 1),
            "routes": len(saved_by_route),
            "by_route": [{"code": c, "minutes_saved": round(v, 1)} for c, v in saved_by_route[:12]],
        },
        "punctuality": {
            "delivered": len(delivered), "on_time": on_time,
            "pct": round(100 * on_time / len(delivered), 1) if delivered else None,
            "tolerance_min": LATE_TOLERANCE_MIN,
        },
        "failed_by_reason": [{"reason": r, "count": n} for r, n in failed.most_common()],
        "experiments": experiment_results(),
    }
