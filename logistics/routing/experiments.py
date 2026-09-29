"""Experimentos E1 a E7 (con E4 y E6) para el documento de tesis (docs/PLAN.md §2.10).

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

from django.utils import timezone

from logistics.models import DayType, Node, RouteSample, TrafficBand
from logistics.routing.astar import astar, compute_v_max
from logistics.routing.build import SAMPLE_MAX_AGE, fetch_samples
from logistics.routing.dijkstra import dijkstra, dijkstra_all
from logistics.routing.google import RoutesClient
from logistics.routing.graph import DISTANCE, TIME, RoadGraph
from logistics.routing.multistop import nearest_neighbor, route_cost, time_matrix, two_opt
from logistics.routing.synthetic import geometric_graph, grid_graph
from logistics.routing.traffic import GT_TZ, representative_departure

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


# --- E4: precisión (MAPE contra Google) ---------------------------------------

E4_MIN_STRAIGHT_KM = 100  # "ruta completa": viajes largos, no un tramo entre vecinos
GOOGLE_SOURCE = "google_routes"


def e4_trips(graph: RoadGraph, count: int = 50, seed: int = 2026) -> list[dict]:
    """Viajes (origen, destino, franja, tipo de día) muestreados con semilla fija entre cabeceras."""
    heads = [i for i in range(graph.node_count) if graph.kinds[i] == Node.Kind.CABECERA] or list(range(graph.node_count))
    combos = [(s, t, band, day) for s in heads for t in heads
              if s != t and graph.straight_km(s, t) >= E4_MIN_STRAIGHT_KM for band, day in PROFILES]
    rng = random.Random(seed)
    picked = rng.sample(combos, min(count, len(combos)))
    return [{"trip": n, "origin": graph.codes[s], "destination": graph.codes[t], "band": band, "day_type": day}
            for n, (s, t, band, day) in enumerate(picked)]


def e4_cached(trips: list[dict], max_age=None) -> dict[tuple, RouteSample]:
    """Muestras de Google ya guardadas para esos viajes (solo respuestas OK; sin `max_age`, de cualquier edad)."""
    found = {}
    fresh_after = timezone.now() - max_age if max_age else None
    for band, day in {(t["band"], t["day_type"]) for t in trips}:
        wanted = {(t["origin"], t["destination"]) for t in trips if t["band"] == band and t["day_type"] == day}
        for s in RouteSample.objects.filter(band=band, day_type=day).select_related("origin", "destination"):
            pair = (s.origin.code, s.destination.code)
            if pair in wanted and s.ok and (fresh_after is None or s.fetched_at >= fresh_after):
                found[(*pair, band, day)] = s
    return found


def e4_pending(trips: list[dict]) -> int:
    """Consultas a Google que faltan (las que fetch_samples pediría): sin muestra OK de los últimos 7 días."""
    cached = e4_cached(trips, max_age=SAMPLE_MAX_AGE)
    return sum((t["origin"], t["destination"], t["band"], t["day_type"]) not in cached for t in trips)


def e4_precision(graph: RoadGraph, trips: list[dict], client: RoutesClient | None = None, now=None,
                 refresh: bool = False) -> list[dict]:
    """Minutos del motor (ruta completa con el tráfico de la franja) vs duración de Google (TRAFFIC_AWARE).

    Con `client` pide a Google lo que falta en RouteSample; sin él usa solo la caché (y omite lo que no esté).
    """
    now = now or timezone.now()
    samples: dict[tuple, RouteSample] = {}
    if client is not None:
        codes = {c for t in trips for c in (t["origin"], t["destination"])}
        nodes = {n.code: n for n in Node.objects.filter(code__in=codes)}
        for band, day in sorted({(t["band"], t["day_type"]) for t in trips}):
            pairs = [(t["origin"], t["destination"]) for t in trips if t["band"] == band and t["day_type"] == day]
            got = fetch_samples(client, nodes, pairs, band=band, day_type=day, traffic=True, refresh=refresh,
                                departure_time=representative_departure(band, day, now))
            samples.update({(*pair, band, day): s for pair, s in got.items()})
    else:
        samples = e4_cached(trips)

    rows = []
    for t in trips:
        sample = samples.get((t["origin"], t["destination"], t["band"], t["day_type"]))
        if sample is None or not sample.ok:
            continue
        s, d = graph.index[t["origin"]], graph.index[t["destination"]]
        w = graph.weights(TIME, t["band"], t["day_type"])
        res = astar(graph, w, s, d, v_max=compute_v_max(graph, w))
        if not res.found:
            continue
        engine, google = res.cost, sample.duration_s / 60
        rows.append({
            **t, "engine_min": round(engine, 2), "google_min": round(google, 2),
            "abs_error_min": round(abs(engine - google), 2),
            "signed_error_pct": round(100 * (engine - google) / google, 2),
            "error_pct": round(100 * abs(engine - google) / google, 2),
            "engine_km": round(res.total(graph.km), 1), "google_km": round(sample.distance_m / 1000, 1),
            "data_source": f"motor[{data_source(graph)}];google={GOOGLE_SOURCE}",
        })
    return rows


def e4_summary(rows: list[dict]) -> list[dict]:
    """MAPE global y por franja (promedio del error porcentual absoluto) y sesgo (error con signo)."""
    out = []
    groups = [("global", rows)] + [(b, [r for r in rows if r["band"] == b]) for b in TrafficBand.values]
    for label, sub in groups:
        if not sub:
            continue
        out.append({"group": label, "trips": len(sub),
                    "mape_pct": round(statistics.mean(r["error_pct"] for r in sub), 2),
                    "bias_pct": round(statistics.mean(r["signed_error_pct"] for r in sub), 2),
                    "data_source": sub[0]["data_source"]})
    return out


# --- E6: hora de salida --------------------------------------------------------

E6_PAIRS = [("ciudad-guatemala", "quetzaltenango"), ("ciudad-guatemala", "flores"),
            ("ciudad-guatemala", "puerto-barrios"), ("ciudad-guatemala", "escuintla")]


def road_names(graph: RoadGraph, edges: list[int]) -> str:
    """Carreteras de la ruta en orden, sin repetir tramos seguidos de la misma."""
    names: list[str] = []
    for e in edges:
        road = graph.roads[e]
        if road and (not names or names[-1] != road):
            names.append(road)
    return " > ".join(names)


def e6_departure_time(graph: RoadGraph, pairs: list[tuple[str, str]] | None = None, quick: bool = False) -> list[dict]:
    """La ruta más rápida de un mismo viaje saliendo en cada franja (7 × laboral/fin de semana)."""
    pairs = [p for p in (pairs or E6_PAIRS) if p[0] in graph.index and p[1] in graph.index]
    if quick:
        pairs = pairs[:2]
    rows = []
    for origin, destination in pairs:
        s, t = graph.index[origin], graph.index[destination]
        for band, day in PROFILES:
            w = graph.weights(TIME, band, day)
            a = astar(graph, w, s, t, v_max=compute_v_max(graph, w))
            if not a.found:
                continue
            rows.append({
                "pair": f"{origin} -> {destination}", "origin": origin, "destination": destination,
                "band": band, "day_type": day, "minutes": round(a.cost, 2), "km": round(a.total(graph.km), 1),
                "route_roads": road_names(graph, a.edges),
                "same_cost_dijkstra": same_cost(a.cost, dijkstra(graph, w, s, t).cost),
                "data_source": data_source(graph),
            })
    return rows


def run_date() -> str:
    return datetime.now(GT_TZ).strftime("%Y-%m-%d %H:%M")
