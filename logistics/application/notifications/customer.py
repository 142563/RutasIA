"""Correos al cliente final (Order.recipient_email), como hace una mensajería.

Hoy: entregado. A3 (RUT-71) agrega recibido, programado, en camino y no entregado, y el
enlace público de seguimiento. Los pedidos de demo nunca envían correo.
"""
from __future__ import annotations

from logistics.domain.notifications import Event, customer_gets
from logistics.models import NotificationLog, Order, RouteStop

from .core import Message, dispatch, format_moment, render_email


def _reachable(order: Order) -> bool:
    return bool(order.recipient_email) and not order.is_demo


def notify_delivered(stop_id: int) -> list[str]:
    """Entregado → al cliente. Devuelve los destinatarios a los que se envió."""
    stop = RouteStop.objects.select_related("order", "route__driver").filter(pk=stop_id).first()
    if stop is None or stop.status != RouteStop.Status.DELIVERED or stop.delivered_at is None:
        return []
    order, route = stop.order, stop.route
    if not customer_gets(Event.DELIVERED) or not _reachable(order):
        return []
    subject = f"Tu pedido {order.code} fue entregado"
    html, text = render_email("delivered", {
        "subject": subject, "recipient": order.recipient or "cliente", "code": order.code,
        "when": format_moment(stop.delivered_at), "address": order.address,
        "driver_name": route.driver.name if route.driver else "nuestro conductor",
        "tracking_url": "",
    })
    return dispatch([Message(
        event=Event.DELIVERED, audience=NotificationLog.Audience.CUSTOMER, to=order.recipient_email,
        subject=subject, html=html, text=text, order_id=order.id, route_id=route.id,
        dedupe_key=f"{Event.DELIVERED}:order:{order.id}:{order.recipient_email.lower()}",
    )])


def notify_order_received(order_id: int) -> list[str]:
    return []


def notify_route_scheduled(route_id: int) -> list[str]:
    return []


def notify_route_started(route_id: int) -> list[str]:
    return []


def notify_delivery_failed(stop_id: int) -> list[str]:
    return []
