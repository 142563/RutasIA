import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .domain.services import GreedyOptimizer, invalidate_route_cache
from .models import Department, Order, RouteConnection, Trip, UserProfile, Vehicle
from .services import AStarOptimizer, PlanningError, RouteOptimizer, TripPlanner


class RouteOptimizerTests(TestCase):
    def setUp(self):
        # El grafo se cachea 120 s; sin limpiar, un test arrastra el grafo de otro.
        invalidate_route_cache()
        self.gua = Department.objects.create(code="GUA", name="Guatemala")
        self.esc = Department.objects.create(code="ESC", name="Escuintla")
        self.que = Department.objects.create(code="QUE", name="Quetzaltenango")
        RouteConnection.objects.create(
            origin=self.gua,
            destination=self.esc,
            distance_km=Decimal("64"),
            is_bidirectional=True,
        )
        RouteConnection.objects.create(
            origin=self.esc,
            destination=self.que,
            distance_km=Decimal("160"),
            is_bidirectional=True,
        )

    def tearDown(self):
        invalidate_route_cache()

    def test_shortest_path_returns_route_and_distance(self):
        path, distance = RouteOptimizer.shortest_path(self.gua.id, self.que.id)
        self.assertEqual(path, [self.gua.id, self.esc.id, self.que.id])
        self.assertEqual(distance, Decimal("224.00"))


class AlgorithmComparisonTests(TestCase):
    """Cubren el Objetivo Especifico 1: comparar algoritmos por distancia,
    tiempo de procesamiento y reduccion frente a la planificacion convencional.

    La red reproduce el caso Guatemala -> Suchitepequez de la base real: existe
    un desvio corto hacia el noroeste (Chimaltenango/Quetzaltenango) que atrae a
    la heuristica voraz porque acerca en linea recta, pero que por carretera es
    mucho mas largo que bajar por Escuintla.
    """

    def setUp(self):
        invalidate_route_cache()
        coords = {
            "GUA": ("14.634915", "-90.506882"),
            "CHI": ("14.661111", "-90.820000"),
            "QUE": ("14.845500", "-91.518000"),
            "RET": ("14.536111", "-91.677778"),
            "SUC": ("14.534000", "-91.363000"),
            "ESC": ("14.305000", "-90.785000"),
        }
        self.depts = {
            code: Department.objects.create(
                code=code, name=code, latitude=Decimal(lat), longitude=Decimal(lng)
            )
            for code, (lat, lng) in coords.items()
        }
        edges = [
            ("GUA", "CHI", "55"), ("CHI", "QUE", "173"), ("QUE", "RET", "62"),
            ("RET", "SUC", "47"), ("GUA", "ESC", "64"), ("ESC", "SUC", "101"),
        ]
        for origin, destination, distance in edges:
            RouteConnection.objects.create(
                origin=self.depts[origin],
                destination=self.depts[destination],
                distance_km=Decimal(distance),
                is_bidirectional=True,
            )

    def tearDown(self):
        invalidate_route_cache()

    def test_dijkstra_and_astar_agree_on_the_optimal_distance(self):
        origin, destination = self.depts["GUA"].id, self.depts["SUC"].id
        dijkstra = RouteOptimizer.search(origin, destination)
        astar = AStarOptimizer.search(origin, destination)
        self.assertEqual(dijkstra.distance, astar.distance)
        self.assertEqual(dijkstra.path, astar.path)
        self.assertEqual(dijkstra.distance, Decimal("165.00"))

    def test_astar_never_explores_more_nodes_than_dijkstra(self):
        # La heuristica Haversine es admisible, asi que A* no puede expandir mas
        # nodos que Dijkstra sobre el mismo grafo.
        for origin in self.depts.values():
            for destination in self.depts.values():
                if origin.id == destination.id:
                    continue
                with self.subTest(origin=origin.code, destination=destination.code):
                    dijkstra = RouteOptimizer.search(origin.id, destination.id)
                    astar = AStarOptimizer.search(origin.id, destination.id)
                    self.assertLessEqual(astar.explored, dijkstra.explored)

    def test_greedy_baseline_is_never_shorter_than_the_optimum(self):
        for origin in self.depts.values():
            for destination in self.depts.values():
                if origin.id == destination.id:
                    continue
                with self.subTest(origin=origin.code, destination=destination.code):
                    optimal = RouteOptimizer.search(origin.id, destination.id)
                    greedy = GreedyOptimizer.search(origin.id, destination.id)
                    self.assertGreaterEqual(greedy.distance, optimal.distance)

    def test_greedy_takes_the_long_way_to_suchitepequez(self):
        # Es el caso que sostiene el porcentaje de reduccion de la hipotesis.
        origin, destination = self.depts["GUA"].id, self.depts["SUC"].id
        greedy = GreedyOptimizer.search(origin, destination)
        optimal = RouteOptimizer.search(origin, destination)
        self.assertEqual(greedy.distance, Decimal("337.00"))
        reduction = (greedy.distance - optimal.distance) / greedy.distance * 100
        self.assertGreater(reduction, 15)

    def test_search_reports_processing_metrics(self):
        result = RouteOptimizer.search(self.depts["GUA"].id, self.depts["SUC"].id)
        self.assertEqual(result.visited_order[0], self.depts["GUA"].id)
        self.assertEqual(result.explored, len(result.visited_order))
        self.assertGreaterEqual(result.frontier_peak, 1)
        self.assertGreater(result.elapsed_ms, 0)

    def test_compare_endpoint_returns_the_three_algorithms(self):
        user = User.objects.create_user(username="lab", password="lab-pass-123")
        UserProfile.objects.create(user=user, role=UserProfile.Role.ADMIN)
        self.client.force_login(user)

        response = self.client.post(
            reverse("api-compare-routes"),
            data=json.dumps({
                "origin_id": self.depts["GUA"].id,
                "destination_id": self.depts["SUC"].id,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        results = response.json()["comparison"]["results"]
        self.assertEqual([item["key"] for item in results], ["greedy", "dijkstra", "astar"])

        baseline = results[0]
        self.assertTrue(baseline["is_baseline"])
        self.assertEqual(baseline["reduction_pct"], 0.0)
        for item in results[1:]:
            self.assertGreater(item["reduction_pct"], 15)
            self.assertEqual(item["explored"], len(item["visited_order"]))


class TripPlanningApiTests(TestCase):
    def setUp(self):
        # /api/trips/plan/ exige sesion iniciada y rol admin o supervisor:
        # sin esto la vista responde 302 hacia el login.
        self.user = User.objects.create_user(username="tester", password="test-pass-123")
        UserProfile.objects.create(user=self.user, role=UserProfile.Role.ADMIN)
        self.client.force_login(self.user)

        self.gua = Department.objects.create(code="GUA", name="Guatemala")
        self.esc = Department.objects.create(code="ESC", name="Escuintla")
        self.que = Department.objects.create(code="QUE", name="Quetzaltenango")
        RouteConnection.objects.create(
            origin=self.gua,
            destination=self.esc,
            distance_km=Decimal("64"),
            is_bidirectional=True,
        )
        RouteConnection.objects.create(
            origin=self.esc,
            destination=self.que,
            distance_km=Decimal("160"),
            is_bidirectional=True,
        )
        self.vehicle = Vehicle.objects.create(
            plate="C-111AAA",
            model="Isuzu NPR",
            capacity_kg=Decimal("2500"),
            fuel_efficiency_km_l=Decimal("6.20"),
            cost_per_km=Decimal("4.10"),
            is_active=True,
            current_department=self.gua,
        )
        self.order_1 = Order.objects.create(
            origin=self.gua,
            destination=self.que,
            weight_kg=Decimal("700"),
            package_count=10,
            priority=Order.Priority.NORMAL,
            status=Order.Status.PENDING,
        )
        self.order_2 = Order.objects.create(
            origin=self.gua,
            destination=self.que,
            weight_kg=Decimal("600"),
            package_count=8,
            priority=Order.Priority.HIGH,
            status=Order.Status.PENDING,
        )

    def test_plan_trip_api_creates_trip_and_assigns_orders(self):
        response = self.client.post(
            reverse("api-plan-trip"),
            data=json.dumps(
                {
                    "vehicle_id": self.vehicle.id,
                    "order_ids": [self.order_1.id, self.order_2.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        trip = Trip.objects.get()
        self.assertEqual(trip.status, Trip.Status.PLANNED)
        self.assertEqual(trip.orders.count(), 2)
        self.order_1.refresh_from_db()
        self.order_2.refresh_from_db()
        self.assertEqual(self.order_1.status, Order.Status.ASSIGNED)
        self.assertEqual(self.order_2.status, Order.Status.ASSIGNED)

    def test_plan_trip_records_the_requested_algorithm(self):
        response = self.client.post(
            reverse("api-plan-trip"),
            data=json.dumps({
                "vehicle_id": self.vehicle.id,
                "order_ids": [self.order_1.id],
                "algorithm": "astar",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["trip"]["algorithm"], "astar")

        trip = Trip.objects.get()
        self.assertEqual(trip.algorithm, Trip.Algorithm.ASTAR)
        # El evento del viaje deja constancia para la bitacora de la defensa.
        self.assertIn("A*", trip.events.first().note)

    def test_plan_trip_rejects_an_unknown_algorithm(self):
        response = self.client.post(
            reverse("api-plan-trip"),
            data=json.dumps({
                "vehicle_id": self.vehicle.id,
                "order_ids": [self.order_1.id],
                "algorithm": "genetico",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Trip.objects.exists())

    def test_trip_planner_validates_capacity(self):
        self.vehicle.capacity_kg = Decimal("900")
        self.vehicle.save(update_fields=["capacity_kg"])
        with self.assertRaisesMessage(PlanningError, "excede la capacidad"):
            TripPlanner.plan_trip(self.vehicle, Order.objects.filter(id__in=[self.order_1.id, self.order_2.id]))

# Create your tests here.
