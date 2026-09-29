"""Experimentos E1, E2, E3, E5 y E7 para el documento de tesis (docs/PLAN.md §2.10).

Cada función devuelve filas (dicts) listas para CSV. Toda fila lleva la fuente
de los datos: con aristas "estimate" o tráfico "synthetic" los números sirven
para probar el pipeline, NO para el documento.
"""
from __future__ import annotations

import math
import random
import statistics
from datetime import datetime
from typing import Callable

from logistics.models import DayType, Node, TrafficBand
from logistics.routing.astar import astar, compute_v_max
from logistics.routing.dijkstra import dijkstra, dijkstra_all
from logistics.routing.graph import DISTANCE, TIME, RoadGraph
from logistics.routing.multistop import nearest_neighbor, route_cost, time_matrix, two_opt
from logistics.routing.synthetic import geometric_graph, grid_graph
from logistics.routing.traffic import GT_TZ

PROFILES = [(band, day) for day in DayType.values for band in TrafficBand.values]


def data_source(graph: RoadGraph) -> str:
    return ";".join(f"{k}={v}" for k, v in sorted(graph.sources.items()))


def same_cost(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def median_ms(run: Callable[[], object], reps: int) -> tuple[object, float]:
    """Resultado de la primera corrida y la mediana de sus ms (en ~100 nodos los ms son diminutos)."""
    times, result = [], None
    for _ in range(reps):
        r = run()
        result = result or r
        times.append(r.elapsed_ms)
    return result, statistics.median(times)


def weight_sets(graph: RoadGraph, quick: bool):
    yield "sin_trafico", graph.weights(TIME)
    profiles = [(TrafficBand.PEAK_AM, DayType.WEEKDAY)] if quick else PROFILES
    for band, day in profiles:
        yield f"{band}/{day}", graph.weights(TIME, band, day)
    yield "km", graph.weights(DISTANCE)


def sources_for(graph: RoadGraph, quick: bool) -> range:
    return range(0, graph.node_count, 9 if quick else 1)


# --- E1: correctitud -----------------------------------------------------------

def e1_correctness(graph: RoadGraph, quick: bool = False) -> list[dict]:
    rows = []
    for profile, w in weight_sets(graph, quick):
        v_max = compute_v_max(graph, w)
        pairs = equal = 0
        worst = 0.0
        for s in sources_for(graph, quick):
            tree = dijkstra_all(graph, w, s)
            for t in range(graph.node_count):
                if t == s or tree.dist[t] == math.inf:
                    continue
                a = astar(graph, w, s, t, v_max=v_max)
                pairs += 1
                equal += same_cost(a.cost, tree.dist[t])
                worst = max(worst, abs(a.cost - tree.dist[t]))
        rows.append({"profile": profile, "pairs": pairs, "equal": equal,
                     "pct_equal": round(100 * equal / pairs, 4) if pairs else None,
                     "max_abs_diff": worst, "data_source": data_source(graph)})
    return rows


# --- E2: eficiencia ------------------------------------------------------------

def e2_efficiency(graph: RoadGraph, reps: int = 5, quick: bool = False) -> list[dict]:
    rows = []
    profiles = [("sin_trafico", None, None), ("peak_am/weekday", TrafficBand.PEAK_AM, DayType.WEEKDAY)]
    for label, band, day in profiles:
        w = graph.weights(TIME, band, day)
        v_max = compute_v_max(graph, w)
        for s in sources_for(graph, quick):
            for t in range(graph.node_count):
                if s == t:
                    continue
                d, d_ms = median_ms(lambda: dijkstra(graph, w, s, t), reps)
                a, a_ms = median_ms(lambda: astar(graph, w, s, t, v_max=v_max), reps)
                if not d.found:
                    continue
                rows.append({
                    "profile": label, "origin": graph.codes[s], "destination": graph.codes[t],
                    "straight_km": round(graph.straight_km(s, t), 2), "minutes": round(d.cost, 2),
                    "dijkstra_expanded": d.expanded, "astar_expanded": a.expanded,
                    "dijkstra_ms": round(d_ms, 5), "astar_ms": round(a_ms, 5),
                    "same_cost": same_cost(d.cost, a.cost), "data_source": data_source(graph),
                })
    return rows


# --- E3: impacto del tráfico ---------------------------------------------------

def e3_traffic_impact(graph: RoadGraph, codes: list[str] | None = None, quick: bool = False) -> list[dict]:
    """Más rápida (tiempo con tráfico) vs más corta (km), evaluadas en la misma franja."""
    if codes is None:
        codes = list(Node.objects.filter(kind=Node.Kind.CABECERA).values_list("code", flat=True))
    nodes = [graph.index[c] for c in codes if c in graph.index]
    if quick:
        nodes = nodes[:6]
    km_w = graph.weights(DISTANCE)
    shortest = {(s, t): astar(graph, km_w, s, t) for s in nodes for t in nodes if s != t}
    rows = []
    for band, day in PROFILES:
        w = graph.weights(TIME, band, day)
        v_max = compute_v_max(graph, w)
        for (s, t), short in shortest.items():
            if not short.found:
                continue
            fast = astar(graph, w, s, t, v_max=v_max)
            short_minutes = short.total(w)
            rows.append({
                "band": band, "day_type": day, "origin": graph.codes[s], "destination": graph.codes[t],
                "fastest_minutes": round(fast.cost, 2), "fastest_km": round(fast.total(graph.km), 2),
                "shortest_minutes": round(short_minutes, 2), "shortest_km": round(short.cost, 2),
                "minutes_saved": round(short_minutes - fast.cost, 2),
                "route_changes": fast.path != short.path, "data_source": data_source(graph),
            })
    return rows


# --- E5: varias paradas --------------------------------------------------------

def e5_multistop(graph: RoadGraph, sizes=(5, 10, 15, 20), instances: int = 30, seed: int = 2026,
                 depot_code: str = "ciudad-guatemala") -> list[dict]:
    rng = random.Random(seed)
    depot = graph.index.get(depot_code, 0)
    w = graph.weights(TIME, TrafficBand.PEAK_AM, DayType.WEEKDAY)
    candidates = [i for i in range(graph.node_count) if i != depot]
    rows = []
    for k in sizes:
        for instance in range(instances):
            stops = rng.sample(candidates, min(k, len(candidates)))
            matrix, _ = time_matrix(graph, w, [depot, *stops])
            if any(x == math.inf for x in matrix[0]):
                continue
            capture = list(range(1, len(stops) + 1))
            nn = nearest_neighbor(matrix)
            opt = two_opt(nn, matrix)
            c, n, o = route_cost(capture, matrix), route_cost(nn, matrix), route_cost(opt, matrix)
            rows.append({
                "stops": k, "instance": instance, "capture_minutes": round(c, 2),
                "nearest_neighbor_minutes": round(n, 2), "two_opt_minutes": round(o, 2),
                "two_opt_vs_capture_pct": round(100 * (c - o) / c, 2),
                "two_opt_vs_nn_pct": round(100 * (n - o) / n, 2), "data_source": data_source(graph),
            })
    return rows


# --- E7: escalabilidad ---------------------------------------------------------

def e7_scalability(max_nodes: int = 100_000, queries: int = 20, reps: int = 3, seed: int = 2026) -> list[dict]:
    rows = []
    sizes = [n for n in (1_000, 10_000, 100_000) if n <= max_nodes]
    for n in sizes:
        for builder in (grid_graph, geometric_graph):
            graph = builder(n, seed=seed)
            w = graph.weights(TIME)
            v_max = compute_v_max(graph, w)
            rng = random.Random(seed + n)
            done = attempts = 0
            while done < queries and attempts < queries * 10:
                attempts += 1
                s, t = rng.randrange(graph.node_count), rng.randrange(graph.node_count)
                if s == t:
                    continue
                d, d_ms = median_ms(lambda: dijkstra(graph, w, s, t), reps)
                if not d.found:
                    continue  # geométrico: el par cayó en componentes distintas
                a, a_ms = median_ms(lambda: astar(graph, w, s, t, v_max=v_max), reps)
                rows.append({
                    "graph": graph.sources["edges"], "nodes": graph.node_count, "edges": graph.edge_count,
                    "query": done, "straight_km": round(graph.straight_km(s, t), 2),
                    "dijkstra_expanded": d.expanded, "astar_expanded": a.expanded,
                    "dijkstra_ms": round(d_ms, 4), "astar_ms": round(a_ms, 4),
                    "same_cost": same_cost(d.cost, a.cost), "data_source": graph.sources["edges"],
                })
                done += 1
    return rows


def run_date() -> str:
    return datetime.now(GT_TZ).strftime("%Y-%m-%d %H:%M")
