"""GPS: permiso por ruta y límite compartido entre procesos del servidor."""
from datetime import timedelta
from math import isfinite

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from logistics.application.driver import NotFoundError, driver_for
from logistics.domain.exceptions import PlanningError
from logistics.models import Driver, Route, VehiclePosition

MIN_INTERVAL = timedelta(seconds=5)
TRACE_WINDOW = timedelta(minutes=30)
TRACE_LIMIT = 360


class PositionRateError(PlanningError):
    pass


def _number(payload, key, low, high, optional=False, exclusive_high=False):
    label = {"lat": "Latitud", "lng": "Longitud", "speed_kmh": "Velocidad",
             "heading": "Orientación", "accuracy_m": "Precisión"}[key]
    value = payload.get(key)
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanningError(f"{label}: indica un número válido.")
    try:
        value = float(value)
    except OverflowError:
        raise PlanningError(f"{label}: el valor está fuera del rango permitido.") from None
    if not isfinite(value) or value < low or value > high or (exclusive_high and value == high):
        raise PlanningError(f"{label}: el valor está fuera del rango permitido.")
    return value


def position_payload(position):
    if position is None:
        return None
    return {key: getattr(position, key) for key in (
        "id", "lat", "lng", "speed_kmh", "heading", "accuracy_m", "source",
    )} | {"recorded_at": position.recorded_at.isoformat()}


@transaction.atomic
def record_position(user, payload):
    driver = driver_for(user)
    route_id = payload.get("route_id")
    if isinstance(route_id, bool) or not isinstance(route_id, int) or route_id <= 0:
        raise PlanningError("Indica una ruta válida.")
    route = Route.objects.select_for_update().filter(pk=route_id, driver=driver).first()
    if route is None:
        raise NotFoundError("La ruta no existe.")
    if route.status != Route.Status.IN_PROGRESS:
        raise PlanningError("Solo puedes compartir ubicación durante una ruta en curso.")
    if payload.get("source", VehiclePosition.Source.PHONE) != VehiclePosition.Source.PHONE:
        raise PlanningError("Esta sesión solo admite posiciones del celular.")
    values = {
        "lat": _number(payload, "lat", -90, 90),
        "lng": _number(payload, "lng", -180, 180),
        "speed_kmh": _number(payload, "speed_kmh", 0, 300, optional=True),
        "heading": _number(payload, "heading", 0, 360, optional=True, exclusive_high=True),
        "accuracy_m": _number(payload, "accuracy_m", 0, 100000, optional=True),
    }
    now = timezone.now()
    # UPDATE condicional: dos workers no pueden reservar el mismo intervalo.
    reserved = Driver.objects.filter(pk=driver.pk).filter(
        Q(last_position_at__isnull=True) | Q(last_position_at__lte=now - MIN_INTERVAL)
    ).update(last_position_at=now)
    # El UPDATE conserva el bloqueo del conductor hasta terminar la transacción;
    # el historial impide que una edición de Configuración restablezca el límite.
    if not reserved or VehiclePosition.objects.filter(driver=driver, recorded_at__gt=now - MIN_INTERVAL).exists():
        raise PositionRateError("Espera 5 segundos antes de volver a enviar tu ubicación.")
    position = VehiclePosition.objects.create(route=route, driver=driver, recorded_at=now, **values)
    return {"position": position_payload(position)}


def route_positions(route_id, params):
    if not Route.objects.filter(pk=route_id).exists():
        raise NotFoundError("La ruta no existe.")
    cutoff = timezone.now() - TRACE_WINDOW
    since = params.get("since")
    if since:
        try:
            moment = parse_datetime(since)
        except (ValueError, TypeError):
            moment = None
        if moment is None or timezone.is_naive(moment):
            raise PlanningError("Indica since en formato ISO con zona horaria.")
        cutoff = max(cutoff, moment)
    positions = VehiclePosition.objects.filter(route_id=route_id)
    latest = positions.order_by("-recorded_at", "-id").first()
    trace = list(positions.filter(recorded_at__gt=cutoff).order_by("-recorded_at", "-id")[:TRACE_LIMIT])
    return {"route_id": route_id, "latest": position_payload(latest),
            "positions": [position_payload(position) for position in reversed(trace)]}
