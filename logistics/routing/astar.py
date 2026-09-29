"""A*: búsqueda guiada por f(n) = g(n) + h(n).

Heurística en la MISMA unidad que el costo:  h(n) = haversine(n, destino) / v_max

v_max = max sobre las aristas de  haversine(u, v) / w(u, v)

Por construcción, en TODA arista  haversine(u, v) / v_max ≤ w(u, v). Como la
distancia haversine cumple la desigualdad triangular:
    h(u) - h(v) ≤ haversine(u, v) / v_max ≤ w(u, v)
es decir, h es CONSISTENTE (y por lo tanto admisible). Consecuencias: cada nodo
se cierra una sola vez y A* devuelve exactamente el costo de Dijkstra.
"""
from __future__ import annotations

import heapq
from time import perf_counter
from typing import Sequence

from logistics.routing.geo import haversine_km
from logistics.routing.graph import RoadGraph
from logistics.routing.instrument import INF, SearchResult, reconstruct

# Margen de punto flotante: v_max se agranda en una parte en mil millones para
# que h quede apenas por debajo y la consistencia no se rompa por redondeo.
VMAX_SAFETY = 1e-9


def compute_v_max(graph: RoadGraph, weights: Sequence[float]) -> float:
    """Velocidad "en línea recta" máxima del grafo para estos pesos (km por unidad de costo)."""
    best = 0.0
    for e, w in enumerate(weights):
        if w == INF:
            continue  # arista bloqueada: no aporta cota
        straight = graph.straight_km(graph.edge_from[e], graph.edge_to[e])
        if w <= 0:
            if straight > 0:
                return INF  # sin cota posible: h = 0 (A* se vuelve Dijkstra)
            continue
        best = max(best, straight / w)
    return INF if best == 0 else best * (1 + VMAX_SAFETY)


def heuristic(graph: RoadGraph, node: int, target: int, v_max: float) -> float:
    """h(node) hacia `target`, en la unidad del costo."""
    if v_max == INF:
        return 0.0
    # Misma fórmula que dentro de astar(): distancia × (1 / v_max).
    return haversine_km(graph.lat[node], graph.lon[node], graph.lat[target], graph.lon[target]) * (1.0 / v_max)


def astar(
    graph: RoadGraph,
    weights: Sequence[float],
    source: int,
    target: int,
    v_max: float | None = None,
    record_order: bool = False,
) -> SearchResult:
    if v_max is None:
        v_max = compute_v_max(graph, weights)
    n = graph.node_count
    # h se calcula solo para los nodos que se alcanzan (importa en grafos grandes, E7).
    h = [-1.0] * n
    tlat, tlon = graph.lat[target], graph.lon[target]
    lat, lon = graph.lat, graph.lon
    inv_v = 0.0 if v_max == INF else 1.0 / v_max
    g_score = [INF] * n
    prev_edge = [-1] * n
    closed = [False] * n
    g_score[source] = 0.0
    # (f, -g, nodo): con f iguales sale primero el de MAYOR g, el más avanzado hacia el destino.
    h[source] = haversine_km(lat[source], lon[source], tlat, tlon) * inv_v
    heap: list[tuple[float, float, int]] = [(h[source], -0.0, source)]
    expanded, pushed = 0, 1
    order: list[int] | None = [] if record_order else None
    adj = graph.adj

    started = perf_counter()
    while heap:
        _f, neg_g, u = heapq.heappop(heap)
        if closed[u]:
            continue
        closed[u] = True
        expanded += 1
        if order is not None:
            order.append(u)
        if u == target:
            break
        g = -neg_g
        for v, e in adj[u]:
            if closed[v]:
                continue  # con h consistente, un nodo cerrado ya tiene su costo óptimo
            candidate = g + weights[e]
            if candidate < g_score[v]:
                g_score[v] = candidate
                prev_edge[v] = e
                hv = h[v]
                if hv < 0:
                    hv = h[v] = haversine_km(lat[v], lon[v], tlat, tlon) * inv_v
                heapq.heappush(heap, (candidate + hv, -candidate, v))
                pushed += 1
    elapsed_ms = (perf_counter() - started) * 1000

    path, edges = reconstruct(graph, prev_edge, source, target) if g_score[target] < INF else ([], [])
    return SearchResult(
        algorithm="astar", source=source, target=target, cost=g_score[target], path=path, edges=edges,
        expanded=expanded, pushed=pushed, elapsed_ms=elapsed_ms, order=order, v_max=v_max,
    )
