"""Geometría: distancia en línea recta sobre la esfera terrestre."""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia del círculo máximo entre dos puntos GPS, en km.

    Se devuelve sin redondear: redondear hacia arriba puede hacer que h(u) supere
    el costo de una arista y la heurística deja de ser admisible y consistente.
    Es una métrica (cumple la desigualdad triangular), base de la consistencia de A*.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
