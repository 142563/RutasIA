"""Un punto de entrada por evento del negocio; reparte entre cliente (customer.py) y personal (staff.py).

La lógica de negocio solo hace `later(on_algo, id)`: así planning, assignment, driver e incidents
no saben quién recibe qué (eso lo decide la matriz por rol de domain/notifications.py).
"""
from __future__ import annotations

from . import customer, staff


def on_order_received(order_id: int) -> list[str]:
    return customer.notify_order_received(order_id)


def on_route_created(route_id: int) -> list[str]:
    """Ruta planificada con sus pedidos: el cliente sabe qué día llega; el conductor, si ya hay uno."""
    return customer.notify_route_scheduled(route_id) + staff.notify_route_assigned(route_id)


def on_driver_assigned(route_id: int) -> list[str]:
    return staff.notify_route_assigned(route_id)


def on_route_canceled(route_id: int, driver_id: int | None) -> list[str]:
    return staff.notify_route_canceled(route_id, driver_id)


def on_route_started(route_id: int) -> list[str]:
    return customer.notify_route_started(route_id)


def on_delivered(stop_id: int) -> list[str]:
    return customer.notify_delivered(stop_id)


def on_delivery_failed(stop_id: int) -> list[str]:
    return customer.notify_delivery_failed(stop_id) + staff.notify_delivery_failed(stop_id)


def on_route_completed(route_id: int) -> list[str]:
    return staff.notify_route_completed(route_id)


def on_incident_reported(incident_id: int) -> list[str]:
    return staff.notify_incident_reported(incident_id)


def on_reroute_pending(proposal_id: int) -> list[str]:
    return staff.notify_reroute_pending(proposal_id)


def on_reroute_approved(proposal_id: int) -> list[str]:
    return staff.notify_reroute_approved(proposal_id)
