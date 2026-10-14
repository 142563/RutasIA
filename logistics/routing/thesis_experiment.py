"""Experimento de la tesis (Cap. III): ruta convencional vs. optimizada, 3 escenarios × 10 repeticiones.

- Convencional: "proximidad sucesiva". Desde la bodega siempre al punto
  GEOGRÁFICAMENTE más cercano al anterior (línea recta), sin tráfico; cada tramo
  por el camino más corto en km (A* con km). Sus minutos se miden con el tráfico
  real de la franja, como los viviría el mensajero.
- Optimizada: el algoritmo genético ordena las paradas con la matriz de minutos
  con tráfico (Dijkstra uno-a-todos) y cada tramo se traza con A* por tiempo.
- Las dos evitan la terracería, como el sistema por defecto (penalización ×20).
- Ambas sobre el MISMO conjunto de puntos, el mismo grafo y la misma franja
  ("mismo instante" = misma ejecución con las mismas condiciones de la vía).

Escenarios (tres corredores interdepartamentales desde la Ciudad de Guatemala):
- normal: tráfico de la franja.
- congestion: la ruta principal del corredor con multiplicador ×2.5 (incidente).
- cierre: un tramo de la ruta principal cerrado; se mide si A* encuentra la
  ruta alternativa y en cuánto tiempo.
Repeticiones: 10 por escenario (4 pico matutino, 3 valle, 3 pico vespertino);
la repetición i usa el mismo conjunto de paradas en los tres escenarios.

Las variantes del grafo se arman EN MEMORIA (copias de RoadGraph); la base de
datos solo se lee. Además se compara el genético con OR-Tools (línea base) en
las mismas 30 instancias, y se mide el tiempo de respuesta con 50 paradas.
"""
from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Callable, Sequence

from logistics.routing import genetic
from logistics.routing.astar import astar
from logistics.routing.geo import haversine_km
from logistics.routing.graph import DISTANCE, TIME, RoadGraph
from logistics.routing.multistop import GENETIC, MultiStopPlan, plan_multistop, time_matrix
from logistics.routing.traffic import GT_TZ, REPRESENTATIVE_TIME, profile_for

DEPOT = "ciudad-guatemala"
STOPS_PER_INSTANCE = 12
REPETITIONS = 10
SERVICE_MIN = 10.0
CONGESTION_MULTIPLIER = 2.5
EXPERIMENT_DAY = date(2026, 10, 13)  # martes (día laboral)
# 4 + 3 + 3 = 10 repeticiones por escenario
BAND_PLAN = ["peak_am"] * 4 + ["mid_morning"] * 3 + ["peak_pm"] * 3
BAND_LABEL = {"peak_am": "pico matutino", "mid_morning": "valle", "peak_pm": "pico vespertino"}
SCENARIOS = ("normal", "congestion", "cierre")
SCENARIO_LABEL = {"normal": "Tráfico normal", "congestion": "Congestionamiento en ruta principal",
                  "cierre": "Cierre de vía con ruta alternativa"}
ALPHA = 0.05
# Igual que la app (planificador y /api/routes/optimize/): la terracería se evita por defecto
AVOID_UNPAVED = True
GOALS = {"distance_pct": 15.0, "time_pct": 20.0, "alternative_success_pct": 90.0, "response_s": 30.0}


@dataclass(frozen=True)
class Corridor:
    key: str
    name: str
    terminal: str  # fin de la ruta principal (la define A* por km desde la capital)
    departments: tuple[str, ...]  # de dónde se toman los puntos de entrega


CORRIDORS = (
    Corridor("occidente", "Occidente (CA-1): Guatemala – Chimaltenango – Quetzaltenango", "quetzaltenango",
             ("SA", "CM", "SO", "TO", "QZ")),
    Corridor("sur", "Sur (CA-9 / CA-2): Guatemala – Escuintla – Mazatenango – Retalhuleu", "retalhuleu",
             ("ES", "SU", "RE", "SR")),
    Corridor("atlantico", "Atlántico (CA-9): Guatemala – El Progreso – Zacapa – Puerto Barrios", "puerto-barrios",
             ("PR", "ZA", "IZ", "CQ")),
)


# --- variantes del grafo en memoria ------------------------------------------

def main_road(graph: RoadGraph, corridor: Corridor) -> list[int]:
    """Aristas (ida) de la ruta principal del corredor: la más corta en km desde la capital."""
    result = astar(graph, graph.search_weights(DISTANCE, avoid_unpaved=AVOID_UNPAVED),
                   graph.node_index(DEPOT), graph.node_index(corridor.terminal))
    if not result.found:
        raise ValueError(f"El corredor {corridor.key} no está conectado en el grafo.")
    return list(result.edges)


def _reverse_edges(graph: RoadGraph, edges: Sequence[int]) -> list[int]:
    pairs = {(graph.edge_to[e], graph.edge_from[e]) for e in edges}
    return [e for e in range(graph.edge_count) if (graph.edge_from[e], graph.edge_to[e]) in pairs]


def congested(graph: RoadGraph, edges: Sequence[int], factor: float = CONGESTION_MULTIPLIER) -> RoadGraph:
    """Copia del grafo con la ruta principal (ambos sentidos) multiplicada por `factor` (≥ 1) en toda franja."""
    hit = set(edges) | set(_reverse_edges(graph, edges))
    multipliers = {profile: [m * factor if e in hit else m for e, m in enumerate(values)]
                   for profile, values in graph.multipliers.items()}
    return replace(graph, multipliers=multipliers)


def closed(graph: RoadGraph, edges: Sequence[int]) -> RoadGraph:
    """Copia del grafo SIN las aristas cerradas (ambos sentidos)."""
    drop = set(edges) | set(_reverse_edges(graph, edges))
    keep = [e for e in range(graph.edge_count) if e not in drop]
    pick = lambda values: [values[e] for e in keep]  # noqa: E731
    return replace(
        graph,
        edge_from=pick(graph.edge_from), edge_to=pick(graph.edge_to), t0=pick(graph.t0), km=pick(graph.km),
        roads=pick(graph.roads), edge_db_ids=pick(graph.edge_db_ids), road_classes=pick(graph.road_classes),
        multipliers={profile: pick(values) for profile, values in graph.multipliers.items()},
    )


def closure_edges(graph: RoadGraph, road: Sequence[int]) -> list[int]:
    """Tramo a cerrar: la primera arista de la ruta principal, desde un tercio del camino,
    cuyo cierre deja conectados la capital y el destino (hay alternativa)."""
    start = len(road) // 3
    depot, terminal = graph.edge_from[road[0]], graph.edge_to[road[-1]]
    for e in [*road[start:], *road[:start]]:
        test = closed(graph, [e])
        if astar(test, test.search_weights(DISTANCE, avoid_unpaved=AVOID_UNPAVED), depot, terminal).found:
            return [e]
    raise ValueError("Ningún tramo de la ruta principal tiene alternativa.")


# --- las dos rutas -----------------------------------------------------------

def conventional_order(graph: RoadGraph, depot: int, stops: Sequence[int]) -> list[int]:
    """Proximidad sucesiva: siempre al punto pendiente más cercano en línea recta (sin tráfico)."""
    pending, order, current = set(range(len(stops))), [], depot
    while pending:
        nxt = min(pending, key=lambda i: (haversine_km(graph.lat[current], graph.lon[current],
                                                       graph.lat[stops[i]], graph.lon[stops[i]]), i))
        order.append(nxt)
        pending.remove(nxt)
        current = stops[nxt]
    return order


def conventional_plan(graph: RoadGraph, depot: int, stops: Sequence[int], departure: datetime) -> MultiStopPlan:
    return plan_multistop(graph, depot, stops, departure, SERVICE_MIN, return_to_depot=True, criterion=DISTANCE,
                          fixed_order=conventional_order(graph, depot, stops), avoid_unpaved=AVOID_UNPAVED)


def optimized_plan(graph: RoadGraph, depot: int, stops: Sequence[int], departure: datetime,
                   params: genetic.GeneticParams | None = None) -> tuple[MultiStopPlan, float]:
    """Plan del genético y su tiempo de respuesta real en segundos (matriz + genético + tramos)."""
    started = time.perf_counter()
    plan = plan_multistop(graph, depot, stops, departure, SERVICE_MIN, return_to_depot=True, criterion=TIME,
                          optimizer=GENETIC, ga_params=params, avoid_unpaved=AVOID_UNPAVED)
    return plan, time.perf_counter() - started


def unpaved_km(graph: RoadGraph, plan: MultiStopPlan) -> float:
    return sum(graph.unpaved_km(leg.search.edges) for leg in plan.legs)


def reduction_pct(conventional: float, optimized: float) -> float:
    return (conventional - optimized) / conventional * 100 if conventional else 0.0


# --- corrida -----------------------------------------------------------------

def instance_stops(graph: RoadGraph, departments: dict[str, str], corridor: Corridor, repetition: int,
                   seed: int, size: int = STOPS_PER_INSTANCE) -> list[int]:
    pool = sorted(i for i, code in enumerate(graph.codes)
                  if departments.get(code) in corridor.departments and code != DEPOT)
    rng = random.Random(f"{seed}-{corridor.key}-{repetition}")
    return rng.sample(pool, min(size, len(pool)))


def run(graph: RoadGraph, departments: dict[str, str], seed: int = 2026, repetitions: int = REPETITIONS,
        params: genetic.GeneticParams | None = None, baseline: Callable | None = None,
        progress: Callable[[str], None] | None = None) -> tuple[list[dict], list[dict]]:
    """Devuelve (matriz comparativa, genético vs OR-Tools). `baseline(matrix) -> (cost, ms)` o None."""
    depot = graph.node_index(DEPOT)
    roads = {c.key: main_road(graph, c) for c in CORRIDORS}
    variants = {
        (c.key, "normal"): graph for c in CORRIDORS
    }
    closures = {}
    for c in CORRIDORS:
        variants[(c.key, "congestion")] = congested(graph, roads[c.key])
        closures[c.key] = closure_edges(graph, roads[c.key])
        variants[(c.key, "cierre")] = closed(graph, closures[c.key])

    rows, baseline_rows = [], []
    for scenario in SCENARIOS:
        for rep in range(repetitions):
            corridor = CORRIDORS[rep % len(CORRIDORS)]
            band = BAND_PLAN[rep % len(BAND_PLAN)]
            departure = datetime.combine(EXPERIMENT_DAY, REPRESENTATIVE_TIME[band], tzinfo=GT_TZ)
            g = variants[(corridor.key, scenario)]
            stops = instance_stops(graph, departments, corridor, rep, seed)
            conv = conventional_plan(g, depot, stops, departure)
            opt, response_s = optimized_plan(g, depot, stops, departure, params)
            row = {
                "escenario": scenario,
                "escenario_nombre": SCENARIO_LABEL[scenario],
                "repeticion": rep + 1,
                "corredor": corridor.name,
                "franja": BAND_LABEL[band],
                "salida": departure.isoformat(),
                "paradas": len(stops),
                "convencional_km": round(conv.total_km, 2),
                "optimizada_km": round(opt.total_km, 2),
                "reduccion_km_pct": round(reduction_pct(conv.total_km, opt.total_km), 2),
                "convencional_min": round(conv.driving_minutes),
                "optimizada_min": round(opt.driving_minutes),
                "reduccion_min_pct": round(reduction_pct(conv.driving_minutes, opt.driving_minutes), 2),
                # Sin redondear, para la estadística
                "convencional_min_exacto": round(conv.driving_minutes, 3),
                "optimizada_min_exacto": round(opt.driving_minutes, 3),
                "convencional_km_terraceria": round(unpaved_km(g, conv), 2),
                "optimizada_km_terraceria": round(unpaved_km(g, opt), 2),
                "tiempo_respuesta_s": round(response_s, 3),
                "generaciones_ga": opt.ga_generations,
                "tramo_cerrado": "",
                "ruta_alterna_exitosa": "",
                "ruta_alterna_s": "",
            }
            if scenario == "cierre":
                edge = closures[corridor.key][0]
                row["tramo_cerrado"] = f"{graph.codes[graph.edge_from[edge]]} -> {graph.codes[graph.edge_to[edge]]}"
                # Éxito: A* encuentra la alternativa hasta cada parada sin pasar por el tramo cerrado
                started = time.perf_counter()
                band_key, day = profile_for(departure)
                weights = g.search_weights(TIME, band_key, day, AVOID_UNPAVED)
                ok = all(astar(g, weights, depot, s).found for s in stops) and len(opt.legs) == len(stops) + 1
                row["ruta_alterna_exitosa"] = ok
                row["ruta_alterna_s"] = round(time.perf_counter() - started, 4)
            row["fuente_datos"] = ";".join(f"{k}={v}" for k, v in sorted(graph.sources.items()))
            rows.append(row)

            if baseline is not None:
                band_key, day = profile_for(departure)
                matrix, _ = time_matrix(g, g.search_weights(TIME, band_key, day, AVOID_UNPAVED), [depot, *stops])
                ga = genetic.solve(matrix, params, return_to_depot=True)
                ort_cost, ort_ms = baseline(matrix)
                baseline_rows.append({
                    "escenario": scenario, "repeticion": rep + 1, "corredor": corridor.key,
                    "franja": BAND_LABEL[band], "paradas": len(stops),
                    "genetico_min": round(ga.cost, 3), "ortools_min": round(ort_cost, 3),
                    "diferencia_pct": round((ga.cost - ort_cost) / ort_cost * 100, 3) if ort_cost else 0.0,
                    "genetico_ms": round(ga.ms, 1), "ortools_ms": round(ort_ms, 1),
                })
            if progress:
                progress(f"{scenario} #{rep + 1}: {row['convencional_min']} -> {row['optimizada_min']} min, "
                         f"{row['convencional_km']} -> {row['optimizada_km']} km ({response_s:.2f} s)")
    return rows, baseline_rows


def response_time_50(graph: RoadGraph, seed: int = 2026, params: genetic.GeneticParams | None = None) -> list[dict]:
    """Tiempo de respuesta real con el máximo de 50 paradas, en cada franja del experimento."""
    depot = graph.node_index(DEPOT)
    pool = [i for i in range(graph.node_count) if i != depot]
    rows = []
    for band in ("peak_am", "mid_morning", "peak_pm"):
        stops = random.Random(f"{seed}-50-{band}").sample(pool, min(50, len(pool)))
        departure = datetime.combine(EXPERIMENT_DAY, REPRESENTATIVE_TIME[band], tzinfo=GT_TZ)
        plan, seconds = optimized_plan(graph, depot, stops, departure, params)
        rows.append({"franja": BAND_LABEL[band], "paradas": len(stops), "tiempo_respuesta_s": round(seconds, 3),
                     "generaciones_ga": plan.ga_generations})
    return rows


# --- estadística (SciPy, solo en desarrollo) -----------------------------------

def _paired_test(conventional: Sequence[float], optimized: Sequence[float]) -> dict:
    """Shapiro-Wilk sobre las diferencias; t pareada si son normales, si no Wilcoxon.
    H1 unilateral: la optimizada es menor que la convencional. d de Cohen pareada."""
    from scipy import stats

    diffs = [c - o for c, o in zip(conventional, optimized)]
    n = len(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    shapiro_p = float(stats.shapiro(diffs).pvalue) if n >= 3 and sd > 0 else None
    normal = shapiro_p is not None and shapiro_p > ALPHA
    if sd == 0:
        test, p = "sin variación", (0.0 if statistics.mean(diffs) > 0 else 1.0)
    elif normal:
        test, p = "t pareada", float(stats.ttest_rel(conventional, optimized, alternative="greater").pvalue)
    else:
        test, p = "Wilcoxon", float(stats.wilcoxon(conventional, optimized, alternative="greater").pvalue)
    mean_red = statistics.mean(reduction_pct(c, o) for c, o in zip(conventional, optimized))
    return {
        "n": n,
        "media_convencional": round(statistics.mean(conventional), 3),
        "media_optimizada": round(statistics.mean(optimized), 3),
        "de_convencional": round(statistics.stdev(conventional), 3) if n > 1 else 0.0,
        "de_optimizada": round(statistics.stdev(optimized), 3) if n > 1 else 0.0,
        "reduccion_media_pct": round(mean_red, 2),
        "shapiro_p": None if shapiro_p is None else round(shapiro_p, 5),
        "diferencias_normales": normal,
        "prueba": test,
        "p_valor": p if p < 1e-4 else round(p, 5),
        "d_cohen": round(statistics.mean(diffs) / sd, 3) if sd else (math.inf if statistics.mean(diffs) else 0.0),
        "significativo": p < ALPHA,
    }


def statistics_report(rows: list[dict], baseline_rows: list[dict], response_50: list[dict]) -> dict:
    def block(subset: list[dict]) -> dict:
        km = _paired_test([r["convencional_km"] for r in subset], [r["optimizada_km"] for r in subset])
        mins = _paired_test([r["convencional_min_exacto"] for r in subset], [r["optimizada_min_exacto"] for r in subset])
        km["cumple_meta_15"] = km["reduccion_media_pct"] >= GOALS["distance_pct"]
        mins["cumple_meta_20"] = mins["reduccion_media_pct"] >= GOALS["time_pct"]
        return {"distancia_km": km, "tiempo_min": mins}

    total = block(rows)
    closures = [r for r in rows if r["escenario"] == "cierre"]
    success = sum(1 for r in closures if r["ruta_alterna_exitosa"]) / len(closures) * 100 if closures else None
    responses = [r["tiempo_respuesta_s"] for r in rows] + [r["tiempo_respuesta_s"] for r in response_50]
    km = total["distancia_km"]
    return {
        "alfa": ALPHA,
        "metas": GOALS,
        "pares": len(rows),
        "total": total,
        "por_escenario": {s: block([r for r in rows if r["escenario"] == s]) for s in SCENARIOS},
        "ruta_alternativa": {"casos": len(closures), "exito_pct": success,
                             "cumple_meta_90": success is not None and success > GOALS["alternative_success_pct"],
                             "max_s": max((r["ruta_alterna_s"] for r in closures), default=None)},
        "tiempo_respuesta": {"max_s": round(max(responses), 3), "media_s": round(statistics.mean(responses), 3),
                             "con_50_paradas": response_50,
                             "cumple_meta_30": max(responses) < GOALS["response_s"]},
        # Regla de decisión de la tesis: se rechaza H0 si p < 0.05 Y la reducción media es ≥ 15 %
        "h0_distancia": {"rechazada": bool(km["significativo"] and km["cumple_meta_15"]),
                         "regla": "p < 0.05 y reducción media de distancia ≥ 15 %"},
        "genetico_vs_ortools": _baseline_summary(baseline_rows),
    }


def _baseline_summary(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    gaps = [r["diferencia_pct"] for r in rows]
    return {
        "instancias": len(rows),
        "genetico_igual_o_mejor": sum(1 for g in gaps if g <= 1e-6),
        "diferencia_media_pct": round(statistics.mean(gaps), 3),
        "diferencia_max_pct": round(max(gaps), 3),
        "genetico_ms_media": round(statistics.mean(r["genetico_ms"] for r in rows), 1),
        "ortools_ms_media": round(statistics.mean(r["ortools_ms"] for r in rows), 1),
    }
