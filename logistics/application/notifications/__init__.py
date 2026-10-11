"""Avisos por correo (docs/PLAN.md §14.2). El rol decide quién recibe qué: logistics/domain/notifications.py.

- core.py: Message, dispatch (envío + bitácora + sin repetir), later (después del commit, sin romper nada).
- transport.py: Resend (uno o en lote).
- recipients.py: a qué usuarios del personal les toca un evento.
- customer.py: correos al cliente final. account.py: bienvenida. staff.py: avisos al personal.
"""
from .core import Message, dispatch, format_clock, format_day, format_moment, later, render_email, safely, site_url
from .customer import notify_delivered
from .hooks import (
    on_delivered, on_delivery_failed, on_driver_assigned, on_incident_reported, on_order_received, on_reroute_approved,
    on_reroute_pending, on_route_canceled, on_route_completed, on_route_created, on_route_started,
)

__all__ = [
    "Message", "dispatch", "format_clock", "format_day", "format_moment", "later", "notify_delivered",
    "render_email", "safely", "site_url",
    "on_delivered", "on_delivery_failed", "on_driver_assigned", "on_incident_reported", "on_order_received",
    "on_reroute_approved", "on_reroute_pending", "on_route_canceled", "on_route_completed", "on_route_created",
    "on_route_started",
]
