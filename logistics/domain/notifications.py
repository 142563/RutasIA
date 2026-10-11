"""Qué correo le llega a quién (docs/PLAN.md §14.2). El ROL decide; aquí solo hay datos.

Alcance de cada rol en un evento:
- ALL: todos los usuarios activos de ese rol que tengan correo.
- CREATOR: el usuario que creó la ruta (si tiene ese rol, correo y está activo).
- ASSIGNED: el conductor asignado a la ruta.
- SELF: el propio usuario (bienvenida).
El cliente final no es un usuario: recibe los eventos de CUSTOMER_EVENTS en Order.recipient_email.
"""
from __future__ import annotations

from enum import StrEnum


class Event(StrEnum):
    ACCOUNT_CREATED = "account_created"
    ORDER_RECEIVED = "order_received"
    ROUTE_ASSIGNED = "route_assigned"
    ROUTE_STARTED = "route_started"
    DELIVERED = "delivered"
    DELIVERY_FAILED = "delivery_failed"
    INCIDENT_REPORTED = "incident_reported"
    REROUTE_PENDING = "reroute_pending"
    REROUTE_APPROVED = "reroute_approved"
    ROUTE_COMPLETED = "route_completed"
    ROUTE_CANCELED = "route_canceled"


class Scope(StrEnum):
    ALL = "all"
    CREATOR = "creator"
    ASSIGNED = "assigned"
    SELF = "self"


# Roles tal como están en UserProfile.Role (no se importa el modelo: domain no depende de Django)
ADMIN, DISPATCHER, DRIVER = "admin", "dispatcher", "driver"

STAFF_MATRIX: dict[Event, dict[str, Scope]] = {
    Event.ACCOUNT_CREATED: {ADMIN: Scope.SELF, DISPATCHER: Scope.SELF, DRIVER: Scope.SELF},
    Event.ROUTE_ASSIGNED: {DRIVER: Scope.ASSIGNED},
    Event.DELIVERY_FAILED: {ADMIN: Scope.ALL, DISPATCHER: Scope.CREATOR},
    Event.INCIDENT_REPORTED: {ADMIN: Scope.ALL, DISPATCHER: Scope.ALL},
    Event.REROUTE_PENDING: {DISPATCHER: Scope.CREATOR},
    Event.REROUTE_APPROVED: {DRIVER: Scope.ASSIGNED},
    Event.ROUTE_COMPLETED: {DISPATCHER: Scope.CREATOR},
    Event.ROUTE_CANCELED: {DRIVER: Scope.ASSIGNED},
}

CUSTOMER_EVENTS: frozenset[Event] = frozenset({
    Event.ORDER_RECEIVED, Event.ROUTE_ASSIGNED, Event.ROUTE_STARTED, Event.DELIVERED, Event.DELIVERY_FAILED,
})

# Texto para el correo de bienvenida: qué le va a llegar a cada rol
ROLE_SUMMARY: dict[str, list[str]] = {
    ADMIN: ["Entregas que no se pudieron hacer.", "Incidentes reportados en la carretera."],
    DISPATCHER: [
        "Entregas que no se pudieron hacer en tus rutas.",
        "Incidentes reportados en la carretera.",
        "Recálculos de ruta que esperan tu aprobación.",
        "Un resumen cuando termina cada ruta que creaste.",
    ],
    DRIVER: ["Cada ruta que te asignen o cancelen.", "Los cambios de ruta aprobados mientras manejas."],
}


def staff_scopes(event: Event) -> dict[str, Scope]:
    """Roles del personal que reciben este evento y con qué alcance."""
    return STAFF_MATRIX.get(event, {})


def customer_gets(event: Event) -> bool:
    return event in CUSTOMER_EVENTS
