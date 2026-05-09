from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from django.conf import settings as django_settings

from logistics.models import Department, Driver, FuelPrice, Order, RouteConnection, Trip, UserProfile, Vehicle
from logistics.domain.exceptions import PlanningError
from logistics.application.services import TripLifecycleService, TripPlanner
from logistics.presentation.serializers import (
    _as_float,
    _dashboard_payload,
    _error,
    _get_role,
    _ok,
    _parse_json,
    _require_role,
    _serialize_driver,
    _serialize_event,
    _serialize_order,
    _serialize_trip,
    _serialize_vehicle,
    _serialize_department,
)


@ensure_csrf_cookie
@login_required
@require_GET
def index(request: HttpRequest):
    return render(request, "logistics/index.html", {
        "ors_api_key": getattr(django_settings, "ORS_API_KEY", ""),
    })


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
@require_GET
def api_dashboard(request: HttpRequest):
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    return _ok({"dashboard": _dashboard_payload(date_from=date_from, date_to=date_to)})


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

        algorithm = payload.get("algorithm", "dijkstra")
        if algorithm not in ("dijkstra", "astar"):
            return _error("Algoritmo inválido. Use 'dijkstra' o 'astar'.")

        trip = TripPlanner.plan_trip(vehicle=vehicle, orders=orders, driver=driver, algorithm=algorithm)
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
@require_http_methods(["GET", "POST"])
def api_fuel_price(request: HttpRequest):
    fp = FuelPrice.current()

    if request.method == "GET":
        return _ok({
            "fuel_price": {
                "regular_gtq_l": _as_float(fp.regular_gtq_l),
                "super_gtq_l": _as_float(fp.super_gtq_l),
                "diesel_gtq_l": _as_float(fp.diesel_gtq_l),
                "source": fp.source,
                "updated_at": timezone.localtime(fp.updated_at).isoformat(),
            }
        })

    perm_error = _require_role(request, UserProfile.Role.ADMIN)
    if perm_error:
        return perm_error

    try:
        payload = _parse_json(request)
        fp.regular_gtq_l = Decimal(str(payload["regular_gtq_l"]))
        fp.super_gtq_l = Decimal(str(payload["super_gtq_l"]))
        fp.diesel_gtq_l = Decimal(str(payload["diesel_gtq_l"]))
        fp.source = str(payload.get("source", "Manual"))
        fp.save()
        return _ok({
            "fuel_price": {
                "regular_gtq_l": _as_float(fp.regular_gtq_l),
                "super_gtq_l": _as_float(fp.super_gtq_l),
                "diesel_gtq_l": _as_float(fp.diesel_gtq_l),
                "source": fp.source,
                "updated_at": timezone.localtime(fp.updated_at).isoformat(),
            }
        })
    except (KeyError, ValueError) as exc:
        return _error(f"Datos inválidos: {exc}")


def method_not_allowed(_: HttpRequest):
    return HttpResponseNotAllowed(["GET", "POST"])
