"""Avisos al personal según su rol (A4, RUT-72): excepciones, resumen de ruta y avisos al conductor.

Cada función devuelve los correos a los que se envió. Destinatarios: recipients.staff_recipients.
"""
from __future__ import annotations


def notify_route_assigned(route_id: int) -> list[str]:
    return []


def notify_route_canceled(route_id: int, driver_id: int | None) -> list[str]:
    return []


def notify_delivery_failed(stop_id: int) -> list[str]:
    return []


def notify_route_completed(route_id: int) -> list[str]:
    return []


def notify_incident_reported(incident_id: int) -> list[str]:
    return []


def notify_reroute_pending(proposal_id: int) -> list[str]:
    return []


def notify_reroute_approved(proposal_id: int) -> list[str]:
    return []
