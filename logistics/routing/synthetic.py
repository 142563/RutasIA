"""Grafos sintéticos grandes para E7 (escalabilidad).

Corren en la computadora local, no en Render. Los pesos son
    km = haversine × factor ≥ 1 (curvas de la carretera)
    t0 = km / velocidad (40–90 km/h)
así la heurística de A* sigue siendo admisible, igual que en el grafo real.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

from logistics.routing.geo import haversine_km
from logistics.routing.graph import RoadGraph

ORIGIN_LAT, ORIGIN_LON = 14.0, -91.5  # esquina de la región (Guatemala)
SPACING_DEG = 0.01  # ~1.1 km entre nodos vecinos


def _edge(rng: random.Random, lat, lon, u: int, v: int) -> tuple[float, float]:
    km = haversine_km(lat[u], lon[u], lat[v], lon[v]) * rng.uniform(1.0, 1.4)
    return km, km / rng.uniform(40.0, 90.0) * 60


def _build(name: str, lat: list[float], lon: list[float], pairs: list[tuple[int, int]], rng) -> RoadGraph:
    edges_from, edges_to, km, t0 = [], [], [], []
    for u, v in pairs:
        for a, b in ((u, v), (v, u)):  # dos aristas dirigidas con pesos propios
            k, t = _edge(rng, lat, lon, a, b)
            edges_from.append(a)
            edges_to.append(b)
            km.append(k)
            t0.append(t)
    codes = [f"{name}-{i}" for i in range(len(lat))]
    return RoadGraph(codes=codes, names=codes, lat=lat, lon=lon, edge_from=edges_from, edge_to=edges_to,
                     t0=t0, km=km, sources={"edges": f"synthetic-{name}", "traffic": "none"})


def grid_graph(n_nodes: int, seed: int = 2026) -> RoadGraph:
    """Cuadrícula de ~n nodos con vecinos arriba/abajo/izquierda/derecha."""
    rng = random.Random(seed)
    side = max(2, round(math.sqrt(n_nodes)))
    lat = [ORIGIN_LAT + r * SPACING_DEG for r in range(side) for _c in range(side)]
    lon = [ORIGIN_LON + c * SPACING_DEG for _r in range(side) for c in range(side)]
    pairs = []
    for r in range(side):
        for c in range(side):
            i = r * side + c
            if c + 1 < side:
                pairs.append((i, i + 1))
            if r + 1 < side:
                pairs.append((i, i + side))
    return _build("grid", lat, lon, pairs, rng)


def geometric_graph(n_nodes: int, avg_degree: float = 6.0, seed: int = 2026) -> RoadGraph:
    """Grafo geométrico aleatorio: puntos al azar unidos si están a menos de r.

    r se elige para un grado medio ≈ avg_degree; se usa una rejilla de celdas
    para no comparar todos los pares (O(n) en vez de O(n²)).
    """
    rng = random.Random(seed)
    side_deg = math.sqrt(n_nodes) * SPACING_DEG
    lat = [ORIGIN_LAT + rng.random() * side_deg for _ in range(n_nodes)]
    lon = [ORIGIN_LON + rng.random() * side_deg for _ in range(n_nodes)]
    radius = math.sqrt(avg_degree * side_deg ** 2 / (math.pi * n_nodes))

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n_nodes):
        cells[(int((lat[i] - ORIGIN_LAT) / radius), int((lon[i] - ORIGIN_LON) / radius))].append(i)
    pairs = []
    r2 = radius * radius
    for (cx, cy), members in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((cx + dx, cy + dy), ()):
                    for i in members:
                        if i < j and (lat[i] - lat[j]) ** 2 + (lon[i] - lon[j]) ** 2 <= r2:
                            pairs.append((i, j))
    return _build("geometric", lat, lon, pairs, rng)
