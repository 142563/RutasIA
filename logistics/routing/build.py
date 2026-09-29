"""Construcción del grafo nacional a partir de los tramos candidatos.

1. Google (TRAFFIC_UNAWARE) mide km y t0 de cada tramo en ambos sentidos.
   Las respuestas se guardan en RouteSample (caché y bitácora de auditoría).
2. Cada tramo se convierte en DOS aristas dirigidas.
3. Se verifica el resultado: rutas no encontradas, rodeos y tramos redundantes.

Modo sin conexión (--estimate): km y minutos ESTIMADOS desde la línea recta,
marcados con source="estimate". Sirven para desarrollar; no son datos de tesis.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from logistics.models import Edge, Node, RouteSample
from logistics.routing.geo import haversine_km
from logistics.routing.google import TRAFFIC_AWARE_OPTIMAL, TRAFFIC_UNAWARE, RoutesClient
from logistics.routing.graph import RoadGraph, invalidate_graph
from logistics.routing.seed_data import NODES, ROAD_SEGMENTS, RoadSegment

# Supuestos PROVISIONALES del modo sin conexión (se reemplazan con Google):
ESTIMATE_DETOUR_FACTOR = 1.3  # km por carretera ≈ 1.3 × km en línea recta
ESTIMATE_SPEED_KMH = 60.0  # velocidad media supuesta sin tráfico

SAMPLE_MAX_AGE = timedelta(days=7)
DETOUR_WARNING_RATIO = 2.5  # km por carretera / km en línea recta
REDUNDANT_TOLERANCE = 1.02  # un camino alterno ≤ 2 % más largo = el tramo pasa por otro nodo


@dataclass
class BuildReport:
    edges_created: int = 0
    edges_updated: int = 0
    edges_skipped: int = 0
    requests: int = 0
    elements: int = 0
    not_found: list[tuple[str, str, str]] = field(default_factory=list)
    detours: list[tuple[str, str, float]] = field(default_factory=list)
    redundant: list[tuple[str, str]] = field(default_factory=list)


def _directed_pairs(segments: list[RoadSegment]) -> dict[tuple[str, str], RoadSegment]:
    pairs = {}
    for s in segments:
        pairs[(s.a, s.b)] = s
        pairs[(s.b, s.a)] = s
    return pairs


def _upsert_edge(origin: Node, destination: Node, defaults: dict, report: BuildReport) -> Edge:
    edge, created = Edge.objects.update_or_create(origin=origin, destination=destination, defaults=defaults)
    if created:
        report.edges_created += 1
    else:
        report.edges_updated += 1
    return edge


# --- Google ----------------------------------------------------------------

def fetch_samples(
    client: RoutesClient,
    nodes: dict[str, Node],
    pairs: list[tuple[str, str]],
    band: str = "",
    day_type: str = "",
    departure_time=None,
    traffic: bool = False,
    refresh: bool = False,
) -> dict[tuple[str, str], RouteSample]:
    """Muestras de Google por par dirigido para un perfil (vacío = sin tráfico).

    Solo pide lo que falta o tiene más de 7 días; lo demás sale de RouteSample.
    """
    fresh_after = timezone.now() - SAMPLE_MAX_AGE
    existing = {
        (s.origin.code, s.destination.code): s
        for s in RouteSample.objects.filter(band=band, day_type=day_type).select_related("origin", "destination")
    }
    missing: dict[str, list[str]] = defaultdict(list)
    for pair in pairs:
        sample = existing.get(pair)
        if refresh or sample is None or not sample.ok or sample.fetched_at < fresh_after:
            missing[pair[0]].append(pair[1])

    # Un origen contra sus vecinos por solicitud: pocas decenas de elementos.
    for origin_code, destination_codes in missing.items():
        origin = nodes[origin_code]
        destinations = [nodes[c] for c in destination_codes]
        elements = client.compute_route_matrix(
            [(origin.latitude, origin.longitude)],
            [(d.latitude, d.longitude) for d in destinations],
            departure_time=departure_time,
            traffic=traffic,
        )
        now = timezone.now()
        for el in elements:
            destination = destinations[el.destination_index]
            sample, _ = RouteSample.objects.update_or_create(
                origin=origin, destination=destination, band=band, day_type=day_type,
                defaults={
                    "departure_time": departure_time,
                    "routing_preference": TRAFFIC_AWARE_OPTIMAL if traffic else TRAFFIC_UNAWARE,
                    "status": el.status,
                    "distance_m": el.distance_m,
                    "duration_s": el.duration_s,
                    "static_duration_s": el.static_duration_s,
                    "fetched_at": now,
                },
            )
            existing[(origin_code, destination.code)] = sample
    return {pair: existing[pair] for pair in pairs if pair in existing}


@transaction.atomic
def build_from_google(client: RoutesClient, refresh: bool = False, segments=ROAD_SEGMENTS) -> BuildReport:
    report = BuildReport()
    nodes = {n.code: n for n in Node.objects.all()}
    pairs = _directed_pairs(segments)
    samples = fetch_samples(client, nodes, list(pairs), refresh=refresh)
    report.requests, report.elements = client.requests_made, client.elements_requested

    for (a, b), segment in pairs.items():
        sample = samples.get((a, b))
        if sample is None or not sample.ok or not sample.distance_m or not (sample.static_duration_s or sample.duration_s):
            report.not_found.append((a, b, sample.status if sample else "sin respuesta"))
            report.edges_skipped += 1
            Edge.objects.filter(origin=nodes[a], destination=nodes[b]).update(is_active=False)
            continue
        t0_s = sample.static_duration_s or sample.duration_s
        _upsert_edge(nodes[a], nodes[b], {
            "distance_km": sample.distance_m / 1000,
            "duration_free_min": t0_s / 60,
            "road": segment.road,
            "source": Edge.Source.GOOGLE,
            "verified_at": sample.fetched_at,
            "is_active": True,
        }, report)

    verify_graph(report, deactivate=True)
    invalidate_graph()
    return report


# --- sin conexión ----------------------------------------------------------

def estimate_segment(a: Node, b: Node) -> tuple[float, float]:
    """(km, minutos) estimados desde la línea recta. NO son datos reales."""
    km = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * ESTIMATE_DETOUR_FACTOR
    return km, km / ESTIMATE_SPEED_KMH * 60


def estimated_graph_from_seed(multipliers=None) -> RoadGraph:
    """Grafo semilla con aristas estimadas, SIN BD (pruebas y experimentos sin conexión)."""
    coords = {n.code: (n.latitude, n.longitude) for n in NODES}
    edges = []
    for (a, b) in _directed_pairs(ROAD_SEGMENTS):
        km = haversine_km(*coords[a], *coords[b]) * ESTIMATE_DETOUR_FACTOR
        edges.append((a, b, km, km / ESTIMATE_SPEED_KMH * 60))
    return RoadGraph.from_lists(
        nodes=[(n.code, n.name, n.latitude, n.longitude) for n in NODES],
        edges=edges,
        multipliers=multipliers,
        sources={"edges": "estimate", "traffic": "synthetic" if multipliers else "none"},
    )


@transaction.atomic
def build_estimated(segments=ROAD_SEGMENTS) -> BuildReport:
    """Aristas estimadas. Nunca pisa aristas que ya vienen de Google o son manuales."""
    report = BuildReport()
    nodes = {n.code: n for n in Node.objects.all()}
    protected = set(
        Edge.objects.exclude(source=Edge.Source.ESTIMATE).values_list("origin__code", "destination__code")
    )
    for (a, b), segment in _directed_pairs(segments).items():
        if (a, b) in protected:
            report.edges_skipped += 1
            continue
        km, minutes = estimate_segment(nodes[a], nodes[b])
        _upsert_edge(nodes[a], nodes[b], {
            "distance_km": km,
            "duration_free_min": minutes,
            "road": segment.road,
            "source": Edge.Source.ESTIMATE,
            "verified_at": None,
            "is_active": True,
        }, report)
    invalidate_graph()
    return report


# --- verificación ----------------------------------------------------------

def _shortest_km_without(adj: dict[int, list[tuple[int, float, int]]], source: int, target: int,
                         skip_edge: int, limit: float) -> float:
    """Dijkstra por km ignorando una arista; se corta al superar `limit`.

    Es una herramienta de verificación del grafo, no el motor de rutas.
    """
    dist = {source: 0.0}
    heap = [(0.0, source)]
    closed = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in closed:
            continue
        if u == target:
            return d
        if d > limit:
            break
        closed.add(u)
        for v, w, edge_id in adj.get(u, []):
            if edge_id == skip_edge:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return float("inf")


def verify_graph(report: BuildReport, deactivate: bool) -> None:
    """Rodeos y tramos redundantes sobre las aristas activas."""
    edges = list(Edge.objects.filter(is_active=True).select_related("origin", "destination"))
    for e in edges:
        straight = haversine_km(e.origin.latitude, e.origin.longitude, e.destination.latitude, e.destination.longitude)
        if straight > 0 and e.distance_km / straight > DETOUR_WARNING_RATIO:
            report.detours.append((e.origin.code, e.destination.code, e.distance_km / straight))

    adj: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
    for e in edges:
        adj[e.origin_id].append((e.destination_id, e.distance_km, e.id))

    # De la arista más larga a la más corta; una arista desactivada ya no sirve
    # de alternativa a otra, así nunca se quitan las dos partes de un mismo camino.
    for e in sorted(edges, key=lambda x: x.distance_km, reverse=True):
        limit = e.distance_km * REDUNDANT_TOLERANCE
        alternative = _shortest_km_without(adj, e.origin_id, e.destination_id, e.id, limit)
        if alternative <= limit:
            report.redundant.append((e.origin.code, e.destination.code))
            adj[e.origin_id] = [item for item in adj[e.origin_id] if item[2] != e.id]
            if deactivate:
                Edge.objects.filter(pk=e.pk).update(is_active=False)
