"""Día 5: run_experiments genera los CSV de E1, E2, E3, E5 y E7."""
import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from logistics.routing.astar import astar
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.dijkstra import dijkstra
from logistics.routing.graph import invalidate_graph
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
