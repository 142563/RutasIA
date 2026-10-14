"""Algoritmo genético para el orden de visita (tesis, Cap. III: motor principal)."""
import itertools
import json
import random
import time
from datetime import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from logistics.application.routing import get_graph, optimizer_params
from logistics.models import Depot, Driver, OptimizerSettings, Order, Route, UserProfile, Vehicle
from logistics.routing import genetic
from logistics.routing.build import build_estimated, estimated_graph_from_seed
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.genetic import GeneticParams, fast_two_opt, mutate, ordered_crossover, solve, tour_cost
from logistics.routing.graph import TIME, invalidate_graph
from logistics.routing.multistop import nearest_neighbor, plan_multistop, route_cost, time_matrix, two_opt
from logistics.routing.traffic import GT_TZ


def random_matrix(n: int, seed: int) -> list[list[float]]:
    """Matriz asimétrica (como la del grafo dirigido): distancia euclidiana × factor por sentido."""
    rng = random.Random(seed)
    pts = [(rng.random() * 100, rng.random() * 100) for _ in range(n)]
    return [[0.0 if i == j else ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) ** 0.5
             * (1 + rng.random() * 0.5) for j in range(n)] for i in range(n)]


class GeneticOperatorTests(SimpleTestCase):
    def test_crossover_and_mutation_keep_valid_permutations(self):
        rng = random.Random(1)
        genes = list(range(1, 21))
        for _ in range(500):
            a, b = genes[:], genes[:]
            rng.shuffle(a)
            rng.shuffle(b)
            child = ordered_crossover(a, b, rng)
            self.assertEqual(sorted(child), genes)
            mutate(child, rng)
            self.assertEqual(sorted(child), genes)

    def test_fast_two_opt_matches_cost_and_never_worsens(self):
        for seed in range(20):
            m = random_matrix(12, seed)
            start = list(range(1, 12))
            random.Random(seed).shuffle(start)
            for back in (False, True):
                out = fast_two_opt(start, m, back)
                self.assertEqual(sorted(out), list(range(1, 12)))
                self.assertLessEqual(tour_cost(out, m, back), tour_cost(start, m, back) + 1e-9)
                # Óptimo local: el 2-opt de referencia ya no lo mejora
                self.assertAlmostEqual(route_cost(two_opt(out, m, back), m, back), tour_cost(out, m, back), places=6)

    def test_finds_brute_force_optimum_with_8_stops(self):
        for seed in range(15):
            m = random_matrix(9, seed)
            for back in (False, True):
                best = min(tour_cost(p, m, back) for p in itertools.permutations(range(1, 9)))
                self.assertAlmostEqual(solve(m, return_to_depot=back).cost, best, places=6, msg=(seed, back))

    def test_never_worse_than_nearest_neighbor_or_its_seeds(self):
        for seed in range(10):
            m = random_matrix(25, seed)
            nn = nearest_neighbor(m)
            nn2 = two_opt(nn, m, True)
            result = solve(m, GeneticParams(generations=30), True, seeds=[nn2])
            self.assertLessEqual(result.cost, route_cost(nn, m, True) + 1e-9)
            self.assertLessEqual(result.cost, route_cost(nn2, m, True) + 1e-9)
            self.assertAlmostEqual(result.cost, tour_cost(result.order, m, True), places=9)

    def test_same_seed_same_result(self):
        m = random_matrix(30, 3)
        a, b = solve(m, GeneticParams(seed=11)), solve(m, GeneticParams(seed=11))
        self.assertEqual(a.order, b.order)
        self.assertEqual(a.history, b.history)

    def test_history_never_increases_and_stops_by_stall(self):
        result = solve(random_matrix(15, 5), GeneticParams(stall_generations=5, generations=1000))
        self.assertEqual(result.history, sorted(result.history, reverse=True))
        self.assertEqual(result.stop_reason, "stall")
        self.assertLess(result.generations, 1000)

    def test_trivial_instances(self):
        self.assertEqual(solve([[0.0]]).order, [])
        self.assertEqual(solve([[0, 5], [5, 0]]).order, [1])
        self.assertEqual(solve([[0, 9, 1], [1, 0, 1], [1, 2, 0]]).order, [2, 1])

    def test_fifty_stops_well_under_thirty_seconds(self):
        """Tesis: tiempo de respuesta < 30 s con el máximo de 50 paradas."""
        started = time.perf_counter()
        result = solve(random_matrix(51, 9), return_to_depot=True)
        self.assertLess(time.perf_counter() - started, 30)
        self.assertEqual(sorted(result.order), list(range(1, 51)))

    def test_params_are_clamped(self):
        p = GeneticParams(population=1, generations=0, tournament=99, crossover_rate=3, mutation_rate=-1).clamped()
        self.assertEqual((p.population, p.generations, p.tournament, p.crossover_rate, p.mutation_rate),
                         (4, 1, 10, 1.0, 0.0))


class GeneticPlanTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.g = estimated_graph_from_seed()
        cls.depot = cls.g.node_index("ciudad-guatemala")

    def test_plan_multistop_uses_genetic_by_default_and_never_loses_to_two_opt(self):
        rng = random.Random(4)
        for _ in range(8):
            stops = rng.sample([i for i in range(self.g.node_count) if i != self.depot], 12)
            plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 7, 30, tzinfo=GT_TZ),
                                  return_to_depot=True)
            self.assertEqual(plan.optimizer, "genetic")
            self.assertLessEqual(plan.optimized_minutes, plan.two_opt_minutes + 1e-9)
            self.assertLessEqual(plan.two_opt_minutes, plan.nearest_neighbor_minutes + 1e-9)
            self.assertGreaterEqual(plan.optimize_ms, 0)
            self.assertEqual(sorted(plan.order), list(range(12)))

    def test_nn2opt_still_available(self):
        stops = [self.g.node_index(c) for c in ("quetzaltenango", "escuintla", "coban")]
        plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 10, 0, tzinfo=GT_TZ),
                              optimizer="nn2opt")
        self.assertEqual(plan.optimizer, "nn2opt")
        self.assertAlmostEqual(plan.optimized_minutes, plan.two_opt_minutes)
        with self.assertRaises(ValueError):
            plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 10, 0, tzinfo=GT_TZ), optimizer="x")

    def test_matrix_comes_from_dijkstra_with_the_band(self):
        """El genético ordena sobre la matriz de Dijkstra; los costos coinciden con time_matrix."""
        stops = [self.g.node_index(c) for c in ("antigua-guatemala", "escuintla", "mazatenango", "retalhuleu")]
        departure = datetime(2026, 10, 6, 7, 30, tzinfo=GT_TZ)
        plan = plan_multistop(self.g, self.depot, stops, departure)
        from logistics.routing.traffic import profile_for
        band, day = profile_for(departure)
        matrix, _ = time_matrix(self.g, self.g.weights(TIME, band, day), [self.depot, *stops])
        self.assertAlmostEqual(plan.optimized_minutes, route_cost([i + 1 for i in plan.order], matrix), places=6)


class GeneticApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        invalidate_graph()
        call_command("seed_demo_data", stdout=StringIO())
        cls.depot = Depot.objects.get(name="Bodega Central")
        cls.user = User.objects.create_user(username="despachador", password="clave-segura-123")
        UserProfile.objects.create(user=cls.user, role=UserProfile.Role.DISPATCHER)

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.user)

    def post(self, name, payload):
        return self.client.post(reverse(name), json.dumps(payload), content_type="application/json")

    def test_settings_default_and_admin_values(self):
        self.assertEqual(optimizer_params(), GeneticParams())
        OptimizerSettings.objects.create(population=40, generations=99, seed=7, mutation_rate=5)
        params = optimizer_params()
        self.assertEqual((params.population, params.generations, params.seed, params.mutation_rate), (40, 99, 7, 1.0))
        OptimizerSettings(population=10).save()  # siempre la misma fila
        self.assertEqual(OptimizerSettings.objects.count(), 1)

    def test_optimize_endpoint_reports_genetic_and_response_time_with_50_stops(self):
        codes = [c for c in get_graph().codes if c != "ciudad-guatemala"]
        stops = (codes * 2)[:50]
        response = self.post("api-routes-optimize", {"depot": "ciudad-guatemala", "stops": stops,
                                                     "departure": "2026-10-06T07:30", "return_to_depot": True})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["plan"]["optimizer"], "genetic")
        self.assertLess(data["response_seconds"], 30)
        self.assertLessEqual(data["plan"]["baseline"]["optimized_minutes"],
                             data["plan"]["baseline"]["two_opt_minutes"] + 1e-6)

    def test_optimize_endpoint_rejects_unknown_optimizer(self):
        response = self.post("api-routes-optimize", {"depot": "ciudad-guatemala", "stops": ["escuintla"],
                                                     "optimizer": "magia"})
        self.assertEqual(response.status_code, 400)

    def test_planner_and_saved_route_use_genetic(self):
        ids = list(Order.objects.filter(is_demo=True, status=Order.Status.PENDING).order_by("id")
                   .values_list("id", flat=True)[:6])
        data = self.post("api-v2-routes-plan", {"depot_id": self.depot.id, "order_ids": ids,
                                                "departure": "2026-10-06T07:30"}).json()
        self.assertEqual(data["fastest"]["optimizer"], "genetic")
        self.assertEqual(data["shortest"]["optimizer"], "genetic")
        self.assertLess(data["response_seconds"], 30)
        driver = Driver.objects.first()
        vehicle = Vehicle.objects.filter(capacity_kg__gte=500).first()
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": ids,
                                               "departure": "2026-10-06T07:30", "criterion": "time",
                                               "driver_id": driver.id, "vehicle_id": vehicle.id})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["route"]["optimizer"], "genetic")
        self.assertEqual(Route.objects.get().optimizer, "genetic")


class GeneticModuleTests(SimpleTestCase):
    def test_engine_uses_only_standard_library(self):
        """Regla del motor: implementación propia, sin librerías de ruteo ni de optimización."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(genetic))
        imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertLessEqual(imported, {"__future__", "random", "time", "dataclasses", "typing"})
