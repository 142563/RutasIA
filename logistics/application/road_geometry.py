"""Geometría de carretera de cada arista, lista para dibujar (fuera del motor).

Las polilíneas de Google traen ~445 000 puntos para las 258 aristas (1 MB). Mandarlas
completas a cada mapa trababa el navegador: las decodificaba y proyectaba enteras en
cada render. Aquí se simplifican una sola vez (Douglas-Peucker con tolerancia de
~10 m, invisible a la escala del mapa) y se guardan en memoria del proceso. La caché
se reconstruye sola cuando cambia el grafo (las señales llaman a invalidate_graph y
load_graph devuelve un objeto nuevo).
"""
from __future__ import annotations

import math
import threading

from logistics.models import Edge
from logistics.routing.graph import load_graph

# Grados de tolerancia: 1e-4° ≈ 11 m en latitud. Los extremos de cada tramo se conservan.
TOLERANCE_DEG = 1e-4

_lock = threading.Lock()
_cache: dict | None = None
_cache_owner: object | None = None


def decode(encoded: str) -> list[tuple[float, float]]:
    """Formato de polilínea de Google (precisión 1e-5)."""
    points, index, lat, lng = [], 0, 0, 0
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            result, shift = 0, 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        points.append((lat / 1e5, lng / 1e5))
    return points


def encode(points: list[tuple[float, float]]) -> str:
    out, prev_lat, prev_lng = [], 0, 0
    for lat, lng in points:
        ilat, ilng = round(lat * 1e5), round(lng * 1e5)
        for value in (ilat - prev_lat, ilng - prev_lng):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def simplify(points: list[tuple[float, float]], tolerance: float = TOLERANCE_DEG) -> list[tuple[float, float]]:
    """Douglas-Peucker iterativo: quita puntos que se desvían menos que `tolerance` de la recta."""
    if len(points) < 3:
        return list(points)
    # La longitud se escala por cos(latitud) para medir en grados "cuadrados" (Guatemala: ~15°).
    scale = math.cos(math.radians(points[0][0]))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (ay, ax), (by, bx) = points[first], points[last]
        ax, bx = ax * scale, bx * scale
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        worst, index = -1.0, -1
        for i in range(first + 1, last):
            py, px = points[i]
            px *= scale
            if norm == 0:
                dist = math.hypot(px - ax, py - ay)
            else:
                dist = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if dist > worst:
                worst, index = dist, i
        if worst > tolerance:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [p for p, k in zip(points, keep) if k]


def _build() -> dict:
    rows = Edge.objects.filter(is_active=True).exclude(polyline="").values_list(
        "origin__code", "destination__code", "polyline")
    result = {}
    for origin, destination, polyline in rows:
        try:
            result[(origin, destination)] = encode(simplify(decode(polyline)))
        except (IndexError, ValueError):
            continue  # polilínea dañada: ese tramo no se dibuja
    return result


def simplified_geometry() -> dict[tuple[str, str], str]:
    """{(origen, destino): polilínea simplificada}, en memoria mientras el grafo no cambie."""
    global _cache, _cache_owner
    owner = load_graph()
    with _lock:
        if _cache is None or _cache_owner is not owner:
            _cache, _cache_owner = _build(), owner
        return _cache


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None
