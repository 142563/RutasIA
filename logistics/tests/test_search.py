"""Día 3: Dijkstra y A*. Incluye E1: costo(A*) == costo(Dijkstra) en todos los pares y franjas."""
import math
import random

from django.test import SimpleTestCase

from logistics.models import DayType, TrafficBand
from logistics.routing.astar import VMAX_SAFETY, astar, compute_v_max, heuristic
from logistics.routing.build import estimated_graph_from_seed
from logistics.routing.dijkstra import dijkstra, dijkstra_all
from logistics.routing.graph import DISTANCE, TIME, RoadGraph
from logistics.routing.instrument import INF

PROFILES = [(band, day) for band in TrafficBand.values for day in DayType.values]  # 14


def random_multipliers(edge_count: int, seed: int = 2026) -> dict:
    """14 perfiles con m ∈ [1, 2.5] por arista (semilla fija: prueba reproducible)."""
    rng = random.Random(seed)
    return {profile: [rng.uniform(1.0, 2.5) for _ in range(edge_count)] for profile in PROFILES}


def same_cost(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


class SmallGraphTests(SimpleTestCase):
    """Grafo a mano:  a --10--> b --10--> d   y   a --25--> d  (directo pero más lento).

    d --5--> a es la única arista de regreso (grafo dirigido). e no tiene aristas.
    """

    def setUp(self):
        self.g = RoadGraph.from_lists(
            nodes=[("a", "A", 14.60, -90.50), ("b", "B", 14.65, -90.60), ("d", "D", 14.70, -90.70),
                   ("e", "E", 15.50, -89.50)],
            edges=[("a", "b", 12, 10.0), ("b", "d", 12, 10.0), ("a", "d", 22, 25.0), ("d", "a", 22, 5.0)],
        )
        self.a, self.b, self.d, self.e = (self.g.node_index(c) for c in "abde")
        self.w = self.g.weights(TIME)

    def test_both_find_the_cheaper_detour(self):
        for search in (dijkstra, astar):
            r = search(self.g, self.w, self.a, self.d)
            self.assertEqual(r.cost, 20.0, search.__name__)
            self.assertEqual(r.path_codes(self.g), ["a", "b", "d"])
            self.assertEqual(r.total(self.g.km), 24)

    def test_distance_criterion_prefers_direct_road(self):
        w = self.g.weights(DISTANCE)
        self.assertEqual(dijkstra(self.g, w, self.a, self.d).path_codes(self.g), ["a", "d"])
        self.assertEqual(astar(self.g, w, self.a, self.d).path_codes(self.g), ["a", "d"])

    def test_directed_graph_return_trip_differs(self):
        self.assertEqual(dijkstra(self.g, self.w, self.d, self.a).cost, 5.0)
        self.assertEqual(dijkstra(self.g, self.w, self.b, self.a).cost, 15.0)  # b -> d -> a

    def test_source_equals_target(self):
        for search in (dijkstra, astar):
            r = search(self.g, self.w, self.b, self.b)
            self.assertEqual((r.cost, r.path, r.expanded), (0.0, [self.b], 1))

    def test_unreachable_target(self):
        for search in (dijkstra, astar):
            r = search(self.g, self.w, self.a, self.e)
            self.assertFalse(r.found)
            self.assertEqual((r.cost, r.path), (INF, []))

    def test_instrumentation(self):
        r = dijkstra(self.g, self.w, self.a, self.d, record_order=True)
        self.assertEqual(r.order[0], self.a)
        self.assertEqual(r.order[-1], self.d)
        self.assertEqual(len(r.order), r.expanded)
        self.assertGreaterEqual(r.pushed, r.expanded)
        self.assertGreaterEqual(r.elapsed_ms, 0)

    def test_v_max_bounds_every_edge(self):
        v_max = compute_v_max(self.g, self.w)
        for e, w in enumerate(self.w):
            self.assertLessEqual(self.g.straight_km(self.g.edge_from[e], self.g.edge_to[e]) / v_max, w)


class NationalGraphTests(SimpleTestCase):
    """Grafo semilla (108 nodos, 260 aristas) con km/minutos estimados y tráfico aleatorio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = estimated_graph_from_seed()
        cls.g = estimated_graph_from_seed(random_multipliers(base.edge_count))

    def all_weights(self):
        yield ("sin tráfico", None), self.g.weights(TIME)
        for band, day in PROFILES:
            yield (band, day), self.g.weights(TIME, band, day)
        yield ("km", None), self.g.weights(DISTANCE)

    def test_e1_astar_equals_dijkstra_all_pairs_all_profiles(self):
        """E1 (obligatoria, CLAUDE.md): 108 × 107 pares × 14 franjas (+ sin tráfico + km)."""
        n = self.g.node_count
        checked = 0
        for profile, w in self.all_weights():
            v_max = compute_v_max(self.g, w)
            for s in range(n):
                tree = dijkstra_all(self.g, w, s)
                for t in range(n):
                    if t == s:
                        continue
                    a = astar(self.g, w, s, t, v_max=v_max)
                    if not same_cost(a.cost, tree.dist[t]):
                        self.fail(f"{profile}: {self.g.codes[s]}->{self.g.codes[t]} "
                                  f"A*={a.cost} Dijkstra={tree.dist[t]}")
                    checked += 1
        self.assertEqual(checked, 16 * n * (n - 1))

    def test_heuristic_is_consistent_on_every_edge_and_target(self):
        """h(u) ≤ w(u, v) + h(v) para toda arista, todo destino y todo perfil."""
        for profile, w in self.all_weights():
            v_max = compute_v_max(self.g, w)
            for t in range(self.g.node_count):
                h = [heuristic(self.g, i, t, v_max) for i in range(self.g.node_count)]
                for e, weight in enumerate(w):
                    u, v = self.g.edge_from[e], self.g.edge_to[e]
                    self.assertLessEqual(h[u], weight + h[v], f"{profile} arista {e} destino {t}")

    def test_v_max_has_float_safety_margin(self):
        w = self.g.weights(TIME)
        raw = max(self.g.straight_km(self.g.edge_from[e], self.g.edge_to[e]) / x for e, x in enumerate(w))
        self.assertEqual(compute_v_max(self.g, w), raw * (1 + VMAX_SAFETY))

    def test_one_to_all_matches_point_to_point(self):
        w = self.g.weights(TIME, TrafficBand.PEAK_AM, DayType.WEEKDAY)
        s = self.g.node_index("ciudad-guatemala")
        tree = dijkstra_all(self.g, w, s)
        for t in range(self.g.node_count):
            point = dijkstra(self.g, w, s, t)
            self.assertTrue(same_cost(point.cost, tree.dist[t]))
            self.assertEqual(tree.path_to(self.g, t)[0], point.path)

    def test_astar_explores_fewer_nodes_than_dijkstra(self):
        w = self.g.weights(TIME)
        s, t = self.g.node_index("ciudad-guatemala"), self.g.node_index("flores")
        d, a = dijkstra(self.g, w, s, t), astar(self.g, w, s, t)
        self.assertTrue(same_cost(d.cost, a.cost))
        self.assertEqual(d.path, a.path)
        self.assertLess(a.expanded, d.expanded)

        total_a = total_d = 0
        for s in range(0, self.g.node_count, 7):
            for t in range(0, self.g.node_count, 5):
                total_a += astar(self.g, w, s, t).expanded
                total_d += dijkstra(self.g, w, s, t).expanded
        self.assertLess(total_a, total_d)

    def test_inadmissible_heuristic_breaks_optimality(self):
        """Contraejemplo: con un v_max inventado (3 veces menor), h sobreestima y A* falla.

        Por eso v_max se DERIVA de los datos y no se elige a ojo.
        """
        w = self.g.weights(TIME)
        bad_v_max = compute_v_max(self.g, w) / 3
        worse = 0
        for s in range(self.g.node_count):
            tree = dijkstra_all(self.g, w, s)
            for t in range(self.g.node_count):
                if astar(self.g, w, s, t, v_max=bad_v_max).cost > tree.dist[t] * (1 + 1e-9):
                    worse += 1
        self.assertGreater(worse, 0)
