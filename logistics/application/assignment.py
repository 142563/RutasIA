"""Asignar, reasignar y cancelar rutas (docs/PLAN.md §8, flujo A).

Reglas:
- Solo las rutas *planificadas* se reasignan o cancelan. Una ruta en curso ya
  salió: cambiarle el piloto o el camión desde aquí confundiría al conductor.
- Un piloto o un camión está "ocupado" si tiene OTRA ruta planificada o en curso
  cuyo horario [salida, fin] se traslapa con el de esta ruta.
- La carga total de los pedidos debe caber en la capacidad del camión.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from logistics.application.routing import parse_departure
from logistics.domain.exceptions import PlanningError
from logistics.models import Driver, Order, Route, Vehicle

ACTIVE_STATUSES = (Route.Status.PLANNED, Route.Status.IN_PROGRESS)
# Ventana por omisión cuando se consulta por fecha y no por ruta
DEFAULT_WINDOW = timedelta(hours=8)


class RouteNotFound(Exception):
    pass


def _overlapping(start: datetime, end: datetime, exclude_route_id: int | None = None):
    qs = Route.objects.filter(status__in=ACTIVE_STATUSES, departure_at__lt=end, finish_at__gt=start)
    if exclude_route_id:
        qs = qs.exclude(pk=exclude_route_id)
    return qs


def _busy_maps(start: datetime, end: datetime, exclude_route_id: int | None):
    """Mapas {driver_id: ruta} y {vehicle_id: ruta} de lo que está ocupado en la ventana."""
    by_driver: dict[int, Route] = {}
    by_vehicle: dict[int, Route] = {}
    for route in _overlapping(start, end, exclude_route_id).order_by("departure_at"):
        if route.driver_id:
            by_driver.setdefault(route.driver_id, route)
        if route.vehicle_id:
            by_vehicle.setdefault(route.vehicle_id, route)
    return by_driver, by_vehicle


def route_weight(route: Route) -> Decimal:
    return sum((s.order.weight_kg for s in route.stops.select_related("order")), Decimal("0"))


def _fmt_kg(value) -> str:
    return f"{float(value):,.0f}"


def _check_vehicle_basics(vehicle: Vehicle | None, weight: Decimal) -> Vehicle:
    if vehicle is None:
        raise PlanningError("El camión no existe.")
    if not vehicle.is_active:
        raise PlanningError(f"El camión {vehicle.plate} está inactivo y no se puede asignar.")
    if weight > Decimal(vehicle.capacity_kg):
        raise PlanningError(f"No cabe: la carga ({_fmt_kg(weight)} kg) excede la capacidad del camión "
                            f"{vehicle.plate} ({_fmt_kg(vehicle.capacity_kg)} kg).")
    return vehicle


def _check_driver_basics(driver: Driver | None) -> Driver:
    if driver is None:
        raise PlanningError("El piloto no existe.")
    if not driver.is_active:
        raise PlanningError(f"{driver.name} está inactivo y no se le pueden asignar rutas.")
    return driver


def check_driver(driver_id, start: datetime, end: datetime, exclude_route_id: int | None = None) -> Driver:
    driver = _check_driver_basics(Driver.objects.filter(pk=driver_id).first() if driver_id else None)
    busy = _overlapping(start, end, exclude_route_id).filter(driver=driver).first()
    if busy:
        raise PlanningError(f"{driver.name} ya está ocupado en la ruta {busy.code} en ese horario.")
    return driver


def check_vehicle(vehicle_id, weight: Decimal, start: datetime, end: datetime,
                  exclude_route_id: int | None = None) -> Vehicle:
    vehicle = _check_vehicle_basics(Vehicle.objects.filter(pk=vehicle_id).first() if vehicle_id else None, weight)
    busy = _overlapping(start, end, exclude_route_id).filter(vehicle=vehicle).first()
    if busy:
        raise PlanningError(f"El camión {vehicle.plate} ya está ocupado en la ruta {busy.code} en ese horario.")
    return vehicle


def validate_for_new_route(payload: dict, weight: Decimal) -> tuple[Driver | None, Vehicle | None]:
    """Existencia, estado activo y capacidad (antes de calcular la ruta).

    La disponibilidad por horario se revisa después con ``ensure_available``,
    porque necesita la hora de fin que sale del cálculo.
    """
    driver = vehicle = None
    if payload.get("driver_id"):
        driver = _check_driver_basics(Driver.objects.filter(pk=payload["driver_id"]).first())
    if payload.get("vehicle_id"):
        vehicle = _check_vehicle_basics(Vehicle.objects.filter(pk=payload["vehicle_id"]).first(), weight)
    return driver, vehicle


def ensure_available(driver: Driver | None, vehicle: Vehicle | None, start: datetime, end: datetime,
                     exclude_route_id: int | None = None) -> None:
    if driver:
        check_driver(driver.pk, start, end, exclude_route_id)
    if vehicle:
        check_vehicle(vehicle.pk, Decimal("0"), start, end, exclude_route_id)


def options(route_id=None, departure=None) -> dict:
    """Pilotos y camiones activos con su disponibilidad para la ventana de una ruta o de una fecha."""
    route = None
    weight = None
    if route_id not in (None, ""):
        try:
            route = Route.objects.get(pk=int(route_id))
        except (Route.DoesNotExist, ValueError, TypeError):
            raise RouteNotFound("La ruta no existe.") from None
        start, end = route.departure_at, route.finish_at
        weight = route_weight(route)
    else:
        start = parse_departure(departure)
        end = start + DEFAULT_WINDOW
    by_driver, by_vehicle = _busy_maps(start, end, route.pk if route else None)

    def busy_ref(r: Route | None):
        return {"id": r.id, "code": r.code} if r else None

    drivers = [
        {"id": d.id, "name": d.name, "phone": d.phone, "has_mobile_account": d.user_id is not None,
         "busy": d.id in by_driver, "busy_route": busy_ref(by_driver.get(d.id))}
        for d in Driver.objects.filter(is_active=True).order_by("name")
    ]
    vehicles = []
    for v in Vehicle.objects.filter(is_active=True).select_related("driver").order_by("plate"):
        fixed = v.driver if v.driver and v.driver.is_active else None
        vehicles.append({
            "id": v.id, "plate": v.plate, "model": v.model, "capacity_kg": float(v.capacity_kg),
            "default_driver_id": fixed.id if fixed else None,
            "default_driver": fixed.name if fixed else None,
            "busy": v.id in by_vehicle, "busy_route": busy_ref(by_vehicle.get(v.id)),
            "fits": None if weight is None else weight <= Decimal(v.capacity_kg),
        })
    return {
        "route_id": route.id if route else None,
        "window": {"start": timezone.localtime(start).isoformat(), "end": timezone.localtime(end).isoformat()},
        "total_weight_kg": float(weight) if weight is not None else None,
        "drivers": drivers,
        "vehicles": vehicles,
    }


def _response(route: Route, suggested_driver: bool = False) -> dict:
    from logistics.application.planning import route_payload  # import tardío: planning importa este módulo

    route = Route.objects.select_related("depot", "driver", "vehicle").get(pk=route.pk)
    data = route_payload(route)
    data["vehicle_id"] = route.vehicle_id
    data["vehicle_model"] = route.vehicle.model if route.vehicle else None
    return {"route": data, "suggested_driver": suggested_driver}


@transaction.atomic
def assign(route_id: int, payload: dict) -> dict:
    """Asigna o cambia piloto/camión. Una llave ausente no se toca; ``null`` quita la asignación."""
    try:
        route = Route.objects.select_for_update().get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound("La ruta no existe.") from None
    if route.status != Route.Status.PLANNED:
        raise PlanningError("Solo se puede asignar una ruta planificada. Una ruta en curso, "
                            "completada o cancelada ya no se reasigna.")
    if "driver_id" not in payload and "vehicle_id" not in payload:
        raise PlanningError("Indica el piloto o el camión.")

    start, end = route.departure_at, route.finish_at
    weight = route_weight(route)
    suggested = False

    if payload.get("vehicle_id"):
        vehicle = check_vehicle(payload["vehicle_id"], weight, start, end, route.pk)
        route.vehicle = vehicle
        # Camión con piloto fijo y sin piloto indicado ni asignado: se sugiere el fijo si está libre
        if "driver_id" not in payload and route.driver_id is None and vehicle.driver_id:
            fixed = vehicle.driver
            if fixed.is_active and not _overlapping(start, end, route.pk).filter(driver=fixed).exists():
                route.driver = fixed
                suggested = True
    elif "vehicle_id" in payload:
        route.vehicle = None

    if payload.get("driver_id"):
        route.driver = check_driver(payload["driver_id"], start, end, route.pk)
        suggested = False
    elif "driver_id" in payload:
        route.driver = None

    route.save(update_fields=["driver", "vehicle", "updated_at"])
    return _response(route, suggested)


@transaction.atomic
def cancel(route_id: int, reason: str = "") -> dict:
    """Cancela una ruta planificada: los pedidos vuelven a pendiente; las paradas quedan de historial."""
    try:
        route = Route.objects.select_for_update().get(pk=route_id)
    except Route.DoesNotExist:
        raise RouteNotFound("La ruta no existe.") from None
    if route.status != Route.Status.PLANNED:
        raise PlanningError("Solo se puede cancelar una ruta planificada. Una ruta en curso "
                            "debe terminarla el conductor.")
    reason = (reason or "").strip()[:120]
    route.status = Route.Status.CANCELED
    route.save(update_fields=["status", "updated_at"])
    order_ids = list(route.stops.values_list("order_id", flat=True))
    Order.objects.filter(id__in=order_ids, status=Order.Status.ASSIGNED).update(
        status=Order.Status.PENDING, updated_at=timezone.now())
    if reason:  # el motivo queda en las paradas (historial); no se borran
        route.stops.filter(reason="").update(reason=reason)
    data = _response(route)
    data["released_orders"] = len(order_ids)
    return data
