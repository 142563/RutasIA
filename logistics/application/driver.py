"""Vista del conductor (docs/PLAN.md §7): su ruta de hoy, iniciar y marcar entregas.

Todo se filtra por el Driver asociado al usuario logueado: un conductor nunca
ve ni modifica rutas o paradas de otro (responde 404, sin revelar que existen).
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from logistics.application.planning import route_payload
from logistics.domain.exceptions import PlanningError
from logistics.models import Driver, Order, Route, RouteStop

REASON_MAX = 120


class NotFoundError(PlanningError):
    """La ruta o la parada no existe o no es del conductor."""


def driver_for(user) -> Driver:
    driver = Driver.objects.filter(user=user).first()
    if driver is None:
        raise PlanningError("Tu usuario no tiene un conductor asociado. Pide al despachador que lo vincule.")
    return driver


def _own_routes(driver: Driver):
    return Route.objects.select_related("depot", "driver", "vehicle").filter(driver=driver)


def today_routes(user) -> dict:
    """Rutas del conductor con salida hoy (hora de Guatemala) más las que siguen en curso."""
    driver = driver_for(user)
    today = timezone.localdate()
    candidates = (
        _own_routes(driver)
        .filter(Q(departure_at__date=today) | Q(status=Route.Status.IN_PROGRESS))
        .exclude(status=Route.Status.CANCELED)
        .order_by("departure_at", "id")
    )
    # Se confirma la fecha local en Python para no depender de la zona horaria de la BD
    routes = [
        r for r in candidates
        if r.status == Route.Status.IN_PROGRESS or timezone.localtime(r.departure_at).date() == today
    ]
    return {
        "driver": {"id": driver.id, "name": driver.name, "phone": driver.phone},
        "date": today.isoformat(),
        "routes": [route_payload(r) for r in routes],
    }


def _begin(route: Route) -> None:
    now = timezone.now()
    route.status = Route.Status.IN_PROGRESS
    route.started_at = now
    route.save(update_fields=["status", "started_at", "updated_at"])
    Order.objects.filter(
        route_stops__route=route, route_stops__status=RouteStop.Status.PENDING, status=Order.Status.ASSIGNED,
    ).update(status=Order.Status.IN_TRANSIT, updated_at=now)


@transaction.atomic
def start_route(user, route_id: int) -> dict:
    driver = driver_for(user)
    route = _own_routes(driver).filter(pk=route_id).first()
    if route is None:
        raise NotFoundError("La ruta no existe.")
    if route.status != Route.Status.PLANNED:
        raise PlanningError(f"La ruta ya está «{route.get_status_display().lower()}»; solo se inicia una ruta planificada.")
    _begin(route)
    return {"route": route_payload(route)}


@transaction.atomic
def update_stop(user, stop_id: int, payload: dict) -> dict:
    driver = driver_for(user)
    status = payload.get("status")
    if status not in (RouteStop.Status.DELIVERED, RouteStop.Status.FAILED):
        raise PlanningError("El estado debe ser «delivered» o «failed».")
    reason = str(payload.get("reason") or "").strip()
    if status == RouteStop.Status.FAILED and not reason:
        raise PlanningError("Indica el motivo por el que no se entregó.")
    if len(reason) > REASON_MAX:
        raise PlanningError(f"El motivo admite hasta {REASON_MAX} caracteres.")

    stop = RouteStop.objects.select_related("order").filter(pk=stop_id, route__driver=driver).first()
    if stop is None:
        raise NotFoundError("La parada no existe.")
    route = _own_routes(driver).get(pk=stop.route_id)
    if route.status in (Route.Status.COMPLETED, Route.Status.CANCELED):
        raise PlanningError("La ruta ya no admite cambios.")
    if stop.status != RouteStop.Status.PENDING:
        raise PlanningError("Esta parada ya fue marcada.")

    now = timezone.now()
    stop.status = status
    stop.reason = reason if status == RouteStop.Status.FAILED else ""
    stop.delivered_at = now
    stop.save(update_fields=["status", "reason", "delivered_at"])
    Order.objects.filter(pk=stop.order_id).update(
        status=Order.Status.DELIVERED if status == RouteStop.Status.DELIVERED else Order.Status.FAILED,
        updated_at=now,
    )

    if route.status == Route.Status.PLANNED:
        _begin(route)
    if not route.stops.filter(status=RouteStop.Status.PENDING).exists():
        route.status = Route.Status.COMPLETED
        route.completed_at = now
        route.save(update_fields=["status", "completed_at", "updated_at"])
    return {"route": route_payload(route), "stop_id": stop.id}
