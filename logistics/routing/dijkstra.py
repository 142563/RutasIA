"""Dijkstra: expande los nodos en orden de costo acumulado g(n).

Correcto porque todos los pesos son ≥ 0 (el tráfico multiplica por m ≥ 1).
Complejidad O((V + E) log V) con heap binario y "lazy deletion": un nodo puede
estar varias veces en el heap; las copias viejas se ignoran al sacarlas porque
el nodo ya está cerrado.
"""
from __future__ import annotations

import heapq
from time import perf_counter
from typing import Sequence

from logistics.routing.graph import RoadGraph
from logistics.routing.instrument import INF, SearchResult, ShortestPathTree, reconstruct


def _run(graph: RoadGraph, weights: Sequence[float], source: int, target: int | None, record_order: bool):
    n = graph.node_count
    dist = [INF] * n
    prev_edge = [-1] * n
    closed = [False] * n
    dist[source] = 0.0
    heap: list[tuple[float, int]] = [(0.0, source)]
    expanded, pushed = 0, 1
    order: list[int] | None = [] if record_order else None
    adj = graph.adj

    started = perf_counter()
    while heap:
        g, u = heapq.heappop(heap)
        if closed[u]:
            continue  # copia vieja en el heap
        closed[u] = True
        expanded += 1
        if order is not None:
            order.append(u)
        if u == target:
            break  # punto a punto: al SACAR el destino su costo ya es definitivo
        for v, e in adj[u]:
            if closed[v]:
                continue
            candidate = g + weights[e]
            if candidate < dist[v]:
                dist[v] = candidate
                prev_edge[v] = e
                heapq.heappush(heap, (candidate, v))
                pushed += 1
    elapsed_ms = (perf_counter() - started) * 1000
    return dist, prev_edge, expanded, pushed, elapsed_ms, order


def dijkstra(
    graph: RoadGraph, weights: Sequence[float], source: int, target: int, record_order: bool = False,
) -> SearchResult:
    """Punto a punto: se detiene al cerrar el destino."""
    dist, prev_edge, expanded, pushed, elapsed_ms, order = _run(graph, weights, source, target, record_order)
    path, edges = reconstruct(graph, prev_edge, source, target) if dist[target] < INF else ([], [])
    return SearchResult(
        algorithm="dijkstra", source=source, target=target, cost=dist[target], path=path, edges=edges,
        expanded=expanded, pushed=pushed, elapsed_ms=elapsed_ms, order=order,
    )


def dijkstra_all(graph: RoadGraph, weights: Sequence[float], source: int, record_order: bool = False) -> ShortestPathTree:
    """Uno a todos: una sola corrida da el costo desde `source` a TODOS los nodos."""
    dist, prev_edge, expanded, pushed, elapsed_ms, order = _run(graph, weights, source, None, record_order)
    return ShortestPathTree(
        source=source, dist=dist, prev_edge=prev_edge, expanded=expanded, pushed=pushed,
        elapsed_ms=elapsed_ms, order=order,
    )
