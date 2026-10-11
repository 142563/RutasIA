"""Seguimiento público del pedido (A3, RUT-71): arma SOLO lo que el cliente final puede ver.

Nunca incluye teléfonos, dirección completa, coordenadas, ids internos ni datos de otros pedidos.
"""
from __future__ import annotations

import re
from datetime import timedelta

from logistics.domain.regions import region_of
from logistics.models import Order, Route, RouteStop

# Los tokens son secrets.token_urlsafe(16): 22 caracteres. Se valida el formato antes de tocar la BD.
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,32}$")
WINDOW = timedelta(minutes=30)

FAILED_NOTE = "No pudimos entregar tu pedido. Nos pondremos en contacto contigo para reprogramar la entrega."


def valid_token(token: str) -> bool:
    return bool(TOKEN_RE.match(token or ""))


def _iso(moment) -> str | None:
    return moment.isoformat() if moment else None


def _current_stop(order: Order) -> RouteStop | None:
    """La parada vigente: la más reciente que no sea de una ruta cancelada."""
    stops = (RouteStop.objects.select_related("route__driver")
             .filter(order=order).exclude(route__status=Route.Status.CANCELED).order_by("-id"))
    return stops.first()


def build_payload(token: str) -> dict | None:
    """Estado público del pedido, o None si el token no existe."""
    if not valid_token(token):
        return None
    order = Order.objects.select_related("node").filter(tracking_token=token).first()
    if order is None:
        return None
    stop = _current_stop(order)
    route = stop.route if stop else None

    delivered = order.status == Order.Status.DELIVERED
    failed = order.status == Order.Status.FAILED
    active = order.status in (Order.Status.ASSIGNED, Order.Status.IN_TRANSIT)
    pending_stop = bool(stop and stop.status == RouteStop.Status.PENDING)
    on_the_way = bool(route and active and pending_stop and route.status == Route.Status.IN_PROGRESS)

    last_at = stop.delivered_at if stop and (delivered or failed) else None
    timeline = [
        {"key": "received", "label": "Pedido recibido", "at": _iso(order.created_at), "done": True},
        {"key": "scheduled", "label": "Entrega programada", "at": _iso(route.created_at) if route else None,
         "done": route is not None},
        {"key": "on_the_way", "label": "En camino", "at": _iso(route.started_at) if route else None,
         "done": bool(route and route.started_at)},
        {"key": "failed" if failed else "delivered", "label": "No entregado" if failed else "Entregado",
         "at": _iso(last_at), "done": delivered or failed},
    ]

    window = None
    if stop and active and pending_stop:
        window = {"from": _iso(stop.eta - WINDOW), "to": _iso(stop.eta + WINDOW)}

    driver = route.driver if on_the_way else None
    driver_name = driver.name.split()[0] if driver and driver.name.strip() else None

    return {
        "ok": True,
        "code": order.code,
        "status": order.status,
        "status_label": order.get_status_display(),
        "timeline": timeline,
        "window": window,
        "place": {
            "municipality": order.node.name if order.node else None,
            "region": (region_of(order.node.department) or {}).get("name") if order.node else None,
        },
        "driver_name": driver_name,
        "note": FAILED_NOTE if failed else None,
    }
