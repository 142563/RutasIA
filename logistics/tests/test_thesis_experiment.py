"""Experimento de la tesis: convencional (proximidad sucesiva) vs. genético, 3 escenarios × 10."""
import unittest
from datetime import datetime

from django.test import SimpleTestCase

from logistics.routing import thesis_experiment as tx
from logistics.routing.build import estimated_graph_from_seed
from logistics.routing.seed_data import NODES
from logistics.routing.traffic import GT_TZ
from logistics.tests.test_search import random_multipliers

try:
    import scipy  # noqa: F401
    HAS_SCIPY = True
except ImportError:  # pragma: no cover
    HAS_SCIPY = False


class ThesisExperimentTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = estimated_graph_from_seed()
        cls.g = estimated_graph_from_seed(random_multipliers(base.edge_count))
        cls.departments = {n.code: n.department for n in NODES}
        cls.rows, cls.baseline = tx.run(cls.g, cls.departments, seed=7)

    def test_thirty_pairs_ten_per_scenario_and_band_split(self):
        self.assertEqual(len(self.rows), 30)
        for scenario in tx.SCENARIOS:
            rows = [r for r in self.rows if r["escenario"] == scenario]
            self.assertEqual(len(rows), 10)
            bands = [r["franja"] for r in rows]
            self.assertEqual((bands.count("pico matutino"), bands.count("valle"), bands.count("pico vespertino")),
                             (4, 3, 3))

    def test_same_points_in_every_scenario(self):
        for rep in range(1, 11):
            corridors = {r["corredor"] for r in self.rows if r["repeticion"] == rep}
            self.assertEqual(len(corridors), 1)
        self.assertEqual(len({r["corredor"] for r in self.rows}), 3)

    def test_units_and_reduction_formula(self):
        for r in self.rows:
            self.assertIsInstance(r["convencional_min"], int)
            self.assertEqual(r["convencional_km"], round(r["convencional_km"], 2))
            expected = (r["convencional_km"] - r["optimizada_km"]) / r["convencional_km"] * 100
            self.assertAlmostEqual(r["reduccion_km_pct"], expected, delta=0.02)
            self.assertLess(r["tiempo_respuesta_s"], 30)

    def test_closure_finds_alternative_and_congestion_only_slows(self):
        for r in self.rows:
            if r["escenario"] == "cierre":
                self.assertTrue(r["ruta_alterna_exitosa"])
                self.assertIn("->", r["tramo_cerrado"])
        normal = {r["repeticion"]: r for r in self.rows if r["escenario"] == "normal"}
        for r in self.rows:
            if r["escenario"] == "congestion":
                # Misma ruta convencional (no ve el tráfico): mismos km, igual o más minutos
                self.assertEqual(r["convencional_km"], normal[r["repeticion"]]["convencional_km"])
                self.assertGreaterEqual(r["convencional_min_exacto"], normal[r["repeticion"]]["convencional_min_exacto"])

    def test_reproducible_with_same_seed(self):
        again, _ = tx.run(self.g, self.departments, seed=7, repetitions=3)
        for a, b in zip(again, self.rows[:3]):
            self.assertEqual({k: v for k, v in a.items() if "respuesta" not in k and "alterna_s" not in k},
                             {k: v for k, v in b.items() if "respuesta" not in k and "alterna_s" not in k})

    def test_conventional_is_successive_geographic_proximity(self):
        depot = self.g.node_index(tx.DEPOT)
        stops = [self.g.node_index(c) for c in ("escuintla", "antigua-guatemala", "mazatenango")]
        self.assertEqual([self.g.codes[stops[i]] for i in tx.conventional_order(self.g, depot, stops)],
                         ["antigua-guatemala", "escuintla", "mazatenango"])

    def test_graph_variants_do_not_touch_the_original(self):
        road = tx.main_road(self.g, tx.CORRIDORS[0])
        before = list(self.g.multipliers[("peak_am", "weekday")])
        congested = tx.congested(self.g, road)
        self.assertEqual(self.g.multipliers[("peak_am", "weekday")], before)
        e = road[0]
        self.assertAlmostEqual(congested.multipliers[("peak_am", "weekday")][e], before[e] * 2.5)
        closed = tx.closed(self.g, road[:1])
        self.assertEqual(closed.edge_count, self.g.edge_count - 2)  # ambos sentidos

    def test_avoids_unpaved_roads_like_the_app(self):
        """Regla de la app: la terracería se evita por defecto; el experimento hace lo mismo."""
        self.assertTrue(tx.AVOID_UNPAVED)
        departure = datetime(2026, 10, 13, 8, 0, tzinfo=GT_TZ)
        depot = self.g.node_index(tx.DEPOT)
        stops = tx.instance_stops(self.g, self.departments, tx.CORRIDORS[0], 0, 7)
        plan, _ = tx.optimized_plan(self.g, depot, stops, departure)
        self.assertIn("convencional_km_terraceria", self.rows[0])
        self.assertGreaterEqual(plan.total_km, 0)

    @unittest.skipUnless(HAS_SCIPY, "SciPy está en requirements-dev.txt")
    def test_statistics_report(self):
        report = tx.statistics_report(self.rows, self.baseline, [{"tiempo_respuesta_s": 1.0}])
        self.assertEqual(report["pares"], 30)
        for metric in ("distancia_km", "tiempo_min"):
            block = report["total"][metric]
            self.assertIn(block["prueba"], ("t pareada", "Wilcoxon", "sin variación"))
            self.assertIsNotNone(block["shapiro_p"])
        self.assertEqual(report["ruta_alternativa"]["exito_pct"], 100.0)
        rule = report["h0_distancia"]["rechazada"]
        km = report["total"]["distancia_km"]
        self.assertEqual(rule, km["significativo"] and km["reduccion_media_pct"] >= 15)

    @unittest.skipUnless(HAS_SCIPY, "SciPy está en requirements-dev.txt")
    def test_paired_test_on_known_data(self):
        conv = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
        opt = [80, 85, 99, 101, 110, 121, 130, 140, 141, 150]
        result = tx._paired_test(conv, opt)
        self.assertTrue(result["significativo"])
        self.assertGreater(result["d_cohen"], 1)
        self.assertGreater(result["reduccion_media_pct"], 15)
