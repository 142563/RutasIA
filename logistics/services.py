from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import heapq
from typing import Iterable

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import Department, Driver, Order, RouteConnection, Trip, TripEvent, TripOrder, Vehicle

ZERO = Decimal("0")
TWO_DP = Decimal("0.01")


class PlanningError(Exception):
    pass


def to_decimal(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


class RouteOptimizer:
    @staticmethod
    def _build_graph() -> dict[int, list[tuple[int, Decimal]]]:
        graph: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
        qs = RouteConnection.objects.select_related("origin", "destination")
        for connection in qs:
            distance = Decimal(connection.distance_km)
            graph[connection.origin_id].append((connection.destination_id, distance))
            if connection.is_bidirectional:
                graph[connection.destination_id].append((connection.origin_id, distance))
        return graph

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        if origin_id == destination_id:
            return [origin_id], ZERO

        graph = cls._build_graph()
        queue: list[tuple[Decimal, int]] = [(ZERO, origin_id)]
        distances: dict[int, Decimal] = {origin_id: ZERO}
        previous: dict[int, int] = {}
        visited: set[int] = set()

        while queue:
            current_distance, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)

            if node == destination_id:
                break

            for neighbor, weight in graph.get(node, []):
                candidate = current_distance + weight
                if candidate < distances.get(neighbor, Decimal("Infinity")):
                    distances[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (candidate, neighbor))

        if destination_id not in distances:
            raise PlanningError("No existe una ruta conectada entre origen y destino.")

        path: list[int] = []
        current = destination_id
        while current != origin_id:
            path.append(current)
            current = previous[current]
        path.append(origin_id)
        path.reverse()
        return path, to_decimal(distances[destination_id])


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
    def plan_trip(cls, vehicle: Vehicle, orders: QuerySet[Order], driver: Driver | None = None) -> Trip:
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
        node_ids, distance = RouteOptimizer.shortest_path(origin.id, destination.id)

        fuel_liters = to_decimal(distance / Decimal(vehicle.fuel_efficiency_km_l))
        estimated_cost = to_decimal(distance * Decimal(vehicle.cost_per_km))
        node_name_lookup = Department.objects.in_bulk(node_ids)
        route_nodes = [node_name_lookup[node_id].name for node_id in node_ids]

        trip = Trip.objects.create(
            vehicle=vehicle,
            driver=driver,
            origin=origin,
            destination=destination,
            route_nodes=route_nodes,
            total_distance_km=distance,
            estimated_fuel_liters=fuel_liters,
            estimated_cost=estimated_cost,
            status=Trip.Status.PLANNED,
        )

        TripOrder.objects.bulk_create([TripOrder(trip=trip, order=order) for order in order_list])
        Order.objects.filter(id__in=[o.id for o in order_list]).update(status=Order.Status.ASSIGNED)
        TripEvent.objects.create(
            trip=trip,
            note=f"Viaje planificado con {len(order_list)} pedido(s). Ruta: {' -> '.join(route_nodes)}.",
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
