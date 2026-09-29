"""Incidentes sobre el grafo: penalizaciones y bloqueos de aristas (docs/PLAN.md §8, flujo C).

Motor puro: sin BD ni Django. Los pesos base (minutos con tráfico) salen de
`RoadGraph.weights` y están cacheados en el grafo; aquí NUNCA se mutan. Se
construye una lista NUEVA donde cada arista afectada vale  w × m  (m ≥ 1) o
infinito si está bloqueada.

Por qué A* sigue siendo exacto con incidentes
---------------------------------------------
Los incidentes solo SUBEN pesos (m ≥ 1) o los dejan en infinito, nunca los bajan.
Con v_max calculado sobre los pesos SIN incidentes, para toda arista
    haversine(u, v) / v_max  ≤  w_base(e)  ≤  w_incidente(e)
así que h sigue siendo consistente (y admisible) con los pesos nuevos, y
costo(A*) == costo(Dijkstra). Lo que NO se debe hacer es recalcular v_max sobre
los pesos penalizados: si se penaliza la arista más "veloz", v_max baja, h sube
y puede sobreestimar. `search_with_penalties` fija v_max con los pesos base.

Las aristas de costo infinito no se recorren: en Dijkstra y A*, `g + inf` nunca
es menor que la distancia actual (infinito), así que el nodo no se alcanza por
ahí y, si no hay otro camino, la búsqueda termina con `found == False`.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

from logistics.routing.astar import astar, compute_v_max
from logistics.routing.graph import RoadGraph
from logistics.routing.instrument import SearchResult

BLOCKED = math.inf  # multiplicador de una arista bloqueada


def validate_multiplier(multiplier: float) -> float:
    """m debe ser un número ≥ 1 (o BLOCKED). Nunca se resta tiempo."""
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or math.isnan(multiplier):
        raise ValueError("El multiplicador debe ser un número.")
    if multiplier < 1.0:
        raise ValueError("El multiplicador debe ser ≥ 1: un incidente nunca reduce el tiempo.")
    return float(multiplier)


def combine_penalties(items: Iterable[tuple[int, float]]) -> dict[int, float]:
    """Une penalizaciones (índice de arista, multiplicador): sobre la misma arista se
    MULTIPLICAN y un bloqueo (BLOCKED) gana sobre cualquier multiplicador."""
    combined: dict[int, float] = {}
    for edge_idx, multiplier in items:
        multiplier = validate_multiplier(multiplier)
        current = combined.get(edge_idx, 1.0)
        combined[edge_idx] = BLOCKED if BLOCKED in (current, multiplier) else current * multiplier
    return combined


def apply_penalties(weights: Sequence[float], penalties: Mapping[int, float]) -> list[float]:
    """Pesos nuevos: w × m, o infinito si la arista está bloqueada.

    Devuelve una lista NUEVA (los pesos cacheados del grafo no se tocan) y
    garantiza que ningún peso baja.
    """
    result = list(weights)
    for edge_idx, multiplier in penalties.items():
        multiplier = validate_multiplier(multiplier)
        if not 0 <= edge_idx < len(result):
            raise IndexError(f"La arista {edge_idx} no existe en el grafo.")
        # w = 0 con m = inf daría nan: un tramo bloqueado es infinito sin importar w.
        result[edge_idx] = math.inf if multiplier == BLOCKED else result[edge_idx] * multiplier
    return result


def search_with_penalties(
    graph: RoadGraph,
    base_weights: Sequence[float],
    penalties: Mapping[int, float],
    source: int,
    target: int,
    record_order: bool = False,
) -> SearchResult:
    """A* sobre los pesos con incidentes, con v_max derivado de los pesos SIN incidentes.

    Es una función pura sobre listas ya en memoria: no consulta BD ni Google.
    """
    weights = apply_penalties(base_weights, penalties) if penalties else list(base_weights)
    return astar(graph, weights, source, target, v_max=compute_v_max(graph, base_weights), record_order=record_order)
