"""Incidentes y recálculo en vivo (docs/PLAN.md §8, flujo C).

1. Un incidente penaliza (multiplicador ≥ 1) o bloquea (costo infinito) aristas.
2. El grafo en memoria NO incluye incidentes: se leen de la BD ANTES de buscar y
   se aplican encima de los pesos cacheados (`weights_with_incidents`). Por eso
   crear o resolver un incidente no invalida el grafo; la búsqueda (Dijkstra/A*)
   sigue sin tocar BD ni Google dentro de su bucle.
3. Al crear un incidente se revisan las rutas planificadas o en curso: si algún
   tramo PENDIENTE pasa por una arista afectada, se recalcula con A* y, si la
   ruta nueva ahorra ≥ 1 min (o la actual quedó bloqueada), se crea una
   RerouteProposal pendiente. El conductor o el despachador la acepta o la rechaza.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from logistics.application.planning import route_payload
from logistics.application.routing import get_graph, parse_departure, roads_along
from logistics.domain.exceptions import PlanningError
from logistics.models import Edge, Incident, RerouteProposal, Route, RouteStop, UserProfile
from logistics.routing.astar import astar, compute_v_max
from logistics.routing.graph import TIME, RoadGraph
from logistics.routing.incidents import BLOCKED, apply_penalties, combine_penalties
from logistics.routing.traffic import profile_for, to_local

MIN_SAVING_MIN = 1.0  # una propuesta exige ahorrar al menos esto (salvo que la ruta actual esté bloqueada)
# Minutos que se registran cuando la ruta actual pasa por un tramo bloqueado (el costo real es infinito,
# pero JSON y las columnas float no lo representan bien). `current_blocked` en la API lo indica.
BLOCKED_MINUTES = 9999.0
MAX_EDGES_PER_INCIDENT = 20
MAX_MULTIPLIER = 50.0
# Multiplicador por omisión según el tipo, cuando el reporte no lo indica y no es un bloqueo.
DEFAULT_MULTIPLIER = {
    Incident.Kind.TRAFFIC: 1.5,
    Incident.Kind.ACCIDENT: 2.0,
    Incident.Kind.LANDSLIDE: 3.0,
    Incident.Kind.CLOSURE: 3.0,
}
# Estos tipos bloquean el tramo salvo que el reporte diga lo contrario.
BLOCKING_KINDS = (Incident.Kind.CLOSURE,)


# --- pesos con incidentes (reutilizable por el motor de consultas) -----------

def active_incidents(now: datetime | None = None):
    """Incidentes vigentes: ya empezaron, no terminaron y no se han resuelto."""
    now = now or timezone.now()
    return Incident.objects.filter(resolved_at__isnull=True, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    )


def incident_penalties(graph: RoadGraph, now: datetime | None = None) -> dict[int, float]:
    """{índice de arista: multiplicador o BLOCKED} de los incidentes vigentes (una consulta a la BD)."""
    position = {db_id: i for i, db_id in enumerate(graph.edge_db_ids) if db_id is not None}
    rows = active_incidents(now).filter(edges__isnull=False).values_list("edges__id", "blocked", "multiplier")
    return combine_penalties(
        (position[edge_id], BLOCKED if blocked else max(multiplier, 1.0))
        for edge_id, blocked, multiplier in rows
        if edge_id in position
    )


def weights_with_incidents(graph: RoadGraph, base_weights, now: datetime | None = None) -> list[float]:
    """Pesos con los incidentes vigentes. NO muta `base_weights` (lista cacheada del grafo).

    Sin incidentes devuelve una copia igual. Úsese junto con
    `astar(..., v_max=compute_v_max(graph, base_weights))`: la heurística se deriva
    de los pesos SIN incidentes para seguir siendo admisible.
    """
    return apply_penalties(base_weights, incident_penalties(graph, now))


# --- serialización -----------------------------------------------------------

def _iso(moment) -> str | None:
    return timezone.localtime(moment).isoformat() if moment else None


def incident_payload(incident: Incident, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    active = (
        incident.resolved_at is None and incident.starts_at <= now
        and (incident.ends_at is None or incident.ends_at > now)
    )
    return {
        "id": incident.id,
        "kind": incident.kind,
        "kind_label": incident.get_kind_display(),
        "blocked": incident.blocked,
        "multiplier": None if incident.blocked else incident.multiplier,
        "starts_at": _iso(incident.starts_at),
        "ends_at": _iso(incident.ends_at),
        "resolved_at": _iso(incident.resolved_at),
        "active": active,
        "note": incident.note,
        "route_id": incident.route_id,
        "reported_by": incident.reported_by.get_username() if incident.reported_by else None,
        "edges": [
            {
                "id": e.id,
                "road": e.road,
                "km": round(e.distance_km, 2),
                "from": {"code": e.origin.code, "name": e.origin.name},
                "to": {"code": e.destination.code, "name": e.destination.name},
            }
            for e in incident.edges.select_related("origin", "destination")
        ],
    }


def proposal_payload(p: RerouteProposal) -> dict:
    return {
        "id": p.id,
        "route_id": p.route_id,
        "route_code": p.route.code,
        "incident_id": p.incident_id,
        "status": p.status,
        "status_label": p.get_status_display(),
        "summary": p.summary,
        "current_minutes": round(p.current_minutes, 2),
        "proposed_minutes": round(p.proposed_minutes, 2),
        "minutes_saved": round(p.minutes_saved, 2),
        "current_blocked": p.current_minutes >= BLOCKED_MINUTES,
        "proposed_legs": p.proposed_legs,
        "created_at": _iso(p.created_at),
        "decided_at": _iso(p.decided_at),
    }


# --- listado -----------------------------------------------------------------

def list_incidents(user, role: str, include_resolved: bool = False) -> dict:
    """Vigentes (y con `all` los últimos resueltos o vencidos), más las propuestas pendientes.

    Despachador/admin ven todas las propuestas; un conductor ve los incidentes
    vigentes (le sirven para saber qué evitar) pero solo las propuestas de sus rutas.
    """
    now = timezone.now()
    if include_resolved:
        incidents = Incident.objects.all()[:50]
    else:
        incidents = active_incidents(now)
    proposals = RerouteProposal.objects.filter(status=RerouteProposal.Status.PENDING).select_related("route")
    if role == UserProfile.Role.DRIVER:
        proposals = proposals.filter(route__driver__user=user)
    return {
        "incidents": [incident_payload(i, now) for i in incidents.select_related("reported_by")],
        "reroutes": [proposal_payload(p) for p in proposals],
    }


# --- crear -------------------------------------------------------------------

def _edge_ids(graph_payload: dict) -> list[Edge]:
    raw = graph_payload.get("edges")
    if raw is None:
        raw = graph_payload.get("edge_ids")
    if not isinstance(raw, list) or not raw:
        raise PlanningError("Indica al menos un tramo: ids de arista o pares {\"from\": código, \"to\": código}.")
    both = bool(graph_payload.get("both_directions"))
    found: dict[int, Edge] = {}
    for spec in raw:
        if isinstance(spec, dict):
            origin, destination = str(spec.get("from") or "").strip(), str(spec.get("to") or "").strip()
            if not origin or not destination:
                raise PlanningError("Cada tramo debe indicar los códigos de nodo \"from\" y \"to\".")
            pairs = [(origin, destination)] + ([(destination, origin)] if both else [])
            hits = [
                Edge.objects.select_related("origin", "destination").filter(
                    origin__code=a, destination__code=b, is_active=True).first()
                for a, b in pairs
            ]
            if not any(hits):
                raise PlanningError(f"No hay un tramo de carretera entre '{origin}' y '{destination}'.")
            edges = [e for e in hits if e]
        else:
            try:
                edge_id = int(spec)
            except (TypeError, ValueError):
                raise PlanningError("Los tramos deben ser ids numéricos o pares {\"from\", \"to\"}.") from None
            edge = Edge.objects.select_related("origin", "destination").filter(pk=edge_id, is_active=True).first()
            if edge is None:
                raise PlanningError(f"No existe el tramo {edge_id}.")
            edges = [edge]
            if both:
                reverse = Edge.objects.select_related("origin", "destination").filter(
                    origin=edge.destination, destination=edge.origin, is_active=True).first()
                edges += [reverse] if reverse else []
        for e in edges:
            found[e.id] = e
    if len(found) > MAX_EDGES_PER_INCIDENT:
        raise PlanningError(f"Un incidente puede afectar máximo {MAX_EDGES_PER_INCIDENT} tramos.")
    return list(found.values())


def _parse_effect(payload: dict, kind: str) -> tuple[bool, float]:
    blocked = payload.get("blocked")
    blocked = kind in BLOCKING_KINDS if blocked is None else bool(blocked)
    if blocked:
        return True, 1.0
    raw = payload.get("multiplier")
    if raw is None:
        return False, DEFAULT_MULTIPLIER[kind]
    try:
        multiplier = float(raw)
    except (TypeError, ValueError):
        raise PlanningError("El multiplicador debe ser un número.") from None
    if math.isnan(multiplier) or multiplier < 1.0:
        raise PlanningError("El multiplicador debe ser ≥ 1: un incidente nunca reduce el tiempo.")
    if multiplier > MAX_MULTIPLIER:
        raise PlanningError(f"El multiplicador no puede pasar de {MAX_MULTIPLIER:g}. Para cerrar el tramo usa blocked.")
    return False, multiplier


def _parse_moment(value, label: str) -> datetime | None:
    if not value:
        return None
    try:
        return parse_departure(value)
    except PlanningError:
        raise PlanningError(f"{label} inválida. Usa el formato 2026-10-06T07:30.") from None


def create_incident(payload: dict, user) -> dict:
    kind = payload.get("kind")
    if kind not in Incident.Kind.values:
        raise PlanningError(f"Tipo de incidente inválido. Opciones: {', '.join(Incident.Kind.values)}.")
    edges = _edge_ids(payload)
    blocked, multiplier = _parse_effect(payload, kind)
    now = timezone.now()
    starts_at = _parse_moment(payload.get("starts_at"), "La hora de inicio") or now
    ends_at = _parse_moment(payload.get("ends_at"), "La hora de fin")
    if ends_at is not None and ends_at <= starts_at:
        raise PlanningError("La hora de fin debe ser posterior a la de inicio.")
    note = str(payload.get("note") or "").strip()
    if len(note) > 255:
        raise PlanningError("La nota admite máximo 255 caracteres.")
    route = None
    if payload.get("route_id"):
        route = Route.objects.filter(pk=payload["route_id"]).first()
        if route is None:
            raise PlanningError("La ruta indicada no existe.")

    with transaction.atomic():
        incident = Incident.objects.create(
            kind=kind, blocked=blocked, multiplier=multiplier, starts_at=starts_at, ends_at=ends_at,
            note=note, reported_by=user if getattr(user, "is_authenticated", False) else None, route=route,
        )
        incident.edges.set(edges)
        result = recompute_routes(incident=incident, now=max(now, starts_at))
    return {"incident": incident_payload(incident), **result}


def resolve_incident(incident_id: int, user, role: str) -> dict:
    incident = Incident.objects.filter(pk=incident_id).first()
    if incident is None:
        raise PlanningError("El incidente no existe.")
    is_dispatch = role in (UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER)
    if not is_dispatch and incident.reported_by_id != user.id:
        raise PlanningError("Solo el despacho o quien reportó el incidente puede resolverlo.")
    if incident.resolved_at is not None:
        raise PlanningError("El incidente ya estaba resuelto.")
    with transaction.atomic():
        incident.resolved_at = timezone.now()
        incident.save(update_fields=["resolved_at", "updated_at"])
        # Sin el incidente las propuestas que nacieron de él ya no tienen sentido.
        RerouteProposal.objects.filter(incident=incident, status=RerouteProposal.Status.PENDING).update(
            status=RerouteProposal.Status.EXPIRED, updated_at=timezone.now())
    return {"incident": incident_payload(incident)}


# --- recálculo ---------------------------------------------------------------

def _edge_lookup(graph: RoadGraph) -> dict[tuple[int, int], int]:
    """(u, v) → índice de la arista. Hay una arista por dirección; si hubiera varias, la más rápida."""
    lookup: dict[tuple[int, int], int] = {}
    for u, neighbours in enumerate(graph.adj):
        for v, e in neighbours:
            best = lookup.get((u, v))
            if best is None or graph.t0[e] < graph.t0[best]:
                lookup[(u, v)] = e
    return lookup


def _path_edges(codes: list[str], graph: RoadGraph, lookup) -> list[int] | None:
    """Aristas de una lista de códigos de nodo; None si algún nodo o tramo ya no existe en el grafo."""
    try:
        nodes = [graph.index[c] for c in codes]
        return [lookup[(a, b)] for a, b in zip(nodes, nodes[1:])]
    except KeyError:
        return None


def _pending_leg_indexes(route: Route, stops: list[RouteStop]) -> list[int]:
    """Tramo i lleva a la parada i (por orden de sequence); el último es el regreso a la bodega.

    Pendientes: los que llevan a paradas pending y el regreso mientras la ruta no termine.
    """
    pending = [i for i, s in enumerate(stops) if s.status == RouteStop.Status.PENDING and i < len(route.legs)]
    if len(route.legs) > len(stops):
        pending.append(len(stops))
    return pending


def recompute_routes(incident: Incident | None = None, now: datetime | None = None) -> dict:
    """Revisa las rutas planificadas o en curso y propone alternativas con A*.

    Solo se recalculan los tramos pendientes; el orden de las paradas no cambia.
    """
    now = now or timezone.now()
    graph = get_graph()
    penalties = incident_penalties(graph, now)
    summary = {"routes_checked": 0, "routes_affected": 0, "proposals": [], "unreachable_routes": []}
    if not penalties:
        return summary

    lookup = _edge_lookup(graph)
    today_start = to_local(now).replace(hour=0, minute=0, second=0, microsecond=0)
    routes = Route.objects.filter(
        status__in=(Route.Status.IN_PROGRESS, Route.Status.PLANNED), departure_at__gte=today_start,
    ).select_related("driver")
    band_cache: dict[tuple[str, str], tuple[list[float], list[float], float]] = {}

    def weights_for(moment: datetime):
        key = profile_for(moment)
        if key not in band_cache:
            base = graph.weights(TIME, *key)
            band_cache[key] = (base, apply_penalties(base, penalties), compute_v_max(graph, base))
        return key, band_cache[key]

    for route in routes:
        summary["routes_checked"] += 1
        stops = list(route.stops.order_by("sequence"))
        legs = route.legs or []
        pending = _pending_leg_indexes(route, stops)
        old_edges = {i: _path_edges(legs[i]["nodes"], graph, lookup) for i in pending}
        if not pending or any(edges is None for edges in old_edges.values()):
            continue  # nada pendiente, o el grafo cambió desde que se planificó
        if not any(e in penalties for i in pending for e in old_edges[i]):
            continue
        summary["routes_affected"] += 1

        clock = now if route.status == Route.Status.IN_PROGRESS else max(now, to_local(route.departure_at))
        current_total = proposed_total = 0.0
        blocked_now, unreachable, new_legs = False, False, []
        for i in pending:
            (band, day_type), (_base, penalized, v_max) = weights_for(clock)
            origin, target = graph.index[legs[i]["nodes"][0]], graph.index[legs[i]["nodes"][-1]]
            cost_now = sum(penalized[e] for e in old_edges[i])
            if cost_now == math.inf:
                blocked_now, cost_now = True, BLOCKED_MINUTES
            current_total += cost_now
            result = astar(graph, penalized, origin, target, v_max=v_max)
            if not result.found:
                unreachable = True
                break
            minutes = result.total(penalized)
            arrive = clock + timedelta(minutes=minutes)
            proposed_total += minutes
            new_legs.append({
                "index": i,
                "nodes": [graph.codes[n] for n in result.path],
                "roads": roads_along(graph, result.edges),
                "minutes": round(minutes, 2),
                "km": round(result.total(graph.km), 2),
                "band": band,
                "depart_at": clock.isoformat(),
                "arrive_at": arrive.isoformat(),
                "expanded": result.expanded,
            })
            clock = arrive + timedelta(minutes=route.service_min if i < len(stops) else 0)
        if unreachable:
            summary["unreachable_routes"].append({"route_id": route.id, "route_code": route.code})
            continue
        saved = current_total - proposed_total
        if not blocked_now and saved < MIN_SAVING_MIN:
            continue  # la ruta actual sigue siendo (casi) tan buena: no molestar al conductor

        with transaction.atomic():
            RerouteProposal.objects.filter(route=route, status=RerouteProposal.Status.PENDING).update(
                status=RerouteProposal.Status.EXPIRED, updated_at=timezone.now())
            proposal = RerouteProposal.objects.create(
                route=route, incident=incident, current_minutes=current_total, proposed_minutes=proposed_total,
                proposed_legs=new_legs, summary=_summary(graph, legs, new_legs, saved, blocked_now),
            )
        summary["proposals"].append(proposal_payload(proposal))
    return summary


def _summary(graph: RoadGraph, old_legs: list[dict], new_legs: list[dict], saved: float, blocked: bool) -> str:
    """"Nueva ruta por Palín: −18 min": un nodo intermedio que la ruta nueva usa y la vieja no."""
    old_nodes = {code for leg in old_legs for code in leg["nodes"]}
    endpoints = {code for leg in new_legs for code in (leg["nodes"][0], leg["nodes"][-1])}
    via = next(
        (graph.names[graph.index[code]] for leg in new_legs for code in leg["nodes"]
         if code not in old_nodes and code not in endpoints and code in graph.index),
        None,
    )
    if via is None:
        old_roads = {r for leg in old_legs for r in leg.get("roads", [])}
        via = next((r for leg in new_legs for r in leg["roads"] if r not in old_roads), None)
    head = f"Nueva ruta por {via}" if via else "Nueva ruta"
    tail = "evita el tramo cerrado" if blocked else f"−{max(round(saved), 1)} min"
    return f"{head}: {tail}"


# --- decisión ----------------------------------------------------------------

def decide_reroute(proposal_id: int, payload: dict, user, role: str) -> dict:
    decision = payload.get("decision")
    if decision not in ("accept", "keep"):
        raise PlanningError("La decisión debe ser 'accept' o 'keep'.")
    with transaction.atomic():
        proposal = RerouteProposal.objects.select_for_update().select_related("route", "route__driver").filter(
            pk=proposal_id).first()
        if proposal is None:
            raise PlanningError("La propuesta no existe.")
        route = proposal.route
        owner = route.driver is not None and route.driver.user_id == user.id
        if not owner and role not in (UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER):
            raise PlanningError("Solo el conductor de la ruta o el despacho puede decidir.")
        if proposal.status != RerouteProposal.Status.PENDING:
            raise PlanningError("Esta propuesta ya fue resuelta o venció.")
        if decision == "accept":
            _apply_proposal(route, proposal)
            proposal.status = RerouteProposal.Status.ACCEPTED
        else:
            proposal.status = RerouteProposal.Status.KEPT
        proposal.decided_by = user
        proposal.decided_at = timezone.now()
        proposal.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    route.refresh_from_db()
    return {"proposal": proposal_payload(proposal), "route": route_payload(route)}


def _apply_proposal(route: Route, proposal: RerouteProposal) -> None:
    """Reemplaza los tramos pendientes y actualiza minutos, km, fin y ETA de las paradas pendientes."""
    if route.status not in (Route.Status.IN_PROGRESS, Route.Status.PLANNED):
        raise PlanningError("La ruta ya no está activa.")
    legs = [dict(leg) for leg in route.legs]
    stops = list(route.stops.order_by("sequence"))
    for new in proposal.proposed_legs:
        index = new["index"]
        if not 0 <= index < len(legs):
            raise PlanningError("La propuesta ya no coincide con la ruta. Pide un recálculo.")
        legs[index] = {k: v for k, v in new.items() if k != "index"}
        if index < len(stops) and stops[index].status == RouteStop.Status.PENDING:
            stops[index].eta = datetime.fromisoformat(new["arrive_at"])
            stops[index].save(update_fields=["eta"])
    route.legs = legs
    route.driving_minutes = sum(leg["minutes"] for leg in legs)
    route.total_km = sum(leg["km"] for leg in legs)
    route.expanded_nodes += sum(new.get("expanded", 0) for new in proposal.proposed_legs)
    if legs:
        route.finish_at = datetime.fromisoformat(legs[-1]["arrive_at"])
    route.save(update_fields=["legs", "driving_minutes", "total_km", "expanded_nodes", "finish_at", "updated_at"])
