from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import heapq
import math

from django.core.cache import cache

from logistics.models import Department, RouteConnection
from logistics.domain.exceptions import PlanningError

ZERO = Decimal("0")
TWO_DP = Decimal("0.01")
INF = Decimal("Infinity")

_GRAPH_CACHE_KEY = "dijkstra_graph_v1"
_COORDS_CACHE_KEY = "dept_coords_v1"
_CACHE_TTL = 120  # segundos — se invalida si cambian las conexiones


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    """Straight-line distance between two GPS points (admissible A* heuristic)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return Decimal(str(2 * R * math.asin(math.sqrt(a)))).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def to_decimal(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _build_graph() -> dict[int, list[tuple[int, Decimal]]]:
    cached = cache.get(_GRAPH_CACHE_KEY)
    if cached is not None:
        return cached
    graph: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
    for conn in RouteConnection.objects.only("origin_id", "destination_id", "distance_km", "is_bidirectional"):
        d = Decimal(str(conn.distance_km))
        graph[conn.origin_id].append((conn.destination_id, d))
        if conn.is_bidirectional:
            graph[conn.destination_id].append((conn.origin_id, d))
    result = dict(graph)
    cache.set(_GRAPH_CACHE_KEY, result, _CACHE_TTL)
    return result


def _load_dept_coords() -> dict[int, Department]:
    cached = cache.get(_COORDS_CACHE_KEY)
    if cached is not None:
        return cached
    depts = {d.id: d for d in Department.objects.only("id", "latitude", "longitude")}
    cache.set(_COORDS_CACHE_KEY, depts, _CACHE_TTL)
    return depts


def invalidate_route_cache() -> None:
    """Llamar cuando se modifican RouteConnections o Departments."""
    cache.delete(_GRAPH_CACHE_KEY)
    cache.delete(_COORDS_CACHE_KEY)


def _reconstruct_path(previous: dict[int, int], origin_id: int, destination_id: int) -> list[int]:
    path: list[int] = []
    current = destination_id
    while current != origin_id:
        path.append(current)
        current = previous[current]
    path.append(origin_id)
    path.reverse()
    return path


class RouteOptimizer:
    """Dijkstra — explores nodes in order of cumulative road distance."""

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        if origin_id == destination_id:
            return [origin_id], ZERO

        graph = _build_graph()
        distances: dict[int, Decimal] = {origin_id: ZERO}
        previous: dict[int, int] = {}
        visited: set[int] = set()
        queue: list[tuple[Decimal, int]] = [(ZERO, origin_id)]

        while queue:
            g, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            if node == destination_id:
                break
            for neighbor, weight in graph.get(node, []):
                candidate = g + weight
                if candidate < distances.get(neighbor, INF):
                    distances[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (candidate, neighbor))

        if destination_id not in distances:
            raise PlanningError("No existe una ruta conectada entre origen y destino.")

        return _reconstruct_path(previous, origin_id, destination_id), to_decimal(distances[destination_id])


class AStarOptimizer:
    """A* — guides the search toward the destination using Haversine straight-line distance as heuristic."""

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        if origin_id == destination_id:
            return [origin_id], ZERO

        depts = _load_dept_coords()
        dest = depts.get(destination_id)

        def h(node_id: int) -> Decimal:
            if dest is None or dest.latitude is None or dest.longitude is None:
                return ZERO
            node = depts.get(node_id)
            if node is None or node.latitude is None or node.longitude is None:
                return ZERO
            return haversine_km(
                float(node.latitude), float(node.longitude),
                float(dest.latitude), float(dest.longitude),
            )

        graph = _build_graph()
        g_scores: dict[int, Decimal] = {origin_id: ZERO}
        previous: dict[int, int] = {}
        visited: set[int] = set()
        # queue: (f = g + h, g, node_id)
        queue: list[tuple[Decimal, Decimal, int]] = [(h(origin_id), ZERO, origin_id)]

        while queue:
            _f, g, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            if node == destination_id:
                break
            for neighbor, weight in graph.get(node, []):
                g_candidate = g + weight
                if g_candidate < g_scores.get(neighbor, INF):
                    g_scores[neighbor] = g_candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (g_candidate + h(neighbor), g_candidate, neighbor))

        if destination_id not in g_scores:
            raise PlanningError("No existe una ruta conectada entre origen y destino.")

        return _reconstruct_path(previous, origin_id, destination_id), to_decimal(g_scores[destination_id])
