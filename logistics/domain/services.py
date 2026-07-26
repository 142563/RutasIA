from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter
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


@dataclass(frozen=True)
class SearchResult:
    """Ruta encontrada más las métricas que exige el Objetivo Específico 1:
    distancia total, tiempo de procesamiento y esfuerzo de búsqueda."""

    path: list[int]
    distance: Decimal
    visited_order: list[int]  # nodos en el orden real en que se expandieron
    explored: int  # cuántos nodos se sacaron de la cola
    frontier_peak: int  # tamaño máximo que alcanzó la frontera
    elapsed_ms: float


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


def warm_route_cache() -> None:
    """Deja el grafo y las coordenadas en caché.

    Necesario antes de cronometrar algoritmos: la primera búsqueda paga la
    consulta a la base (~250 ms) y arrastraría ese costo al tiempo medido.
    """
    _build_graph()
    _load_dept_coords()


def _reconstruct_path(previous: dict[int, int], origin_id: int, destination_id: int) -> list[int]:
    path: list[int] = []
    current = destination_id
    while current != origin_id:
        path.append(current)
        current = previous[current]
    path.append(origin_id)
    path.reverse()
    return path


def _no_heuristic(_node_id: int) -> Decimal:
    """Heurística nula: convierte la búsqueda best-first en Dijkstra puro."""
    return ZERO


def _haversine_heuristic(destination_id: int):
    """Distancia en línea recta al destino. Es admisible (nunca sobreestima el
    costo real por carretera), que es lo que garantiza que A* siga siendo óptimo."""
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

    return h


def _best_first_search(origin_id: int, destination_id: int, heuristic) -> SearchResult:
    """Búsqueda best-first sobre el grafo vial.

    Con `_no_heuristic` es exactamente Dijkstra; con `_haversine_heuristic` es A*.
    Dijkstra y A* solo se diferencian en esa función, así que compartir el cuerpo
    evita que las métricas comparadas dependan de detalles de implementación
    distintos en cada uno.
    """
    started = perf_counter()

    if origin_id == destination_id:
        return SearchResult(
            path=[origin_id],
            distance=ZERO,
            visited_order=[origin_id],
            explored=1,
            frontier_peak=1,
            elapsed_ms=(perf_counter() - started) * 1000,
        )

    graph = _build_graph()
    g_scores: dict[int, Decimal] = {origin_id: ZERO}
    previous: dict[int, int] = {}
    visited: set[int] = set()
    visited_order: list[int] = []
    # cola: (f = g + h, g, node_id)
    queue: list[tuple[Decimal, Decimal, int]] = [(heuristic(origin_id), ZERO, origin_id)]
    frontier_peak = 1

    while queue:
        _f, g, node = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        visited_order.append(node)
        if node == destination_id:
            break
        for neighbor, weight in graph.get(node, []):
            g_candidate = g + weight
            if g_candidate < g_scores.get(neighbor, INF):
                g_scores[neighbor] = g_candidate
                previous[neighbor] = node
                heapq.heappush(queue, (g_candidate + heuristic(neighbor), g_candidate, neighbor))
                frontier_peak = max(frontier_peak, len(queue))

    if destination_id not in g_scores:
        raise PlanningError("No existe una ruta conectada entre origen y destino.")

    return SearchResult(
        path=_reconstruct_path(previous, origin_id, destination_id),
        distance=to_decimal(g_scores[destination_id]),
        visited_order=visited_order,
        explored=len(visited_order),
        frontier_peak=frontier_peak,
        elapsed_ms=(perf_counter() - started) * 1000,
    )


class RouteOptimizer:
    """Dijkstra — explores nodes in order of cumulative road distance."""

    key = "dijkstra"
    label = "Dijkstra"

    @classmethod
    def search(cls, origin_id: int, destination_id: int) -> SearchResult:
        return _best_first_search(origin_id, destination_id, _no_heuristic)

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        result = cls.search(origin_id, destination_id)
        return result.path, result.distance


class AStarOptimizer:
    """A* — guides the search toward the destination using Haversine straight-line distance as heuristic."""

    key = "astar"
    label = "A* (A-estrella)"

    @classmethod
    def search(cls, origin_id: int, destination_id: int) -> SearchResult:
        return _best_first_search(origin_id, destination_id, _haversine_heuristic(destination_id))

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        result = cls.search(origin_id, destination_id)
        return result.path, result.distance


class GreedyOptimizer:
    """Línea base que aproxima la planificación manual.

    En cada cruce avanza al vecino todavía no visitado que quede más cerca del
    destino en línea recta, sin considerar el costo ya acumulado ni el que falta:
    es la regla de "siempre encarar hacia allá" con la que se planifica a ojo.
    Si entra en un callejón sin salida retrocede al cruce anterior.

    No pretende reproducir la ruta que usa una empresa concreta — es una
    heurística voraz documentada que sirve de referencia contra la cual medir el
    porcentaje de reducción. A diferencia de Dijkstra y A*, no garantiza
    optimalidad, y sobre grafos poco densos a menudo coincide con la ruta óptima.
    """

    key = "greedy"
    label = "Planificación convencional"

    @classmethod
    def search(cls, origin_id: int, destination_id: int) -> SearchResult:
        started = perf_counter()

        if origin_id == destination_id:
            return SearchResult(
                path=[origin_id],
                distance=ZERO,
                visited_order=[origin_id],
                explored=1,
                frontier_peak=1,
                elapsed_ms=(perf_counter() - started) * 1000,
            )

        graph = _build_graph()
        h = _haversine_heuristic(destination_id)

        path: list[int] = [origin_id]
        step_costs: list[Decimal] = []
        visited: set[int] = {origin_id}
        visited_order: list[int] = [origin_id]
        distance = ZERO
        frontier_peak = 1

        while path[-1] != destination_id:
            current = path[-1]
            options = sorted(
                (
                    (h(neighbor), weight, neighbor)
                    for neighbor, weight in graph.get(current, [])
                    if neighbor not in visited
                ),
                key=lambda option: (option[0], option[1], option[2]),
            )
            frontier_peak = max(frontier_peak, len(options))

            if not options:
                # Callejón sin salida: deshace el último tramo y sigue por otra rama.
                # `visited` nunca se limpia, así que la búsqueda siempre termina.
                if len(path) == 1:
                    raise PlanningError("No existe una ruta conectada entre origen y destino.")
                path.pop()
                distance -= step_costs.pop()
                continue

            _estimate, weight, chosen = options[0]
            visited.add(chosen)
            visited_order.append(chosen)
            path.append(chosen)
            step_costs.append(weight)
            distance += weight

        return SearchResult(
            path=path,
            distance=to_decimal(distance),
            visited_order=visited_order,
            explored=len(visited_order),
            frontier_peak=frontier_peak,
            elapsed_ms=(perf_counter() - started) * 1000,
        )

    @classmethod
    def shortest_path(cls, origin_id: int, destination_id: int) -> tuple[list[int], Decimal]:
        result = cls.search(origin_id, destination_id)
        return result.path, result.distance


# Orden en que se presentan en el Laboratorio: la línea base primero.
OPTIMIZERS = (GreedyOptimizer, RouteOptimizer, AStarOptimizer)
OPTIMIZERS_BY_KEY = {optimizer.key: optimizer for optimizer in OPTIMIZERS}
