"""Día 5: run_experiments genera los CSV de E1, E2, E3, E5 y E7."""
import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from logistics.models import DayType, TrafficBand
from logistics.routing import experiments
from logistics.routing.astar import astar
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.dijkstra import dijkstra
from logistics.routing.google import MatrixElement
from logistics.routing.graph import RoadGraph, invalidate_graph, load_graph
from logistics.routing.synthetic import geometric_graph, grid_graph


class SyntheticGraphTests(SimpleTestCase):
    def test_grid_is_directed_4_neighbors(self):
        g = grid_graph(100)
        self.assertEqual(g.node_count, 100)
        self.assertEqual(g.edge_count, 2 * 2 * 10 * 9)  # 180 tramos, dos sentidos

    def test_astar_matches_dijkstra_on_synthetic_graphs(self):
        for g in (grid_graph(900), geometric_graph(900)):
            w = g.weights()
            for s, t in ((0, g.node_count - 1), (5, 400), (123, 777)):
                d, a = dijkstra(g, w, s, t), astar(g, w, s, t)
                if d.found:
                    self.assertAlmostEqual(a.cost, d.cost, delta=1e-9 * d.cost)
                    self.assertLessEqual(a.expanded, d.expanded)


class RunExperimentsCommandTests(TestCase):
    def setUp(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        invalidate_graph()

    def test_quick_run_writes_all_csvs_with_data_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = StringIO()
            call_command("run_experiments", "--quick", "--no-charts", "--max-nodes", "2000", "--out", tmp, stdout=out)
            text = out.getvalue()
            self.assertIn("NO para el documento", text)
            self.assertIn("(100.00 %)", text)  # E1
            for name in ("e1_correctitud", "e2_eficiencia", "e3_impacto_trafico", "e5_varias_paradas",
                         "e7_escalabilidad"):
                path = Path(tmp) / f"{name}.csv"
                self.assertTrue(path.exists(), name)
                with path.open(encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                self.assertTrue(rows, name)
                self.assertIn("data_source", rows[0])

    def test_quick_run_includes_e6_and_skips_e4_without_google(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = StringIO()
            call_command("run_experiments", "--quick", "--no-charts", "--only", "e4", "e6", "--out", tmp, stdout=out)
            self.assertIn("E4 omitido", out.getvalue())
            self.assertTrue((Path(tmp) / "e6_hora_de_salida.csv").exists())
            self.assertFalse((Path(tmp) / "e4_precision.csv").exists())

    @override_settings(GOOGLE_ROUTES_API_KEY="")
    def test_e4_with_google_flag_but_no_key_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = StringIO()
            call_command("run_experiments", "--quick", "--no-charts", "--only", "e4", "--with-google", "--yes",
                         "--out", tmp, stdout=out)
            self.assertIn("E4 omitido", out.getvalue())
            self.assertIn("GOOGLE_ROUTES_API_KEY", out.getvalue())

    def test_e4_command_with_mocked_google_writes_csv_and_summary(self):
        client = FakeGoogle(minutes=300)
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
                "logistics.management.commands.run_experiments.RoutesClient", return_value=client):
            out = StringIO()
            call_command("run_experiments", "--quick", "--only", "e4", "--with-google", "--yes", "--out", tmp,
                         stdout=out)
            self.assertIn("MAPE global", out.getvalue())
            with (Path(tmp) / "e4_precision.csv").open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 8)
            self.assertIn("google_routes", rows[0]["data_source"])
            self.assertTrue((Path(tmp) / "e4_resumen.csv").exists())
            self.assertTrue((Path(tmp) / "e4_motor_vs_google.png").exists())


class FakeGoogle:
    """Cliente de Routes API falso: toda ruta dura `minutes` y mide 400 km. Cuenta las consultas."""

    def __init__(self, minutes: float):
        self.minutes = minutes
        self.requests_made = 0
        self.elements_requested = 0

    def compute_route_matrix(self, origins, destinations, departure_time=None, traffic=False):
        self.requests_made += 1
        self.elements_requested += len(origins) * len(destinations)
        return [MatrixElement(0, j, "", 400_000.0, self.minutes * 60, self.minutes * 60)
                for j in range(len(destinations))]


class E4PrecisionTests(TestCase):
    def setUp(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        invalidate_graph()
        self.graph = load_graph()
        self.trips = experiments.e4_trips(self.graph, count=10)

    def test_trips_are_reproducible_long_and_distinct(self):
        self.assertEqual(self.trips, experiments.e4_trips(self.graph, count=10))
        self.assertEqual(len(self.trips), 10)
        self.assertEqual(len({(t["origin"], t["destination"], t["band"], t["day_type"]) for t in self.trips}), 10)
        for t in self.trips:
            self.assertGreaterEqual(
                self.graph.straight_km(self.graph.index[t["origin"]], self.graph.index[t["destination"]]),
                experiments.E4_MIN_STRAIGHT_KM)

    def test_mape_matches_hand_computation(self):
        rows = experiments.e4_precision(self.graph, self.trips, client=FakeGoogle(minutes=300))
        self.assertEqual(len(rows), 10)
        for r in rows:
            self.assertAlmostEqual(r["error_pct"], abs(r["engine_min"] - 300) / 300 * 100, delta=0.02)
            self.assertAlmostEqual(r["abs_error_min"], abs(r["engine_min"] - 300), delta=0.02)
        summary = experiments.e4_summary(rows)
        self.assertEqual(summary[0]["group"], "global")
        self.assertAlmostEqual(summary[0]["mape_pct"], sum(r["error_pct"] for r in rows) / 10, delta=0.01)
        self.assertEqual(sum(s["trips"] for s in summary[1:]), 10)

    def test_summary_with_known_errors(self):
        rows = [{"band": "peak_am", "error_pct": 10.0, "signed_error_pct": 10.0, "data_source": "x"},
                {"band": "peak_am", "error_pct": 30.0, "signed_error_pct": -30.0, "data_source": "x"},
                {"band": "night", "error_pct": 20.0, "signed_error_pct": 20.0, "data_source": "x"}]
        by_group = {s["group"]: s for s in experiments.e4_summary(rows)}
        self.assertEqual(by_group["global"]["mape_pct"], 20.0)
        self.assertEqual(by_group["peak_am"]["mape_pct"], 20.0)
        self.assertEqual(by_group["peak_am"]["bias_pct"], -10.0)
        self.assertEqual(by_group["night"]["mape_pct"], 20.0)

    def test_cache_is_used_and_no_google_means_cache_only(self):
        self.assertEqual(experiments.e4_pending(self.trips), 10)
        self.assertEqual(experiments.e4_precision(self.graph, self.trips), [])  # sin caché ni cliente: nada
        first = FakeGoogle(minutes=300)
        experiments.e4_precision(self.graph, self.trips, client=first)
        self.assertGreater(first.requests_made, 0)
        self.assertEqual(experiments.e4_pending(self.trips), 0)
        second = FakeGoogle(minutes=999)
        rows = experiments.e4_precision(self.graph, self.trips, client=second)
        self.assertEqual(second.requests_made, 0)  # todo salió de RouteSample
        self.assertTrue(all(r["google_min"] == 300 for r in rows))
        self.assertEqual(len(experiments.e4_precision(self.graph, self.trips)), 10)  # sin cliente, con caché


class E6DepartureTimeTests(SimpleTestCase):
    def setUp(self):
        nodes = [("A", "A", 14.0, -90.0), ("B", "B", 14.5, -90.0), ("C", "C", 15.0, -90.0)]
        edges = [("A", "C", 100, 100), ("A", "B", 80, 60), ("B", "C", 80, 60)]  # directa vs desvío de 120 min
        multipliers = {(b, d): [1.0, 1.0, 1.0] for d in DayType.values for b in TrafficBand.values}
        multipliers[(TrafficBand.PEAK_AM, DayType.WEEKDAY)] = [2.0, 1.1, 1.1]
        multipliers[(TrafficBand.PEAK_PM, DayType.WEEKDAY)] = [1.5, 1.0, 1.0]
        self.graph = RoadGraph.from_lists(nodes, edges, multipliers, sources={"edges": "google_routes"})
        self.graph.roads = ["RN-1", "RN-2", "RN-2"]

    def rows(self):
        return {(r["band"], r["day_type"]): r
                for r in experiments.e6_departure_time(self.graph, pairs=[("A", "C")])}

    def test_curve_reflects_multipliers(self):
        rows = self.rows()
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[("night", "weekday")]["minutes"], 100)
        self.assertEqual(rows[("peak_pm", "weekday")]["minutes"], 120)  # min(150, 120): cambia al desvío
        self.assertAlmostEqual(rows[("peak_am", "weekday")]["minutes"], 132)  # min(200, 1.1 × 120)
        self.assertEqual(rows[("peak_am", "weekend")]["minutes"], 100)

    def test_peaks_are_the_slowest_and_roads_change(self):
        rows = self.rows()
        weekday = {b: rows[(b, "weekday")]["minutes"] for b in TrafficBand.values}
        self.assertEqual(max(weekday, key=weekday.get), "peak_am")
        self.assertGreater(weekday["peak_am"], weekday["night"])
        self.assertEqual(rows[("night", "weekday")]["route_roads"], "RN-1")
        self.assertEqual(rows[("peak_am", "weekday")]["route_roads"], "RN-2")

    def test_astar_equals_dijkstra_and_source_is_reported(self):
        for r in self.rows().values():
            self.assertTrue(r["same_cost_dijkstra"])
            self.assertEqual(r["data_source"], "edges=google_routes")
