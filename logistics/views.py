from __future__ import annotations

import json
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .models import Department, Driver, Order, RouteConnection, Trip, TripEvent, UserProfile, Vehicle
from .services import PlanningError, TripLifecycleService, TripPlanner


def _as_float(value: Decimal | None) -> float:
    return float(value or 0)


def _parse_json(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise PlanningError("JSON inválido en la solicitud.")


def _ok(payload: dict, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": True, **payload}, status=status)


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _get_role(request: HttpRequest) -> str:
    try:
        return request.user.profile.role
    except Exception:
        return UserProfile.Role.OPERATOR


def _require_role(request: HttpRequest, *allowed_roles: str) -> JsonResponse | None:
    if _get_role(request) not in allowed_roles:
        return _error("No tienes permisos para esta acción.", 403)
    return None


def _serialize_department(department: Department) -> dict:
    return {
        "id": department.id,
        "code": department.code,
        "name": department.name,
        "latitude": float(department.latitude) if department.latitude else None,
        "longitude": float(department.longitude) if department.longitude else None,
    }


def _serialize_driver(driver: Driver) -> dict:
    return {
        "id": driver.id,
        "name": driver.name,
        "phone": driver.phone,
        "license_number": driver.license_number,
        "is_active": driver.is_active,
    }


def _serialize_vehicle(vehicle: Vehicle) -> dict:
    return {
        "id": vehicle.id,
        "plate": vehicle.plate,
        "model": vehicle.model,
        "capacity_kg": _as_float(vehicle.capacity_kg),
        "fuel_efficiency_km_l": _as_float(vehicle.fuel_efficiency_km_l),
        "cost_per_km": _as_float(vehicle.cost_per_km),
        "is_active": vehicle.is_active,
        "current_department_id": vehicle.current_department_id,
        "current_department_name": vehicle.current_department.name if vehicle.current_department else None,
        "driver_id": vehicle.driver_id,
        "driver_name": vehicle.driver.name if vehicle.driver else None,
    }


def _serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "code": order.code,
        "origin_id": order.origin_id,
        "origin_name": order.origin.name,
        "destination_id": order.destination_id,
        "destination_name": order.destination.name,
        "weight_kg": _as_float(order.weight_kg),
        "package_count": order.package_count,
        "priority": order.priority,
        "status": order.status,
        "requested_for": order.requested_for.isoformat(),
    }


def _serialize_event(event: TripEvent) -> dict:
    return {
        "id": event.id,
        "note": event.note,
        "created_at": timezone.localtime(event.created_at).isoformat(),
    }


def _serialize_trip(trip: Trip) -> dict:
    return {
        "id": trip.id,
        "code": trip.code,
        "vehicle_id": trip.vehicle_id,
        "vehicle_plate": trip.vehicle.plate,
        "driver_id": trip.driver_id,
        "driver_name": trip.driver.name if trip.driver else None,
        "origin_name": trip.origin.name,
        "destination_name": trip.destination.name,
        "route_nodes": trip.route_nodes,
        "total_distance_km": _as_float(trip.total_distance_km),
        "estimated_fuel_liters": _as_float(trip.estimated_fuel_liters),
        "estimated_cost": _as_float(trip.estimated_cost),
        "status": trip.status,
        "started_at": trip.started_at.isoformat() if trip.started_at else None,
        "completed_at": trip.completed_at.isoformat() if trip.completed_at else None,
        "orders": [_serialize_order(order) for order in trip.orders.all().order_by("-created_at")],
        "events": [_serialize_event(event) for event in trip.events.all()],
    }


def _dashboard_payload(date_from=None, date_to=None) -> dict:
    trips = Trip.objects.all()
    if date_from:
        trips = trips.filter(created_at__date__gte=date_from)
    if date_to:
        trips = trips.filter(created_at__date__lte=date_to)

    aggregates = trips.aggregate(
        total_trips=Count("id"),
        total_cost=Sum("estimated_cost"),
        total_distance=Sum("total_distance_km"),
    )

    status_distribution = list(
        trips.values("status").annotate(total=Count("id")).order_by("status")
    )
    vehicle_activity = list(
        Vehicle.objects.annotate(total_trips=Count("trips"))
        .order_by("-total_trips", "plate")
        .values("plate", "total_trips")[:6]
    )

    today = timezone.localdate()
    timeline = []
    for delta in range(6, -1, -1):
        day = today - timedelta(days=delta)
        timeline.append(
            {
                "date": day.isoformat(),
                "trips": trips.filter(created_at__date=day).count(),
            }
        )

    return {
        "summary": {
            "total_trips": aggregates["total_trips"] or 0,
            "active_trips": trips.filter(status__in=[Trip.Status.PLANNED, Trip.Status.IN_PROGRESS]).count(),
            "pending_orders": Order.objects.filter(status=Order.Status.PENDING).count(),
            "delivered_orders": Order.objects.filter(status=Order.Status.DELIVERED).count(),
            "total_cost": _as_float(aggregates["total_cost"]),
            "total_distance_km": _as_float(aggregates["total_distance"]),
        },
        "status_distribution": status_distribution,
        "vehicle_activity": vehicle_activity,
        "timeline": timeline,
    }


@ensure_csrf_cookie
@login_required
@require_GET
def index(request: HttpRequest):
    return render(request, "logistics/index.html")


@login_required
@require_GET
def api_me(request: HttpRequest):
    user = request.user
    return _ok({
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.get_full_name(),
            "role": _get_role(request),
        }
    })


@login_required
@require_http_methods(["GET", "POST"])
def api_users(request: HttpRequest):
    perm_error = _require_role(request, UserProfile.Role.ADMIN)
    if perm_error:
        return perm_error

    if request.method == "GET":
        users = User.objects.select_related("profile").all().order_by("username")
        result = []
        for u in users:
            role = UserProfile.Role.OPERATOR
            try:
                role = u.profile.role
            except Exception:
                pass
            result.append({
                "id": u.id,
                "username": u.username,
                "full_name": u.get_full_name(),
                "email": u.email,
                "role": role,
                "is_active": u.is_active,
            })
        return _ok({"users": result})

    try:
        payload = _parse_json(request)
        username = str(payload["username"]).strip()
        password = str(payload["password"])
        role = payload.get("role", UserProfile.Role.OPERATOR)
        first_name = str(payload.get("first_name", "")).strip()
        last_name = str(payload.get("last_name", "")).strip()
        email = str(payload.get("email", "")).strip()

        if User.objects.filter(username=username).exists():
            return _error("El nombre de usuario ya existe.")
        if role not in [r[0] for r in UserProfile.Role.choices]:
            return _error("Rol inválido.")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        UserProfile.objects.create(user=user, role=role)
        return _ok({
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
                "role": role,
                "is_active": user.is_active,
            }
        }, status=201)
    except KeyError as exc:
        return _error(f"Falta el campo requerido: {exc.args[0]}")
    except Exception as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["GET", "POST"])
def api_drivers(request: HttpRequest):
    if request.method == "GET":
        drivers = Driver.objects.all()
        return _ok({"drivers": [_serialize_driver(d) for d in drivers]})

    perm_error = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.SUPERVISOR)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        driver = Driver.objects.create(
            name=str(payload["name"]).strip(),
            phone=str(payload.get("phone", "")).strip(),
            license_number=str(payload["license_number"]).strip(),
            is_active=bool(payload.get("is_active", True)),
        )
        return _ok({"driver": _serialize_driver(driver)}, status=201)
    except KeyError as exc:
        return _error(f"Falta el campo requerido: {exc.args[0]}")
    except Exception as exc:
        return _error(str(exc))


@login_required
@require_GET
def api_departments(request: HttpRequest):
    departments = Department.objects.all()
    return _ok({"departments": [_serialize_department(d) for d in departments]})


@login_required
@require_GET
def api_connections(request: HttpRequest):
    connections = (
        RouteConnection.objects.select_related("origin", "destination").all()
    )
    payload = [
        {
            "id": c.id,
            "origin_id": c.origin_id,
            "origin_name": c.origin.name,
            "destination_id": c.destination_id,
            "destination_name": c.destination.name,
            "distance_km": _as_float(c.distance_km),
            "is_bidirectional": c.is_bidirectional,
        }
        for c in connections
    ]
    return _ok({"connections": payload})


@login_required
@require_http_methods(["GET", "POST"])
def api_vehicles(request: HttpRequest):
    if request.method == "GET":
        vehicles = Vehicle.objects.select_related("current_department", "driver").all()
        return _ok({"vehicles": [_serialize_vehicle(v) for v in vehicles]})

    perm_error = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.SUPERVISOR)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        current_department = None
        current_department_id = payload.get("current_department_id")
        if current_department_id:
            current_department = Department.objects.get(pk=current_department_id)

        driver = None
        driver_id = payload.get("driver_id")
        if driver_id:
            driver = Driver.objects.get(pk=driver_id)

        vehicle = Vehicle.objects.create(
            plate=str(payload["plate"]).strip().upper(),
            model=str(payload["model"]).strip(),
            capacity_kg=Decimal(str(payload["capacity_kg"])),
            fuel_efficiency_km_l=Decimal(str(payload["fuel_efficiency_km_l"])),
            cost_per_km=Decimal(str(payload["cost_per_km"])),
            is_active=bool(payload.get("is_active", True)),
            current_department=current_department,
            driver=driver,
        )
        return _ok({"vehicle": _serialize_vehicle(vehicle)}, status=201)
    except KeyError as exc:
        return _error(f"Falta el campo requerido: {exc.args[0]}")
    except Department.DoesNotExist:
        return _error("Departamento actual inválido.")
    except Driver.DoesNotExist:
        return _error("Conductor inválido.")
    except Exception as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["GET", "POST"])
def api_orders(request: HttpRequest):
    if request.method == "GET":
        orders = Order.objects.select_related("origin", "destination").all()
        status_filter = request.GET.get("status")
        origin_filter = request.GET.get("origin_id")
        destination_filter = request.GET.get("destination_id")
        if status_filter:
            orders = orders.filter(status=status_filter)
        if origin_filter:
            orders = orders.filter(origin_id=origin_filter)
        if destination_filter:
            orders = orders.filter(destination_id=destination_filter)
        return _ok({"orders": [_serialize_order(o) for o in orders]})

    perm_error = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.SUPERVISOR)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        origin = Department.objects.get(pk=payload["origin_id"])
        destination = Department.objects.get(pk=payload["destination_id"])
        if origin.id == destination.id:
            return _error("Origen y destino no pueden ser iguales.")

        order = Order.objects.create(
            origin=origin,
            destination=destination,
            weight_kg=Decimal(str(payload["weight_kg"])),
            package_count=int(payload.get("package_count", 1)),
            priority=payload.get("priority", Order.Priority.NORMAL),
            status=Order.Status.PENDING,
        )
        return _ok({"order": _serialize_order(order)}, status=201)
    except KeyError as exc:
        return _error(f"Falta el campo requerido: {exc.args[0]}")
    except Department.DoesNotExist:
        return _error("Origen o destino inválido.")
    except Exception as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["GET"])
def api_trips(request: HttpRequest):
    trips = (
        Trip.objects.select_related("vehicle", "driver", "origin", "destination")
        .prefetch_related("orders__origin", "orders__destination", "events")
        .all()
    )
    status_filter = request.GET.get("status")
    vehicle_filter = request.GET.get("vehicle_id")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if status_filter:
        trips = trips.filter(status=status_filter)
    if vehicle_filter:
        trips = trips.filter(vehicle_id=vehicle_filter)
    if date_from:
        trips = trips.filter(created_at__date__gte=date_from)
    if date_to:
        trips = trips.filter(created_at__date__lte=date_to)
    return _ok({"trips": [_serialize_trip(trip) for trip in trips]})


@login_required
@require_http_methods(["POST"])
def api_plan_trip(request: HttpRequest):
    perm_error = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.SUPERVISOR)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        vehicle = Vehicle.objects.get(pk=payload["vehicle_id"])
        order_ids = payload.get("order_ids", [])
        if not isinstance(order_ids, list):
            return _error("order_ids debe ser una lista de IDs.")

        driver = None
        driver_id = payload.get("driver_id")
        if driver_id:
            try:
                driver = Driver.objects.get(pk=driver_id, is_active=True)
            except Driver.DoesNotExist:
                return _error("Conductor inválido o inactivo.")

        orders = Order.objects.select_related("origin", "destination").filter(id__in=order_ids)
        if orders.count() != len(set(order_ids)):
            return _error("Uno o más pedidos no existen.")

        trip = TripPlanner.plan_trip(vehicle=vehicle, orders=orders, driver=driver)
        trip = (
            Trip.objects.select_related("vehicle", "driver", "origin", "destination")
            .prefetch_related("orders__origin", "orders__destination", "events")
            .get(pk=trip.pk)
        )
        return _ok({"trip": _serialize_trip(trip)}, status=201)
    except Vehicle.DoesNotExist:
        return _error("Vehículo inválido.")
    except PlanningError as exc:
        return _error(str(exc))
    except KeyError as exc:
        return _error(f"Falta el campo requerido: {exc.args[0]}")
    except Exception as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["POST"])
def api_trip_action(request: HttpRequest, trip_id: int):
    trip = get_object_or_404(
        Trip.objects.select_related("vehicle", "driver", "origin", "destination").prefetch_related(
            "orders__origin", "orders__destination", "events"
        ),
        pk=trip_id,
    )
    perm_error = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.SUPERVISOR)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        action = payload.get("action")
        if action == "start":
            TripLifecycleService.start_trip(trip)
        elif action == "complete":
            TripLifecycleService.complete_trip(trip)
        elif action == "cancel":
            TripLifecycleService.cancel_trip(trip)
        else:
            return _error("Acción inválida. Usa: start, complete o cancel.")

        trip.refresh_from_db()
        trip = (
            Trip.objects.select_related("vehicle", "driver", "origin", "destination")
            .prefetch_related("orders__origin", "orders__destination", "events")
            .get(pk=trip.pk)
        )
        return _ok({"trip": _serialize_trip(trip)})
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["POST"])
def api_trip_event(request: HttpRequest, trip_id: int):
    trip = get_object_or_404(Trip, pk=trip_id)
    try:
        payload = _parse_json(request)
        note = str(payload.get("note", ""))
        event = TripLifecycleService.add_event(trip, note)
        return _ok({"event": _serialize_event(event)}, status=201)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_GET
def api_dashboard(request: HttpRequest):
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    return _ok({"dashboard": _dashboard_payload(date_from=date_from, date_to=date_to)})


def method_not_allowed(_: HttpRequest):
    return HttpResponseNotAllowed(["GET", "POST"])
