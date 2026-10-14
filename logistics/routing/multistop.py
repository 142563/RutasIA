"""Varias paradas (docs/PLAN.md §2.7).

1. Matriz de tiempos con Dijkstra uno-a-todos desde la bodega y desde cada
   parada: N+1 corridas en vez de N² búsquedas punto a punto.
2. Orden de visita con el algoritmo genético (genetic.py, motor principal de la
   tesis), sembrado con vecino más cercano + 2-opt; "nn2opt" queda como opción.
3. Cada tramo con A*, usando la franja en la que EMPIEZA el tramo: la llegada a
   una parada (más el tiempo de servicio) es la salida del tramo siguiente.

Con criterio de tiempo, la aptitud del genético es dependiente del tiempo
(TimeDependentCost): cada tramo cuesta lo que marca la franja en la que empieza,
igual que al trazarlo con A*, así que el tiempo que estima coincide con el de la
ruta trazada. La matriz de la franja de salida guía al 2-opt.
La matriz NO es simétrica (grafo dirigido), por eso 2-opt evalúa el costo
completo de cada candidato en vez de la fórmula de intercambio simétrica.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import perf_counter
from typing import Sequence

from logistics.routing import genetic
from logistics.routing.astar import astar
from logistics.routing.dijkstra import dijkstra_all
from logistics.routing.graph import DISTANCE, TIME, RoadGraph
from logistics.routing.instrument import INF, SearchResult
from logistics.routing.traffic import profile_for, to_local

DEFAULT_SERVICE_MIN = 10.0
GENETIC, NN2OPT, FIXED = "genetic", "nn2opt", "fixed"
OPTIMIZERS = (GENETIC, NN2OPT)


class UnreachableStopError(Exception):
    def __init__(self, node: int):
        super().__init__(node)
        self.node = node


def time_matrix(graph: RoadGraph, weights: Sequence[float], nodes: Sequence[int]) -> tuple[list[list[float]], int]:
    """matrix[i][j] = costo de nodes[i] a nodes[j]. Devuelve también los nodos expandidos en total."""
    matrix, expanded = [], 0
    for source in nodes:
        tree = dijkstra_all(graph, weights, source)
        expanded += tree.expanded
        matrix.append([tree.dist[t] for t in nodes])
    return matrix, expanded


def route_cost(order: Sequence[int], matrix: list[list[float]], return_to_depot: bool = False) -> float:
    """Costo de salir de la bodega (índice 0) y visitar `order` (índices 1..k)."""
    total, current = 0.0, 0
    for stop in order:
        total += matrix[current][stop]
        current = stop
    if return_to_depot:
        total += matrix[current][0]
    return total


def nearest_neighbor(matrix: list[list[float]]) -> list[int]:
    """Desde la bodega, siempre a la parada pendiente más cercana en tiempo."""
    pending = set(range(1, len(matrix)))
    order, current = [], 0
    while pending:
        nxt = min(pending, key=lambda j: (matrix[current][j], j))
        order.append(nxt)
        pending.remove(nxt)
        current = nxt
    return order


def two_opt(order: Sequence[int], matrix: list[list[float]], return_to_depot: bool = False) -> list[int]:
    """Invierte tramos del recorrido mientras baje el tiempo total (búsqueda local).

    Nunca empeora el orden recibido. No garantiza el óptimo global: el problema
    de ordenar las paradas es NP-difícil; por eso E5 mide cuánto mejora.
    """
    best = list(order)
    best_cost = route_cost(best, matrix, return_to_depot)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                cost = route_cost(candidate, matrix, return_to_depot)
                if cost < best_cost - 1e-9:
                    best, best_cost, improved = candidate, cost, True
    return best


class TimeDependentCost:
    """Minutos de manejo de un orden, con cada tramo en la franja en la que EMPIEZA.

    Reproduce el cálculo de los tramos de plan_multistop (llegada + servicio = salida
    del siguiente) usando matrices de Dijkstra por perfil (franja, tipo de día),
    calculadas solo cuando se necesitan. Las franjas cambian en horas exactas.
    """

    def __init__(self, graph: RoadGraph, nodes: Sequence[int], departure: datetime, service_min: float,
                 return_to_depot: bool, avoid_unpaved: bool = False,
                 known: dict[tuple[str, str], list[list[float]]] | None = None):
        self.graph, self.nodes, self.service = graph, list(nodes), service_min
        self.return_to_depot, self.avoid_unpaved = return_to_depot, avoid_unpaved
        self.hour0 = departure.replace(minute=0, second=0, microsecond=0)
        self.start = (departure - self.hour0).total_seconds() / 60  # minutos desde el inicio de esa hora
        self.matrices: dict[tuple[str, str], list[list[float]]] = dict(known or {})
        self.by_hour: dict[int, list[list[float]]] = {}
        self.expanded = 0

    def _matrix(self, clock: float) -> list[list[float]]:
        hour = int(clock // 60)
        matrix = self.by_hour.get(hour)
        if matrix is None:
            profile = profile_for(self.hour0 + timedelta(hours=hour))
            matrix = self.matrices.get(profile)
            if matrix is None:
                weights = self.graph.search_weights(TIME, *profile, self.avoid_unpaved)
                matrix, expanded = time_matrix(self.graph, weights, self.nodes)
                self.matrices[profile] = matrix
                self.expanded += expanded
            self.by_hour[hour] = matrix
        return matrix

    def __call__(self, order: Sequence[int]) -> float:
        total, clock, current = 0.0, self.start, 0
        for stop in order:
            minutes = self._matrix(clock)[current][stop]
            total += minutes
            clock += minutes + self.service
            current = stop
        if self.return_to_depot:
            total += self._matrix(clock)[current][0]
        return total


@dataclass
class Leg:
    origin: int
    destination: int
    depart_at: datetime
    arrive_at: datetime
    band: str
    day_type: str
    search: SearchResult
    km: float
    minutes: float  # SIEMPRE minutos con el tráfico de la franja del tramo, sea cual sea el criterio


@dataclass
class MultiStopPlan:
    depot: int
    stops: list[int]  # nodos de las paradas, en el orden recibido
    order: list[int]  # índices (0..k-1) de `stops` en el orden de visita
    legs: list[Leg]
    departure: datetime
    service_min: float
    return_to_depot: bool
    matrix_expanded: int
    # Costo de cada orden para comparar métodos (km, o minutos con la franja de cada tramo):
    capture_minutes: float  # orden tal como se capturaron las paradas
    nearest_neighbor_minutes: float
    optimized_minutes: float  # orden elegido por el optimizador (con la matriz de la franja de salida)
    criterion: str = TIME
    optimizer: str = GENETIC  # genetic | nn2opt | fixed (orden dado)
    two_opt_minutes: float = 0.0  # vecino más cercano + 2-opt, para comparar con el genético
    ga_generations: int = 0
    optimize_ms: float = 0.0  # tiempo real que tomó ordenar las paradas
    etas: list[datetime] = field(default_factory=list)  # llegada a cada parada, en orden de visita

    @property
    def driving_minutes(self) -> float:
        return sum(leg.minutes for leg in self.legs)

    @property
    def total_km(self) -> float:
        return sum(leg.km for leg in self.legs)

    @property
    def expanded(self) -> int:
        """Nodos expandidos en total: matriz (Dijkstra) + tramos (A*)."""
        return self.matrix_expanded + sum(leg.search.expanded for leg in self.legs)

    @property
    def finish_at(self) -> datetime:
        return self.legs[-1].arrive_at if self.legs else self.departure


def plan_multistop(
    graph: RoadGraph,
    depot: int,
    stops: Sequence[int],
    departure: datetime,
    service_min: float = DEFAULT_SERVICE_MIN,
    return_to_depot: bool = False,
    criterion: str = TIME,
    fixed_order: Sequence[int] | None = None,
    avoid_unpaved: bool = False,
    optimizer: str = GENETIC,
    ga_params: genetic.GeneticParams | None = None,
) -> MultiStopPlan:
    """criterion="time": la más rápida con tráfico; "distance": la más corta en km.

    En ambos casos las ETAs y los minutos se calculan con el tráfico de cada
    tramo, así "la más corta" se compara con la más rápida en igualdad de condiciones.

    fixed_order (índices 0..k-1 de `stops`) evalúa un orden dado en vez de optimizarlo.
    optimizer: "genetic" (por defecto) o "nn2opt" (vecino más cercano + 2-opt).
    """
    if optimizer not in OPTIMIZERS:
        raise ValueError(f"optimizer debe ser uno de {OPTIMIZERS}")
    departure = to_local(departure)
    band, day_type = profile_for(departure)
    weights = graph.search_weights(criterion, band, day_type, avoid_unpaved)
    nodes = [depot, *stops]

    matrix, matrix_expanded = time_matrix(graph, weights, nodes)
    for j, node in enumerate(nodes):
        if matrix[0][j] == INF:
            raise UnreachableStopError(node)

    capture = list(range(1, len(nodes)))
    nn = nearest_neighbor(matrix)
    started = perf_counter()
    nn_two_opt = two_opt(nn, matrix, return_to_depot)
    generations = 0
    if criterion == TIME:
        cost = TimeDependentCost(graph, nodes, departure, service_min, return_to_depot, avoid_unpaved,
                                 known={(band, day_type): matrix})
    else:
        cost = lambda order: route_cost(order, matrix, return_to_depot)  # noqa: E731  (km: no depende de la hora)
    if fixed_order is not None:
        if sorted(fixed_order) != list(range(len(stops))):
            raise ValueError("fixed_order debe ser una permutación de las paradas")
        optimized, optimizer = [i + 1 for i in fixed_order], FIXED
    elif optimizer == GENETIC:
        result = genetic.solve(matrix, ga_params, return_to_depot, seeds=[nn_two_opt, nn, capture], fitness=cost)
        optimized, generations = result.order, result.generations
    else:
        optimized = nn_two_opt
    optimize_ms = (perf_counter() - started) * 1000

    legs, etas = [], []
    current_time, current_node = departure, depot
    sequence = [nodes[i] for i in optimized] + ([depot] if return_to_depot else [])
    for position, target in enumerate(sequence):
        leg_band, leg_day = profile_for(current_time)
        time_weights = graph.weights(TIME, leg_band, leg_day)
        search_weights = graph.search_weights(criterion, leg_band, leg_day, avoid_unpaved)
        result = astar(graph, search_weights, current_node, target)
        if not result.found:
            raise UnreachableStopError(target)
        minutes = result.total(time_weights)
        arrive = current_time + timedelta(minutes=minutes)
        legs.append(Leg(current_node, target, current_time, arrive, leg_band, leg_day, result,
                        result.total(graph.km), minutes))
        is_stop = position < len(optimized)
        if is_stop:
            etas.append(arrive)
        current_time = arrive + timedelta(minutes=service_min if is_stop else 0)
        current_node = target

    return MultiStopPlan(
        depot=depot,
        stops=list(stops),
        order=[i - 1 for i in optimized],
        legs=legs,
        departure=departure,
        service_min=service_min,
        return_to_depot=return_to_depot,
        matrix_expanded=matrix_expanded + getattr(cost, "expanded", 0),
        capture_minutes=cost(capture),
        nearest_neighbor_minutes=cost(nn),
        optimized_minutes=cost(optimized),
        criterion=criterion,
        optimizer=optimizer,
        two_opt_minutes=cost(nn_two_opt),
        ga_generations=generations,
        optimize_ms=optimize_ms,
        etas=etas,
    )
