"""Configuración de la empresa (admin): bodegas, pilotos, camiones y usuarios.

Regla de oro: nada se borra. "Eliminar" desactiva, para no romper rutas históricas.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from logistics.domain.exceptions import PlanningError
from logistics.models import (
    GT_LAT_MAX, GT_LAT_MIN, GT_LON_MAX, GT_LON_MIN, Depot, Driver, Node, UserProfile, Vehicle,
)
from logistics.routing.graph import load_graph

KINDS = ("depots", "drivers", "vehicles", "users")
MIN_PASSWORD = 10
# Valores razonables cuando el usuario no los indica (se pueden editar después).
DEFAULT_KM_PER_LITER = Decimal("8")
DEFAULT_COST_PER_KM = Decimal("2.50")


def _text(payload: dict, key: str, label: str, *, required: bool = False, max_len: int = 120) -> str | None:
    """None = el campo no venía en el payload (no tocar)."""
    if key not in payload:
        if required:
            raise PlanningError(f"{label} es obligatorio.")
        return None
    value = str(payload[key] or "").strip()
    if required and not value:
        raise PlanningError(f"{label} es obligatorio.")
    if len(value) > max_len:
        raise PlanningError(f"{label} es demasiado largo (máximo {max_len} caracteres).")
    return value


def _number(payload: dict, key: str, label: str, *, positive: bool = True) -> Decimal | None:
    if key not in payload or payload[key] in (None, ""):
        return None
    try:
        value = Decimal(str(payload[key]))
    except (InvalidOperation, ValueError):
        raise PlanningError(f"{label} debe ser un número.") from None
    if not value.is_finite() or value > Decimal("99999") or (value <= 0 if positive else value < 0):
        raise PlanningError(f"{label} debe ser un número mayor que 0." if positive else f"{label} no es válido.")
    return value.quantize(Decimal("0.01"))


def _flag(payload: dict, key: str = "is_active") -> bool | None:
    if key not in payload:
        return None
    if not isinstance(payload[key], bool):
        raise PlanningError("El estado (activo/inactivo) no es válido.")
    return payload[key]


def _check_password(password: Any) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise PlanningError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    return password


def _save(obj, message: str) -> None:
    try:
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        raise PlanningError(message) from None


# --- bodegas -----------------------------------------------------------------

def _nearest_node_or_none(lat: float, lng: float) -> Node | None:
    graph = load_graph()
    if graph.node_count == 0:
        return None
    return Node.objects.filter(code=graph.codes[graph.nearest_node(lat, lng)]).first()


def _depot_payload(depot: Depot) -> dict:
    return {
        "id": depot.id, "name": depot.name, "address": depot.address,
        "latitude": depot.latitude, "longitude": depot.longitude,
        "node": {"code": depot.node.code, "name": depot.node.name} if depot.node else None,
        "is_active": depot.is_active,
    }


def _coords(payload: dict, current: tuple[float, float] | None) -> tuple[float, float]:
    if "latitude" not in payload and "longitude" not in payload and current:
        return current
    try:
        lat, lng = float(payload["latitude"]), float(payload["longitude"])
    except (KeyError, TypeError, ValueError):
        raise PlanningError("Indica la ubicación de la bodega (latitud y longitud).") from None
    if not (GT_LAT_MIN <= lat <= GT_LAT_MAX and GT_LON_MIN <= lng <= GT_LON_MAX):
        raise PlanningError("La ubicación está fuera de Guatemala. Revisa las coordenadas.")
    return lat, lng


def _write_depot(payload: dict, depot: Depot | None) -> dict:
    creating = depot is None
    depot = depot or Depot()
    name = _text(payload, "name", "El nombre", required=creating)
    if name is not None:
        if not name:
            raise PlanningError("El nombre es obligatorio.")
        depot.name = name
    address = _text(payload, "address", "La dirección", max_len=255)
    if address is not None:
        depot.address = address
    current = None if creating else (depot.latitude, depot.longitude)
    lat, lng = _coords(payload, current)
    if creating or (lat, lng) != current:
        depot.latitude, depot.longitude = lat, lng
        depot.node = _nearest_node_or_none(lat, lng)
    active = _flag(payload)
    if active is not None:
        depot.is_active = active
    _save(depot, "Ya existe una bodega con ese nombre.")
    return _depot_payload(depot)


# --- pilotos -----------------------------------------------------------------

def _driver_payload(driver: Driver) -> dict:
    return {
        "id": driver.id, "name": driver.name, "phone": driver.phone,
        "license_number": driver.license_number, "is_active": driver.is_active,
        "user": {"id": driver.user_id, "username": driver.user.username} if driver.user else None,
    }


def _link_user(driver: Driver, user_id: Any) -> None:
    if user_id in (None, ""):
        driver.user = None
        return
    user = User.objects.filter(pk=user_id).select_related("profile").first()
    if not user:
        raise PlanningError("No existe esa cuenta de usuario.")
    if getattr(getattr(user, "profile", None), "role", None) != UserProfile.Role.DRIVER:
        raise PlanningError("Solo se puede enlazar una cuenta con rol Conductor.")
    other = Driver.objects.filter(user=user).exclude(pk=driver.pk).first()
    if other:
        raise PlanningError(f"Esa cuenta ya está enlazada al piloto {other.name}.")
    driver.user = user


def _write_driver(payload: dict, driver: Driver | None) -> dict:
    creating = driver is None
    driver = driver or Driver()
    name = _text(payload, "name", "El nombre", required=creating)
    if name is not None:
        if not name:
            raise PlanningError("El nombre es obligatorio.")
        driver.name = name
    phone = _text(payload, "phone", "El teléfono", max_len=20)
    if phone is not None:
        driver.phone = phone
    license_number = _text(payload, "license_number", "La licencia", required=creating, max_len=30)
    if license_number is not None:
        if not license_number:
            raise PlanningError("La licencia es obligatoria.")
        driver.license_number = license_number
    active = _flag(payload)
    if active is not None:
        driver.is_active = active

    username = _text(payload, "username", "El usuario", max_len=150)
    with transaction.atomic():
        if username:
            if driver.user_id:
                raise PlanningError("Este piloto ya tiene cuenta. Desvincúlala primero o edítala en Usuarios.")
            if User.objects.filter(username__iexact=username).exists():
                raise PlanningError("Ya existe un usuario con ese nombre de usuario.")
            password = _check_password(payload.get("password"))
            user = User.objects.create_user(username=username, password=password, first_name=driver.name[:150])
            UserProfile.objects.create(user=user, role=UserProfile.Role.DRIVER)
            driver.user = user
        elif "user_id" in payload:
            _link_user(driver, payload["user_id"])
        _save(driver, "Ya existe un piloto con ese número de licencia (o la cuenta ya está enlazada).")
    return _driver_payload(driver)


# --- camiones ----------------------------------------------------------------

def _vehicle_payload(vehicle: Vehicle) -> dict:
    return {
        "id": vehicle.id, "plate": vehicle.plate, "model": vehicle.model,
        "capacity_kg": float(vehicle.capacity_kg),
        "fuel_efficiency_km_l": float(vehicle.fuel_efficiency_km_l),
        "cost_per_km": float(vehicle.cost_per_km),
        "driver": {"id": vehicle.driver_id, "name": vehicle.driver.name} if vehicle.driver else None,
        "is_active": vehicle.is_active,
    }


def _write_vehicle(payload: dict, vehicle: Vehicle | None) -> dict:
    creating = vehicle is None
    vehicle = vehicle or Vehicle()
    plate = _text(payload, "plate", "La placa", required=creating, max_len=16)
    if plate is not None:
        if not plate:
            raise PlanningError("La placa es obligatoria.")
        vehicle.plate = plate.upper()
    model = _text(payload, "model", "El modelo", max_len=100)
    if model is not None:
        vehicle.model = model
    if creating and not vehicle.model:
        vehicle.model = "Sin especificar"
    capacity = _number(payload, "capacity_kg", "La capacidad (kg)")
    if capacity is None and creating:
        raise PlanningError("La capacidad (kg) debe ser un número mayor que 0.")
    if capacity is not None:
        vehicle.capacity_kg = capacity
    efficiency = _number(payload, "fuel_efficiency_km_l", "El rendimiento (km/l)")
    if efficiency is not None:
        vehicle.fuel_efficiency_km_l = efficiency
    elif creating:
        vehicle.fuel_efficiency_km_l = DEFAULT_KM_PER_LITER
    cost = _number(payload, "cost_per_km", "El costo por km")
    if cost is not None:
        vehicle.cost_per_km = cost
    elif creating:
        vehicle.cost_per_km = DEFAULT_COST_PER_KM
    if "driver_id" in payload:
        if payload["driver_id"] in (None, ""):
            vehicle.driver = None
        else:
            driver = Driver.objects.filter(pk=payload["driver_id"]).first()
            if not driver:
                raise PlanningError("No existe ese piloto.")
            vehicle.driver = driver
    active = _flag(payload)
    if active is not None:
        vehicle.is_active = active
    _save(vehicle, "Ya existe un camión con esa placa.")
    return _vehicle_payload(vehicle)


# --- usuarios ----------------------------------------------------------------

def _user_payload(user: User) -> dict:
    role = getattr(getattr(user, "profile", None), "role", None)
    if role is None:
        role = UserProfile.Role.ADMIN if user.is_superuser else UserProfile.Role.DRIVER
    return {
        "id": user.id, "username": user.username, "full_name": user.get_full_name(),
        "role": role, "role_label": UserProfile.Role(role).label, "is_active": user.is_active,
    }


def _write_user(payload: dict, user: User | None, actor: User) -> dict:
    creating = user is None
    username = _text(payload, "username", "El usuario", required=creating, max_len=150)
    full_name = _text(payload, "full_name", "El nombre completo")
    role = payload.get("role") if "role" in payload else None
    if role is not None and role not in UserProfile.Role.values:
        raise PlanningError("El rol debe ser Administrador, Despachador o Conductor.")
    if creating and role is None:
        raise PlanningError("Elige el rol del usuario.")
    active = _flag(payload)
    password = payload.get("password") if "password" in payload else None
    if creating or password not in (None, ""):
        password = _check_password(password)
    else:
        password = None

    if not creating and user.pk == actor.pk:
        if active is False:
            raise PlanningError("No puedes desactivar tu propia cuenta.")
        if role is not None and role != UserProfile.Role.ADMIN:
            raise PlanningError("No puedes quitarte el rol de administrador a ti mismo.")

    with transaction.atomic():
        if creating:
            if not username:
                raise PlanningError("El usuario es obligatorio.")
            if User.objects.filter(username__iexact=username).exists():
                raise PlanningError("Ya existe un usuario con ese nombre de usuario.")
            user = User.objects.create_user(username=username, password=password)
        elif username:
            if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                raise PlanningError("Ya existe un usuario con ese nombre de usuario.")
            user.username = username
        if full_name is not None:
            first, _, last = full_name.partition(" ")
            user.first_name, user.last_name = first, last
        if active is not None:
            user.is_active = active
        if password and not creating:
            user.set_password(password)
        _save(user, "No se pudo guardar el usuario.")
        if role is not None:
            UserProfile.objects.update_or_create(user=user, defaults={"role": role})
    return _user_payload(User.objects.select_related("profile").get(pk=user.pk))


# --- punto de entrada --------------------------------------------------------

def _queryset(kind: str):
    return {
        "depots": Depot.objects.select_related("node").order_by("-is_active", "name"),
        "drivers": Driver.objects.select_related("user").order_by("-is_active", "name"),
        "vehicles": Vehicle.objects.select_related("driver").order_by("-is_active", "plate"),
        "users": User.objects.select_related("profile").order_by("-is_active", "username"),
    }[kind]


_SERIALIZERS = {"depots": _depot_payload, "drivers": _driver_payload, "vehicles": _vehicle_payload, "users": _user_payload}
_KEYS = {"depots": "depot", "drivers": "driver", "vehicles": "vehicle", "users": "user"}
_NOT_FOUND = {"depots": "la bodega", "drivers": "el piloto", "vehicles": "el camión", "users": "el usuario"}


def list_items(kind: str) -> dict:
    return {kind: [_SERIALIZERS[kind](obj) for obj in _queryset(kind)]}


def _get(kind: str, item_id: int):
    obj = _queryset(kind).filter(pk=item_id).first()
    if obj is None:
        raise LookupError(f"No se encontró {_NOT_FOUND[kind]}.")
    return obj


def get_item(kind: str, item_id: int) -> dict:
    return {_KEYS[kind]: _SERIALIZERS[kind](_get(kind, item_id))}


def _write(kind: str, payload: dict, obj, actor: User) -> dict:
    if kind == "users":
        data = _write_user(payload, obj, actor)
    else:
        data = {"depots": _write_depot, "drivers": _write_driver, "vehicles": _write_vehicle}[kind](payload, obj)
    return {_KEYS[kind]: data}


def create_item(kind: str, payload: dict, actor: User) -> dict:
    return _write(kind, payload, None, actor)


def update_item(kind: str, item_id: int, payload: dict, actor: User) -> dict:
    return _write(kind, payload, _get(kind, item_id), actor)


def deactivate_item(kind: str, item_id: int, actor: User) -> dict:
    """DELETE = desactivar. Los datos históricos se conservan."""
    return update_item(kind, item_id, {"is_active": False}, actor)
