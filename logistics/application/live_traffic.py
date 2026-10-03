"""Tráfico del momento: valida una ruta YA calculada contra Google ahora mismo.

Para cada tramo pendiente se hace UNA consulta computeRoutes con el tráfico de
ahora (TRAFFIC_AWARE_OPTIMAL), con origen, destino y, como puntos de paso
(`intermediates`, via: true), los nodos que eligió NUESTRO A*. Así Google mide
exactamente nuestra ruta, no la suya.

No viola las reglas del motor: Google no se llama dentro de Dijkstra ni de A*;
es una validación posterior, solo informativa. No cambia la ruta ni las horas
guardadas. Una consulta por tramo, con tope de tramos por llamada y una caché de
5 minutos por ruta para no gastar cuota.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from logistics.application.incidents import _pending_leg_indexes
from logistics.models import Node, Route
from logistics.routing.google import RoutesApiError, RoutesClient
from logistics.routing.traffic import GT_TZ

MAX_INTERMEDIATES = 25
MAX_LEGS = 12
CACHE_SECONDS = 300
TOLERANCE_MIN = 5.0


class LiveCheckError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def _cache_key(route_id: int) -> str:
    return f"live-check:{route_id}"


def sample_intermediates(codes: list[str], limit: int = MAX_INTERMEDIATES) -> list[str]:
    """Nodos entre origen y destino; si hay más de `limit`, se submuestrean parejo."""
    inner = codes[1:-1]
    if len(inner) <= limit:
        return inner
    step = (len(inner) - 1) / (limit - 1)
    return [inner[round(i * step)] for i in range(limit)]


def _clock(moment: datetime) -> str:
    return moment.astimezone(GT_TZ).strftime("%H:%M")


def _message(diff_min: float, arrival: datetime) -> str:
    if abs(diff_min) <= TOLERANCE_MIN:
        return "Google confirma la hora de llegada (±5 min)."
    minutes = round(abs(diff_min))
    if diff_min > 0:
        return f"Hay más tráfico del previsto: llegaría {minutes} min más tarde ({_clock(arrival)})."
    return f"Hay menos tráfico del previsto: llegaría {minutes} min antes ({_clock(arrival)})."


def live_check(route: Route, client: RoutesClient | None = None, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    key = _cache_key(route.id)
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    if route.status in (Route.Status.COMPLETED, Route.Status.CANCELED):
        raise LiveCheckError("Esta ruta ya terminó; no hay tramos pendientes que verificar.", 400)
    stops = list(route.stops.select_related("order").order_by("sequence"))
    pending = [i for i in _pending_leg_indexes(route, stops) if i < len(route.legs)]
    if not pending:
        raise LiveCheckError("No quedan tramos pendientes en esta ruta.", 400)
    if client is None:
        try:
            client = RoutesClient()
        except RoutesApiError as exc:
            raise LiveCheckError(
                "El tráfico del momento no está disponible: falta configurar la llave de Google.", 400) from exc

    checked = pending[:MAX_LEGS]
    codes = {c for i in checked for c in route.legs[i]["nodes"]}
    nodes = {n.code: n for n in Node.objects.filter(code__in=codes)}

    def point(code: str) -> tuple[float, float]:
        node = nodes.get(code)
        if node is None:
            raise LiveCheckError(f"No se encontró el punto «{code}» de la ruta.", 400)
        return node.latitude, node.longitude

    legs_out, stop_rows, cumulative = [], [], 0.0
    for i in checked:
        leg = route.legs[i]
        path = leg["nodes"]
        try:
            result = client.compute_route(
                point(path[0]), point(path[-1]),
                [point(c) for c in sample_intermediates(path)],
                departure_time=now + timedelta(seconds=15),  # Google no acepta una hora ya pasada
            )
        except RoutesApiError as exc:
            raise LiveCheckError(
                "No se pudo consultar el tráfico a Google. Intenta de nuevo en unos minutos.", 502) from exc
        ours = float(leg["minutes"])
        google = round(result.duration_s / 60, 1)
        cumulative += google - ours
        is_return = i >= len(stops)
        stored = datetime.fromisoformat(leg["arrive_at"]) if is_return else stops[i].eta
        legs_out.append({
            "index": i, "from": path[0], "to": path[-1], "to_return": is_return,
            "our_minutes": round(ours, 1), "google_minutes": google, "diff_minutes": round(google - ours, 1),
        })
        stop_rows.append({
            "stop_id": None if is_return else stops[i].id,
            "sequence": None if is_return else stops[i].sequence,
            "label": "Regreso a la bodega" if is_return else stops[i].order.recipient,
            "stored_eta": stored.isoformat(),
            "google_eta": (stored + timedelta(minutes=cumulative)).isoformat(),
            "diff_minutes": round(cumulative, 1),
        })

    our_total = round(sum(x["our_minutes"] for x in legs_out), 1)
    google_total = round(sum(x["google_minutes"] for x in legs_out), 1)
    diff = round(google_total - our_total, 1)
    payload = {
        "route_id": route.id, "checked_at": now.isoformat(),
        "our_minutes": our_total, "google_minutes": google_total, "diff_minutes": diff,
        "confirmed": abs(diff) <= TOLERANCE_MIN,
        "message": _message(diff, datetime.fromisoformat(stop_rows[-1]["google_eta"])),
        "legs": legs_out, "stops": stop_rows,
        "partial": len(checked) < len(pending),
        "cached": False,
    }
    cache.set(key, payload, CACHE_SECONDS)
    return payload
