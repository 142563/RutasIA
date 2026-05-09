from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from logistics.models import Department, Driver, FuelPrice, Order, Trip, TripEvent, TripOrder, Vehicle
from logistics.domain.exceptions import PlanningError
from logistics.domain.services import AStarOptimizer, RouteOptimizer, to_decimal, ZERO

LITERS_PER_GALLON = Decimal("3.78541")


class TripPlanner:
    @staticmethod
    def _validate_orders(orders: Iterable[Order]) -> list[Order]:
        order_list = list(orders)
        if not order_list:
            raise PlanningError("Debes seleccionar al menos un pedido.")

        pending_only = [o for o in order_list if o.status == Order.Status.PENDING]
        if len(pending_only) != len(order_list):
            raise PlanningError("Todos los pedidos deben estar en estado pendiente.")

        first = order_list[0]
        same_route = all(
            o.origin_id == first.origin_id and o.destination_id == first.destination_id for o in order_list
        )
        if not same_route:
            raise PlanningError("Para esta versión, los pedidos deben compartir mismo origen y destino.")

        return order_list

    @classmethod
    @transaction.atomic
    def plan_trip(
        cls,
        vehicle: Vehicle,
        orders: QuerySet[Order],
        driver: Driver | None = None,
        algorithm: str = "dijkstra",
    ) -> Trip:
        if not vehicle.is_active:
            raise PlanningError("El vehículo seleccionado está inactivo.")

        order_list = cls._validate_orders(orders)
        total_weight = sum(Decimal(o.weight_kg) for o in order_list)
        if total_weight > Decimal(vehicle.capacity_kg):
            raise PlanningError(
                f"La carga total ({to_decimal(total_weight)} kg) excede la capacidad del vehículo."
            )

        if Decimal(vehicle.fuel_efficiency_km_l) <= ZERO:
            raise PlanningError("La eficiencia del vehículo debe ser mayor a 0.")

        origin = order_list[0].origin
        destination = order_list[0].destination

        optimizer = AStarOptimizer if algorithm == "astar" else RouteOptimizer
        node_ids, distance = optimizer.shortest_path(origin.id, destination.id)

        fuel_liters = to_decimal(distance / Decimal(vehicle.fuel_efficiency_km_l))
        fuel_gallons = to_decimal(fuel_liters / LITERS_PER_GALLON)
        estimated_cost = to_decimal(distance * Decimal(vehicle.cost_per_km))

        fp = FuelPrice.current()
        fuel_price_gtq_gal = to_decimal(fp.regular_gtq_gal)
        estimated_fuel_cost_gtq = to_decimal(fuel_gallons * fuel_price_gtq_gal)

        node_name_lookup = Department.objects.in_bulk(node_ids)
        route_nodes = [node_name_lookup[node_id].name for node_id in node_ids]

        trip = Trip.objects.create(
            vehicle=vehicle,
            driver=driver,
            origin=origin,
            destination=destination,
            route_nodes=route_nodes,
            total_distance_km=distance,
            estimated_fuel_gallons=fuel_gallons,
            fuel_price_gtq_gal=fuel_price_gtq_gal,
            estimated_fuel_cost_gtq=estimated_fuel_cost_gtq,
            estimated_cost=estimated_cost,
            status=Trip.Status.PLANNED,
        )

        TripOrder.objects.bulk_create([TripOrder(trip=trip, order=order) for order in order_list])
        Order.objects.filter(id__in=[o.id for o in order_list]).update(status=Order.Status.ASSIGNED)
        algo_label = "A* (A-estrella)" if algorithm == "astar" else "Dijkstra"
        TripEvent.objects.create(
            trip=trip,
            note=f"Viaje planificado con {len(order_list)} pedido(s) usando {algo_label}. Ruta: {' -> '.join(route_nodes)}.",
        )
        return trip


class TripLifecycleService:
    @staticmethod
    @transaction.atomic
    def start_trip(trip: Trip) -> Trip:
        if trip.status != Trip.Status.PLANNED:
            raise PlanningError("Solo se puede iniciar un viaje planificado.")
        trip.status = Trip.Status.IN_PROGRESS
        trip.started_at = timezone.now()
        trip.save(update_fields=["status", "started_at", "updated_at"])
        trip.orders.update(status=Order.Status.IN_TRANSIT)
        TripEvent.objects.create(trip=trip, note="Viaje iniciado.")
        return trip

    @staticmethod
    @transaction.atomic
    def complete_trip(trip: Trip) -> Trip:
        if trip.status not in {Trip.Status.IN_PROGRESS, Trip.Status.PLANNED}:
            raise PlanningError("Solo se puede completar un viaje planificado o en progreso.")
        trip.status = Trip.Status.COMPLETED
        if trip.started_at is None:
            trip.started_at = timezone.now()
        trip.completed_at = timezone.now()
        trip.save(update_fields=["status", "started_at", "completed_at", "updated_at"])
        trip.orders.update(status=Order.Status.DELIVERED)
        TripEvent.objects.create(trip=trip, note="Viaje completado y pedidos marcados como entregados.")
        return trip

    @staticmethod
    @transaction.atomic
    def cancel_trip(trip: Trip) -> Trip:
        if trip.status == Trip.Status.COMPLETED:
            raise PlanningError("No se puede cancelar un viaje ya completado.")
        trip.status = Trip.Status.CANCELED
        trip.save(update_fields=["status", "updated_at"])
        trip.orders.exclude(status=Order.Status.DELIVERED).update(status=Order.Status.PENDING)
        TripEvent.objects.create(trip=trip, note="Viaje cancelado.")
        return trip

    @staticmethod
    def add_event(trip: Trip, note: str) -> TripEvent:
        if not note.strip():
            raise PlanningError("El evento no puede estar vacío.")
        return TripEvent.objects.create(trip=trip, note=note.strip())
