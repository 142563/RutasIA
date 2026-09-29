"""Pruebas de la heurística de A* (distancia Haversine sin redondeo)."""
import math
import random
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from logistics.domain.services import AStarOptimizer, RouteOptimizer, haversine_km
from logistics.models import Department, RouteConnection

CIUDAD_GUATEMALA = (14.6349, -90.5069)
# Punto a ~25.4075 km: el redondeo viejo (ROUND_HALF_UP a 2 decimales) lo subía a 25.41.
CERCA_DE_ANTIGUA = (14.5587, -90.7295)


def _reference_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Cálculo independiente (forma atan2 de Haversine) para comparar."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class HaversineTests(SimpleTestCase):
    def test_returns_unrounded_float(self):
        value = haversine_km(*CIUDAD_GUATEMALA, *CERCA_DE_ANTIGUA)
        self.assertIsInstance(value, float)
        self.assertNotEqual(value, round(value, 2))

    def test_never_rounds_up(self):
        value = float(haversine_km(*CIUDAD_GUATEMALA, *CERCA_DE_ANTIGUA))
        exact = _reference_km(*CIUDAD_GUATEMALA, *CERCA_DE_ANTIGUA)
        self.assertLess(value, 25.41)
        self.assertAlmostEqual(value, exact, delta=1e-9)

    def test_matches_reference_on_random_pairs_in_guatemala(self):
        rng = random.Random(2026)
        for _ in range(1000):
            p = (rng.uniform(13.7, 17.8), rng.uniform(-92.2, -88.2))
            q = (rng.uniform(13.7, 17.8), rng.uniform(-92.2, -88.2))
            self.assertAlmostEqual(float(haversine_km(*p, *q)), _reference_km(*p, *q), delta=1e-9)

    def test_heuristic_consistent_on_tight_edge(self):
        """La arista que define v_max es "ajustada": h(u) == costo(u, v).

        Si la distancia se redondea hacia arriba, h(u) > costo(u, v) y se rompe
        la consistencia h(u) <= costo(u, v) + h(v), con h(v) = 0 en el destino.
        """
        cost_min = 20.0  # minutos por la arista u -> v en su franja más rápida
        v_max = _reference_km(*CIUDAD_GUATEMALA, *CERCA_DE_ANTIGUA) / cost_min  # km/min
        h_u = float(haversine_km(*CIUDAD_GUATEMALA, *CERCA_DE_ANTIGUA)) / v_max
        h_v = 0.0
        self.assertLessEqual(h_u, cost_min + h_v + 1e-9)


class LegacyAStarTests(TestCase):
    """El A* del grafo viejo sigue dando el mismo costo que Dijkstra."""

    def setUp(self):
        def dept(code, name, lat, lon):
            return Department.objects.create(
                code=code, name=name, latitude=Decimal(str(lat)), longitude=Decimal(str(lon))
            )

        self.gua = dept("GUA", "Guatemala", 14.634915, -90.506882)
        self.chi = dept("CHI", "Chimaltenango", 14.661111, -90.820000)
        self.esc = dept("ESC", "Escuintla", 14.305000, -90.785000)
        self.que = dept("QUE", "Quetzaltenango", 14.845500, -91.518000)
        for origin, destination, km in [
            (self.gua, self.chi, "55"),
            (self.chi, self.que, "173"),
            (self.gua, self.esc, "64"),
            (self.esc, self.que, "210"),
        ]:
            RouteConnection.objects.create(origin=origin, destination=destination, distance_km=Decimal(km))

    def test_astar_matches_dijkstra(self):
        for origin in (self.gua, self.chi, self.esc, self.que):
            for destination in (self.gua, self.chi, self.esc, self.que):
                d_path, d_cost = RouteOptimizer.shortest_path(origin.id, destination.id)
                a_path, a_cost = AStarOptimizer.shortest_path(origin.id, destination.id)
                self.assertEqual(a_cost, d_cost)
                self.assertEqual(a_path, d_path)
