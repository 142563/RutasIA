from __future__ import annotations

import json
from decimal import Decimal

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from logistics.models import Department, Driver, Order, Trip, TripEvent, UserProfile, Vehicle
from logistics.domain.exceptions import PlanningError


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
        "fuel_price_gtq_l": _as_float(trip.fuel_price_gtq_l) if trip.fuel_price_gtq_l else None,
        "estimated_fuel_cost_gtq": _as_float(trip.estimated_fuel_cost_gtq) if trip.estimated_fuel_cost_gtq else None,
        "estimated_cost": _as_float(trip.estimated_cost),
        "status": trip.status,
        "started_at": trip.started_at.isoformat() if trip.started_at else None,
        "completed_at": trip.completed_at.isoformat() if trip.completed_at else None,
        "orders": [_serialize_order(order) for order in trip.orders.all().order_by("-created_at")],
        "events": [_serialize_event(event) for event in trip.events.all()],
    }


def _dashboard_payload(date_from=None, date_to=None) -> dict:
    from django.db.models import Count, Sum
    from django.utils import timezone as tz
    from datetime import timedelta

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

    today = tz.localdate()
    timeline = []
    for delta in range(6, -1, -1):
        day = today - timedelta(days=delta)
        timeline.append(
            {
                "date": day.isoformat(),
                "trips": trips.filter(created_at__date=day).count(),
            }
        )

    from logistics.models import Order as _Order
    return {
        "summary": {
            "total_trips": aggregates["total_trips"] or 0,
            "active_trips": trips.filter(status__in=[Trip.Status.PLANNED, Trip.Status.IN_PROGRESS]).count(),
            "pending_orders": _Order.objects.filter(status=_Order.Status.PENDING).count(),
            "delivered_orders": _Order.objects.filter(status=_Order.Status.DELIVERED).count(),
            "total_cost": _as_float(aggregates["total_cost"]),
            "total_distance_km": _as_float(aggregates["total_distance"]),
        },
        "status_distribution": status_distribution,
        "vehicle_activity": vehicle_activity,
        "timeline": timeline,
    }
