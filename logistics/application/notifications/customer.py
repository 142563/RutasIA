"""Correos al cliente final (Order.recipient_email), como hace una mensajería.

Recibido, programado, en camino, entregado y no entregado; todos con el botón «Seguir mi pedido»
(página pública /seguimiento/<token>). Los pedidos de demo nunca envían correo.
"""
from __future__ import annotations

from datetime import timedelta

from logistics.domain.notifications import Event, customer_gets
from logistics.models import NotificationLog, Order, RouteStop

from .core import Message, dispatch, format_clock, format_day, format_moment, render_email, site_url

# Margen de la ventana de llegada que se le promete al cliente: ETA ± 30 min
WINDOW = timedelta(minutes=30)


def _reachable(order: Order) -> bool:
    return bool(order.recipient_email) and not order.is_demo


def tracking_url(order: Order) -> str:
    return site_url(f"seguimiento/{order.tracking_token}")


def _window(eta) -> dict:
    return {"window_from": format_clock(eta - WINDOW), "window_to": format_clock(eta + WINDOW)}


def _message(event: Event, order: Order, route_id: int | None, subject: str, template: str, context: dict,
             with_route_key: bool = False) -> Message:
    """Correo al cliente con el enlace de seguimiento; un mismo aviso nunca sale dos veces al mismo correo."""
    html, text = render_email(template, {
        "subject": subject, "recipient": order.recipient or "cliente", "code": order.code,
        "address": order.address, "tracking_url": tracking_url(order), **context,
    })
    key = f"{event}:order:{order.id}:{order.recipient_email.lower()}"
    if with_route_key:
        key = f"{event}:route:{route_id}:order:{order.id}:{order.recipient_email.lower()}"
    return Message(
        event=event, audience=NotificationLog.Audience.CUSTOMER, to=order.recipient_email, subject=subject,
        html=html, text=text, order_id=order.id, route_id=route_id, dedupe_key=key)


def notify_delivered(stop_id: int) -> list[str]:
    """Entregado → al cliente. Devuelve los destinatarios a los que se envió."""
    stop = RouteStop.objects.select_related("order", "route__driver").filter(pk=stop_id).first()
    if stop is None or stop.status != RouteStop.Status.DELIVERED or stop.delivered_at is None:
        return []
    order, route = stop.order, stop.route
    if not customer_gets(Event.DELIVERED) or not _reachable(order):
        return []
    subject = f"Tu pedido {order.code} fue entregado"
    when = format_moment(stop.delivered_at)
    driver_name = route.driver.name if route.driver else "nuestro conductor"
    html, text = render_email("delivered", {
        "subject": subject, "status_label": "Entregado", "recipient": order.recipient or "cliente",
        "code": order.code, "when": when, "address": order.address, "driver_name": driver_name,
        "details": [("Pedido", order.code), ("Entregado", when), ("Dirección", order.address),
                    ("Entregó", driver_name)],
        "tracking_url": tracking_url(order),
    })
    return dispatch([Message(
        event=Event.DELIVERED, audience=NotificationLog.Audience.CUSTOMER, to=order.recipient_email,
        subject=subject, html=html, text=text, order_id=order.id, route_id=route.id,
        dedupe_key=f"{Event.DELIVERED}:order:{order.id}:{order.recipient_email.lower()}",
    )])


def notify_order_received(order_id: int) -> list[str]:
    """Pedido registrado → al cliente: lo recibimos y le avisaremos cuando tenga fecha."""
    order = Order.objects.filter(pk=order_id).first()
    if order is None or not customer_gets(Event.ORDER_RECEIVED) or not _reachable(order):
        return []
    count = order.package_count
    return dispatch([_message(
        Event.ORDER_RECEIVED, order, None, f"Recibimos tu pedido {order.code}", "order_received",
        {"packages": f"{count} bulto" if count == 1 else f"{count} bultos"})])


def _route_stops(route_id: int, only_pending: bool = False) -> list[RouteStop]:
    stops = RouteStop.objects.select_related("order", "route__driver").filter(route_id=route_id).order_by("sequence")
    if only_pending:
        stops = stops.filter(status=RouteStop.Status.PENDING)
    return [s for s in stops if _reachable(s.order)]


def notify_route_scheduled(route_id: int) -> list[str]:
    """Ruta creada → a cada cliente: el día y la ventana estimada de llegada (un solo envío en lote)."""
    if not customer_gets(Event.ROUTE_ASSIGNED):
        return []
    messages = [
        _message(Event.ROUTE_ASSIGNED, s.order, route_id, f"Tu pedido {s.order.code} llegará el {format_day(s.eta)}",
                 "route_scheduled", {"day": format_day(s.eta), **_window(s.eta)}, with_route_key=True)
        for s in _route_stops(route_id)
    ]
    return dispatch(messages)


def notify_route_started(route_id: int) -> list[str]:
    """Conductor inició la ruta → a los clientes con paradas pendientes (un solo envío en lote)."""
    if not customer_gets(Event.ROUTE_STARTED):
        return []
    messages = []
    for s in _route_stops(route_id, only_pending=True):
        driver = s.route.driver
        first_name = driver.name.split()[0] if driver and driver.name.strip() else "Nuestro conductor"
        messages.append(_message(
            Event.ROUTE_STARTED, s.order, route_id, f"Tu pedido {s.order.code} va en camino", "route_started",
            {"driver_name": first_name, **_window(s.eta)}, with_route_key=True))
    return dispatch(messages)


def notify_delivery_failed(stop_id: int) -> list[str]:
    """Entrega fallida → al cliente: el motivo, sin culpas, y que lo contactarán para reprogramar."""
    stop = RouteStop.objects.select_related("order").filter(pk=stop_id).first()
    if stop is None or stop.status != RouteStop.Status.FAILED:
        return []
    order = stop.order
    if not customer_gets(Event.DELIVERY_FAILED) or not _reachable(order):
        return []
    return dispatch([_message(
        Event.DELIVERY_FAILED, order, stop.route_id, f"No pudimos entregar tu pedido {order.code}",
        "delivery_failed", {"reason": (stop.reason or "no se pudo completar la entrega").rstrip(". ")})])
