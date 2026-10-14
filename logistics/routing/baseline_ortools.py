"""Línea base con Google OR-Tools para comparar el algoritmo genético (tesis, Cap. III).

Solo se usa en el experimento (run_thesis_experiment), NUNCA en el motor ni en la
API: OR-Tools está en requirements-dev.txt y Render no lo instala. Resuelve el
mismo problema que el genético (orden de visita sobre la MISMA matriz asimétrica
de minutos) con RoutingModel: PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence

SCALE = 1000  # OR-Tools trabaja con enteros: minutos × 1000


class OrToolsUnavailable(RuntimeError):
    pass


@dataclass
class BaselineResult:
    order: list[int]  # índices 1..k de la matriz, en orden de visita
    cost: float  # recalculado con la matriz original (sin redondeo)
    ms: float
    status: str


def solve(matrix: Sequence[Sequence[float]], return_to_depot: bool = False,
          time_limit_s: int = 10) -> BaselineResult:
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise OrToolsUnavailable("Instala requirements-dev.txt para usar la línea base de OR-Tools.") from exc

    started = time.perf_counter()
    n = len(matrix)
    if n <= 2:
        order = list(range(1, n))
        return BaselineResult(order, _cost(order, matrix, return_to_depot), 0.0, "trivial")

    # Sin regreso: se agrega un nodo ficticio de llegada con costo 0 desde cualquier parada
    size = n if return_to_depot else n + 1
    end = 0 if return_to_depot else n

    def arc(i: int, j: int) -> int:
        if not return_to_depot:
            if j == end:
                return 0  # llegar al nodo ficticio no cuesta: la ruta termina en la última parada
            if i == end:
                return 10 ** 9  # nunca se sale del nodo ficticio
        return int(round(matrix[i][j] * SCALE))

    manager = pywrapcp.RoutingIndexManager(size, 1, [0], [end])
    routing = pywrapcp.RoutingModel(manager)
    callback = routing.RegisterTransitCallback(
        lambda a, b: arc(manager.IndexToNode(a), manager.IndexToNode(b)))
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds = time_limit_s
    solution = routing.SolveWithParameters(search)
    if solution is None:
        raise RuntimeError("OR-Tools no encontró solución.")

    order, index = [], routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node not in (0, end):
            order.append(node)
        index = solution.Value(routing.NextVar(index))
    return BaselineResult(order, _cost(order, matrix, return_to_depot), (time.perf_counter() - started) * 1000,
                          "ok")


def _cost(order: Sequence[int], matrix: Sequence[Sequence[float]], return_to_depot: bool) -> float:
    total, current = 0.0, 0
    for stop in order:
        total += matrix[current][stop]
        current = stop
    if return_to_depot:
        total += matrix[current][0]
    return total
