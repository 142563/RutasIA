"""Bitácora de avisos para la interfaz ("Avisos enviados"): sin cuerpo y con el correo enmascarado."""
from __future__ import annotations

from logistics.domain.notifications import Event
from logistics.models import NotificationLog

LIMIT = 50

EVENT_LABELS: dict[str, str] = {
    Event.ACCOUNT_CREATED: "Bienvenida a la cuenta",
    Event.ORDER_RECEIVED: "Pedido recibido",
    Event.ROUTE_ASSIGNED: "Ruta asignada",
    Event.ROUTE_STARTED: "Ruta en camino",
    Event.DELIVERED: "Pedido entregado",
    Event.DELIVERY_FAILED: "Entrega no realizada",
    Event.INCIDENT_REPORTED: "Incidente reportado",
    Event.REROUTE_PENDING: "Recálculo por aprobar",
    Event.REROUTE_APPROVED: "Cambio de ruta aprobado",
    Event.ROUTE_COMPLETED: "Resumen de ruta",
    Event.ROUTE_CANCELED: "Ruta cancelada",
}


def mask_email(email: str) -> str:
    """'julio@gmail.com' -> 'j***@gmail.com'."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def log_payload(entry: NotificationLog) -> dict:
    return {
        "id": entry.id,
        "event": entry.event,
        "event_label": EVENT_LABELS.get(entry.event, entry.event),
        "recipient": mask_email(entry.recipient),
        "audience": entry.audience,
        "audience_label": entry.get_audience_display(),
        "status": entry.status,
        "status_label": entry.get_status_display(),
        "created_at": entry.created_at.isoformat(),
    }


def recent_for_route(route_id: int) -> list[dict]:
    return [log_payload(e) for e in NotificationLog.objects.filter(route_id=route_id)[:LIMIT]]


def recent_for_order(order_id: int) -> list[dict]:
    return [log_payload(e) for e in NotificationLog.objects.filter(order_id=order_id)[:LIMIT]]
