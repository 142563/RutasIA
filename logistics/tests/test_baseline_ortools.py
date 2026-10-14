"""Línea base OR-Tools (solo experimentos). Se salta si OR-Tools no está instalado."""
import itertools
import unittest

from django.test import SimpleTestCase

from logistics.tests.test_genetic import random_matrix
from logistics.routing.genetic import tour_cost

try:
    import ortools  # noqa: F401
    HAS_ORTOOLS = True
except ImportError:  # pragma: no cover
    HAS_ORTOOLS = False


@unittest.skipUnless(HAS_ORTOOLS, "OR-Tools está en requirements-dev.txt")
class OrToolsBaselineTests(SimpleTestCase):
    def test_valid_and_optimal_on_small_instances(self):
        from logistics.routing.baseline_ortools import solve
        for seed in range(4):
            m = random_matrix(8, seed)
            for back in (False, True):
                best = min(tour_cost(p, m, back) for p in itertools.permutations(range(1, 8)))
                result = solve(m, back, time_limit_s=1)
                self.assertEqual(sorted(result.order), list(range(1, 8)))
                self.assertAlmostEqual(result.cost, tour_cost(result.order, m, back), places=9)
                self.assertLessEqual(result.cost, best * 1.001)

    def test_not_used_by_the_engine(self):
        """OR-Tools nunca se importa desde el motor ni la API (Render no lo instala)."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        for path in [*root.glob("routing/*.py"), *root.glob("application/**/*.py"), *root.glob("presentation/*.py")]:
            if path.name in ("baseline_ortools.py", "thesis_experiment.py"):
                continue
            self.assertNotIn("ortools", path.read_text(encoding="utf-8"), path)
