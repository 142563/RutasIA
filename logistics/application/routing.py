"""Casos de uso del motor de rutas: traduce peticiones a llamadas al motor.

El motor (logistics/routing) trabaja con índices de nodo y listas de pesos; aquí
se resuelven códigos o coordenadas, la hora de salida y el criterio, y los
errores se convierten en PlanningError con mensajes en español.
"""
from __future__ import annotations

import json
from dataclasses import fields as dc_fields
from datetime import date, datetime, time
from time import perf_counter
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from logistics.application import road_geometry
from logistics.domain.exceptions import PlanningError
from logistics.models import DayType, OptimizerSettings, TrafficBand
from logistics.routing.astar import astar
from logistics.routing.dijkstra import dijkstra
from logistics.routing.genetic import GeneticParams
from logistics.routing.graph import CRITERIA, DISTANCE, TIME, RoadGraph, load_graph
from logistics.routing.instrument import SearchResult
from logistics.routing.multistop import (DEFAULT_SERVICE_MIN, GENETIC, OPTIMIZERS, UnreachableStopError,
                                         plan_multistop)
from logistics.routing.traffic import GT_TZ, REPRESENTATIVE_TIME, profile_for, to_local

ALGORITHMS = {"dijkstra": dijkstra, "astar": astar}
MAX_STOPS = 50  # alcance declarado en el protocolo


def geometry(params) -> dict:
    """Geometría simplificada de pares dirigidos (o de toda la red con all=1), fuera del motor.

    Sale de una caché en memoria (road_geometry): no consulta la BD en cada mapa.
    """
    cached = road_geometry.simplified_geometry()
    if str(params.get("all", "")).lower() in ("1", "true"):
        return {"edges": [{"from": a, "to": b, "polyline": p} for (a, b), p in cached.items()]}
    try:
        pairs = json.loads(params.get("edges", "[]"))
    except (ValueError, TypeError):
        raise PlanningError("Indica las aristas como pares de códigos en JSON.") from None
    if not isinstance(pairs, list) or len(pairs) > 500 or any(
        not isinstance(pair, list) or len(pair) != 2 or any(
            not isinstance(code, str) or not code or len(code) > 60 for code in pair
        ) for pair in pairs
    ):
        raise PlanningError("Indica hasta 500 pares de códigos de nodos.")
    edges, seen = [], set()
    for a, b in pairs:
        polyline = cached.get((a, b))
        if polyline and (a, b) not in seen:
            seen.add((a, b))
            edges.append({"from": a, "to": b, "polyline": polyline})
    return {"edges": edges}


def optimizer_params() -> GeneticParams:
    """Parámetros del genético que guardó el administrador (o los de por defecto)."""
    row = OptimizerSettings.objects.filter(pk=1).first()
    if row is None:
        return GeneticParams()
    return GeneticParams(**{f.name: getattr(row, f.name) for f in dc_fields(GeneticParams)}).clamped()


def optimizer_payload(plan) -> dict:
    """Qué algoritmo ordenó las paradas y cuánto tardó (tesis: tiempo de respuesta < 30 s)."""
    return {
        "optimizer": plan.optimizer,
        "ga_generations": plan.ga_generations,
        "optimize_ms": round(plan.optimize_ms, 1),
    }


def get_graph() -> RoadGraph:
    graph = load_graph()
    if graph.node_count == 0 or graph.edge_count == 0:
        raise PlanningError(
            "El grafo vial está vacío. Corre seed_graph_nodes y build_graph (o build_graph --estimate)."
        )
    return graph


def resolve_node(graph: RoadGraph, spec: Any, label: str) -> int:
    """Acepta un código de nodo ("flores") o coordenadas {"lat": .., "lng": ..}."""
    if isinstance(spec, str) and spec.strip():
        try:
            return graph.node_index(spec.strip())
        except KeyError:
            raise PlanningError(f"{label}: no existe el nodo '{spec}'.") from None
    if isinstance(spec, dict):
        if spec.get("code"):
            return resolve_node(graph, spec["code"], label)
        try:
            lat, lng = float(spec["lat"]), float(spec["lng"])
        except (KeyError, TypeError, ValueError):
            raise PlanningError(f"{label}: indica un código de nodo o coordenadas lat/lng.") from None
        return graph.nearest_node(lat, lng)
    raise PlanningError(f"{label}: indica un código de nodo o coordenadas lat/lng.")


def parse_departure(value: Any) -> datetime:
    """Hora de salida ISO 8601; sin zona = hora de Guatemala; vacío = ahora."""
    if not value:
        return to_local(timezone.now())
    moment = parse_datetime(str(value))
    if moment is None:
        raise PlanningError("Hora de salida inválida. Usa el formato 2026-10-06T07:30.")
    return to_local(moment)


def avoid_unpaved(payload) -> bool:
    """Por defecto se evita la terracería; allow_unpaved=true la permite."""
    return str(payload.get("allow_unpaved", "")).lower() not in ("1", "true", "si", "sí", "yes")


def parse_choice(value: Any, allowed, label: str, default: str) -> str:
    value = value or default
    if value not in allowed:
        raise PlanningError(f"{label} inválido. Opciones: {', '.join(allowed)}.")
    return value


# --- serialización -----------------------------------------------------------

def node_payload(graph: RoadGraph, i: int) -> dict:
    return {"code": graph.codes[i], "name": graph.names[i], "kind": graph.kinds[i],
            "lat": graph.lat[i], "lng": graph.lon[i]}


def roads_along(graph: RoadGraph, edges: list[int]) -> list[str]:
    roads: list[str] = []
    for e in edges:
        road = graph.roads[e]
        if road and (not roads or roads[-1] != road):
            roads.append(road)
    return roads


def search_payload(graph: RoadGraph, result: SearchResult, time_weights: list[float]) -> dict:
    return {
        "algorithm": result.algorithm,
        "found": result.found,
        "nodes": [node_payload(graph, i) for i in result.path],
        "roads": roads_along(graph, result.edges),
        "minutes": round(result.total(time_weights), 2) if result.found else None,
        "km": round(result.total(graph.km), 2) if result.found else None,
        "unpaved_km": round(graph.unpaved_km(result.edges), 2) if result.found else None,
        "cost": round(result.cost, 4) if result.found else None,
        "expanded": result.expanded,
        "pushed": result.pushed,
        "elapsed_ms": round(result.elapsed_ms, 4),
    }


def meta(graph: RoadGraph, departure: datetime | None = None, avoid: bool | None = None) -> dict:
    payload = {"data_source": graph.sources}
    if avoid is not None:
        payload["avoid_unpaved"] = avoid
    if departure is not None:
        band, day_type = profile_for(departure)
        payload.update({
            "departure": departure.isoformat(),
            "band": band,
            "band_label": TrafficBand(band).label,
            "day_type": day_type,
        })
    return payload


def _require_found(result: SearchResult, graph: RoadGraph) -> None:
    if not result.found:
        raise PlanningError(
            f"No hay ruta entre {graph.names[result.source]} y {graph.names[result.target]}."
        )


# --- casos de uso ------------------------------------------------------------

def route(payload: dict) -> dict:
    graph = get_graph()
    origin = resolve_node(graph, payload.get("origin"), "Origen")
    destination = resolve_node(graph, payload.get("destination"), "Destino")
    departure = parse_departure(payload.get("departure"))
    algorithm = parse_choice(payload.get("algorithm"), ALGORITHMS, "Algoritmo", "astar")
    criterion = parse_choice(payload.get("criterion"), CRITERIA, "Criterio", TIME)
    band, day_type = profile_for(departure)
    avoid = avoid_unpaved(payload)
    time_weights = graph.weights(TIME, band, day_type)
    weights = graph.search_weights(criterion, band, day_type, avoid)

    result = ALGORITHMS[algorithm](graph, weights, origin, destination)
    _require_found(result, graph)
    return {"route": {**search_payload(graph, result, time_weights), "criterion": criterion},
            **meta(graph, departure, avoid)}


def compare(payload: dict) -> dict:
    """Dijkstra vs A* (mismo costo, distinto esfuerzo) y más rápida vs más corta."""
    graph = get_graph()
    origin = resolve_node(graph, payload.get("origin"), "Origen")
    destination = resolve_node(graph, payload.get("destination"), "Destino")
    departure = parse_departure(payload.get("departure"))
    band, day_type = profile_for(departure)
    avoid = avoid_unpaved(payload)
    time_weights = graph.weights(TIME, band, day_type)
    search = graph.search_weights(TIME, band, day_type, avoid)

    by_dijkstra = dijkstra(graph, search, origin, destination)
    by_astar = astar(graph, search, origin, destination)
    _require_found(by_astar, graph)
    shortest = astar(graph, graph.search_weights(DISTANCE, avoid_unpaved=avoid), origin, destination)

    fastest_payload = search_payload(graph, by_astar, time_weights)
    shortest_payload = search_payload(graph, shortest, time_weights)
    return {
        "algorithms": {
            "dijkstra": search_payload(graph, by_dijkstra, time_weights),
            "astar": fastest_payload,
            "same_cost": abs(by_dijkstra.cost - by_astar.cost) <= 1e-9 * max(1.0, by_dijkstra.cost),
            "expanded_saving_pct": round(100 * (1 - by_astar.expanded / by_dijkstra.expanded), 1),
        },
        "fastest": fastest_payload,
        "shortest": shortest_payload,
        "minutes_saved": round(shortest_payload["minutes"] - fastest_payload["minutes"], 2),
        "same_route": by_astar.path == shortest.path,
        **meta(graph, departure, avoid),
    }


def explore(payload: dict) -> dict:
    """Orden de expansión de ambos algoritmos, para animar el Laboratorio."""
    graph = get_graph()
    origin = resolve_node(graph, payload.get("origin"), "Origen")
    destination = resolve_node(graph, payload.get("destination"), "Destino")
    departure = parse_departure(payload.get("departure"))
    band, day_type = profile_for(departure)
    avoid = avoid_unpaved(payload)
    time_weights = graph.weights(TIME, band, day_type)
    weights = graph.search_weights(TIME, band, day_type, avoid)
    result = {}
    for name, search in ALGORITHMS.items():
        r = search(graph, weights, origin, destination, record_order=True)
        result[name] = {
            **search_payload(graph, r, time_weights),
            "order": [graph.codes[i] for i in r.order],
        }
    return {"explore": result, **meta(graph, departure, avoid)}


def optimize(payload: dict) -> dict:
    started = perf_counter()
    graph = get_graph()
    depot = resolve_node(graph, payload.get("depot"), "Bodega")
    raw_stops = payload.get("stops") or []
    if not isinstance(raw_stops, list) or not raw_stops:
        raise PlanningError("Indica al menos una parada.")
    if len(raw_stops) > MAX_STOPS:
        raise PlanningError(f"Máximo {MAX_STOPS} paradas por ruta.")
    stops = [resolve_node(graph, s, f"Parada {i + 1}") for i, s in enumerate(raw_stops)]
    departure = parse_departure(payload.get("departure"))
    try:
        service_min = float(payload.get("service_min", DEFAULT_SERVICE_MIN))
    except (TypeError, ValueError):
        raise PlanningError("service_min debe ser un número de minutos.") from None
    if service_min < 0:
        raise PlanningError("service_min no puede ser negativo.")

    optimizer = parse_choice(payload.get("optimizer"), OPTIMIZERS, "Optimizador", GENETIC)
    avoid = avoid_unpaved(payload)
    try:
        plan = plan_multistop(graph, depot, stops, departure, service_min, bool(payload.get("return_to_depot")),
                              avoid_unpaved=avoid, optimizer=optimizer, ga_params=optimizer_params())
    except UnreachableStopError as exc:
        raise PlanningError(f"No hay ruta hacia {graph.names[exc.node]}.") from None

    legs = []
    for leg in plan.legs:
        leg_weights = graph.weights(TIME, leg.band, leg.day_type)
        legs.append({
            **search_payload(graph, leg.search, leg_weights),
            "depart_at": leg.depart_at.isoformat(),
            "arrive_at": leg.arrive_at.isoformat(),
            "band": leg.band,
        })
    return {
        "plan": {
            "order": plan.order,
            "stops": [
                {"input_index": i, **node_payload(graph, plan.stops[i]), "eta": eta.isoformat()}
                for i, eta in zip(plan.order, plan.etas)
            ],
            "legs": legs,
            "driving_minutes": round(plan.driving_minutes, 2),
            "total_km": round(plan.total_km, 2),
            "finish_at": plan.finish_at.isoformat(),
            "service_min": service_min,
            "baseline": {
                "capture_order_minutes": round(plan.capture_minutes, 2),
                "nearest_neighbor_minutes": round(plan.nearest_neighbor_minutes, 2),
                "two_opt_minutes": round(plan.two_opt_minutes, 2),
                "optimized_minutes": round(plan.optimized_minutes, 2),
            },
            **optimizer_payload(plan),
            "matrix_expanded": plan.matrix_expanded,
        },
        **meta(graph, departure, avoid),
        # Tiempo real de respuesta del servidor para esta solicitud (tesis: meta < 30 s)
        "response_seconds": round(perf_counter() - started, 3),
    }


def best_departure(params) -> dict:
    """Tiempo del mismo viaje saliendo en cada franja de un día (base de E6)."""
    graph = get_graph()
    origin = resolve_node(graph, params.get("origin"), "Origen")
    destination = resolve_node(graph, params.get("destination"), "Destino")
    day: date | None = parse_date(params.get("date") or "") if params.get("date") else to_local(timezone.now()).date()
    if day is None:
        raise PlanningError("Fecha inválida. Usa el formato 2026-10-06.")
    avoid = avoid_unpaved(params)
    rows = []
    for band in TrafficBand.values:
        departure = datetime.combine(day, REPRESENTATIVE_TIME[band], tzinfo=GT_TZ)
        b, d = profile_for(departure)
        r = astar(graph, graph.search_weights(TIME, b, d, avoid), origin, destination)
        _require_found(r, graph)
        rows.append({
            "band": band, "band_label": TrafficBand(band).label, "departure": departure.isoformat(),
            "minutes": round(r.total(graph.weights(TIME, b, d)), 2), "roads": roads_along(graph, r.edges),
        })
    best = min(rows, key=lambda row: row["minutes"])
    return {
        "origin": node_payload(graph, origin),
        "destination": node_payload(graph, destination),
        "day_type": profile_for(datetime.combine(day, time(12), tzinfo=GT_TZ))[1],
        "bands": rows,
        "best_band": best["band"],
        **meta(graph, avoid=avoid),
    }


def traffic_profile(params) -> dict:
    graph = get_graph()
    band = parse_choice(params.get("band"), TrafficBand.values, "Franja", TrafficBand.PEAK_AM)
    day_type = parse_choice(params.get("day"), DayType.values, "Tipo de día", DayType.WEEKDAY)
    multipliers = graph.multipliers.get((band, day_type))
    edges = [
        {
            "from": graph.codes[graph.edge_from[e]],
            "to": graph.codes[graph.edge_to[e]],
            "road": graph.roads[e],
            "t0_min": round(graph.t0[e], 2),
            "multiplier": round(multipliers[e], 3) if multipliers else 1.0,
        }
        for e in range(graph.edge_count)
    ]
    return {"band": band, "day_type": day_type, "calibrated": multipliers is not None, "edges": edges, **meta(graph)}


def nodes() -> dict:
    """Nodos y tramos (sin dirección) del grafo, para dibujar el mapa esquemático."""
    graph = get_graph()
    seen, edges = set(), []
    for e in range(graph.edge_count):
        a, b = graph.codes[graph.edge_from[e]], graph.codes[graph.edge_to[e]]
        key = frozenset((a, b))
        if key not in seen:
            seen.add(key)
            edges.append({"from": a, "to": b, "road": graph.roads[e]})
    return {"nodes": [node_payload(graph, i) for i in range(graph.node_count)], "edges": edges, **meta(graph)}
