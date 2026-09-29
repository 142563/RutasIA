"""Día 5: varias paradas y endpoints del motor de rutas."""
import json
import random
from datetime import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from logistics.routing.build import build_estimated, estimated_graph_from_seed
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.graph import TIME, invalidate_graph
from logistics.routing.multistop import (
    nearest_neighbor, plan_multistop, route_cost, time_matrix, two_opt,
)
from logistics.routing.traffic import GT_TZ


class MultiStopTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.g = estimated_graph_from_seed()
        cls.depot = cls.g.node_index("ciudad-guatemala")

    def test_nearest_node_maps_address_to_graph(self):
        # Un punto en el centro de Xela se asocia al nodo Quetzaltenango
        self.assertEqual(self.g.codes[self.g.nearest_node(14.8340, -91.5190)], "quetzaltenango")

    def test_two_opt_never_worse_than_nearest_neighbor(self):
        rng = random.Random(7)
        w = self.g.weights(TIME)
        for _ in range(30):
            stops = rng.sample(range(self.g.node_count), 8)
            matrix, _ = time_matrix(self.g, w, [self.depot, *stops])
            nn = nearest_neighbor(matrix)
            for back in (False, True):
                self.assertLessEqual(route_cost(two_opt(nn, matrix, back), matrix, back),
                                     route_cost(nn, matrix, back) + 1e-9)

    def test_two_opt_fixes_a_crossing(self):
        # Orden de captura que va y viene: Xela, Chimaltenango, Retalhuleu
        codes = ["quetzaltenango", "chimaltenango", "retalhuleu"]
        stops = [self.g.node_index(c) for c in codes]
        plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 7, 0, tzinfo=GT_TZ))
        self.assertLess(plan.optimized_minutes, plan.capture_minutes)
        self.assertEqual([codes[i] for i in plan.order][0], "chimaltenango")

    def test_etas_increase_and_include_service_time(self):
        stops = [self.g.node_index(c) for c in ("antigua-guatemala", "escuintla", "mazatenango", "retalhuleu")]
        plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 6, 30, tzinfo=GT_TZ), service_min=15)
        self.assertEqual(len(plan.etas), 4)
        self.assertEqual(plan.etas, sorted(plan.etas))
        for previous, leg in zip(plan.legs, plan.legs[1:]):
            self.assertEqual((leg.depart_at - previous.arrive_at).total_seconds(), 15 * 60)
        self.assertEqual(plan.legs[0].depart_at, plan.departure)

    def test_each_leg_uses_the_band_when_it_starts(self):
        stops = [self.g.node_index(c) for c in ("quetzaltenango", "huehuetenango")]
        plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 6, 0, tzinfo=GT_TZ))
        self.assertEqual(plan.legs[0].band, "dawn")
        self.assertNotEqual(plan.legs[1].band, "dawn")  # sale después de las 07:00

    def test_return_to_depot_adds_final_leg(self):
        stops = [self.g.node_index("escuintla")]
        plan = plan_multistop(self.g, self.depot, stops, datetime(2026, 10, 6, 10, 0, tzinfo=GT_TZ),
                              return_to_depot=True)
        self.assertEqual(len(plan.legs), 2)
        self.assertEqual(plan.legs[-1].destination, self.depot)
        self.assertEqual(len(plan.etas), 1)


class RoutingApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        cls.user = User.objects.create_user(username="despachador", password="clave-de-prueba-123")

    def setUp(self):
        invalidate_graph()  # el grafo en memoria no debe venir de otra prueba
        self.client.force_login(self.user)

    def post(self, name, payload):
        return self.client.post(reverse(name), data=json.dumps(payload), content_type="application/json")

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api-routing-nodes")).status_code, 302)
        self.assertEqual(self.post("api-routing-compare", {}).status_code, 302)

    def test_nodes(self):
        data = self.client.get(reverse("api-routing-nodes")).json()
        self.assertEqual(len(data["nodes"]), 108)
        self.assertEqual(data["data_source"], {"edges": "estimate", "traffic": "synthetic"})

    def test_route_by_code_and_by_coordinates(self):
        data = self.post("api-routing-route", {
            "origin": "ciudad-guatemala", "destination": {"lat": 14.834, "lng": -91.519},
            "departure": "2026-10-06T07:30", "algorithm": "dijkstra",
        }).json()
        self.assertTrue(data["ok"])
        route = data["route"]
        self.assertEqual(route["nodes"][-1]["code"], "quetzaltenango")
        self.assertEqual(data["band"], "peak_am")
        self.assertGreater(route["minutes"], 0)
        self.assertGreater(route["expanded"], 0)

    def test_compare_same_cost_fewer_nodes(self):
        data = self.post("api-routing-compare", {
            "origin": "ciudad-guatemala", "destination": "flores", "departure": "2026-10-06T07:30",
        }).json()
        algorithms = data["algorithms"]
        self.assertTrue(algorithms["same_cost"])
        self.assertLess(algorithms["astar"]["expanded"], algorithms["dijkstra"]["expanded"])
        self.assertGreaterEqual(data["minutes_saved"], 0)
        self.assertLessEqual(data["shortest"]["km"], data["fastest"]["km"])

    def test_explore_returns_expansion_order(self):
        data = self.post("api-routing-explore", {"origin": "ciudad-guatemala", "destination": "flores"}).json()
        for name in ("dijkstra", "astar"):
            self.assertEqual(data["explore"][name]["order"][0], "ciudad-guatemala")
            self.assertEqual(len(data["explore"][name]["order"]), data["explore"][name]["expanded"])

    def test_optimize(self):
        data = self.post("api-routes-optimize", {
            "depot": "ciudad-guatemala", "stops": ["retalhuleu", "chimaltenango", "quetzaltenango"],
            "departure": "2026-10-06T07:00", "service_min": 10,
        }).json()
        plan = data["plan"]
        self.assertEqual(len(plan["stops"]), 3)
        self.assertEqual(len(plan["legs"]), 3)
        self.assertLessEqual(plan["baseline"]["two_opt_minutes"], plan["baseline"]["capture_order_minutes"])
        self.assertEqual(sorted(plan["order"]), [0, 1, 2])

    def test_best_departure_and_traffic_profile(self):
        data = self.client.get(reverse("api-routing-best-departure"), {
            "origin": "ciudad-guatemala", "destination": "quetzaltenango", "date": "2026-10-06"}).json()
        self.assertEqual(len(data["bands"]), 7)
        minutes = {b["band"]: b["minutes"] for b in data["bands"]}
        self.assertGreater(minutes["peak_am"], minutes["night"])

        profile = self.client.get(reverse("api-traffic-profile"), {"band": "peak_pm", "day": "weekday"}).json()
        self.assertTrue(profile["calibrated"])
        self.assertEqual(len(profile["edges"]), 260)
        self.assertTrue(all(e["multiplier"] >= 1 for e in profile["edges"]))

    def test_invalid_requests_return_400_with_spanish_message(self):
        cases = [
            ("api-routing-route", {"origin": "no-existe", "destination": "flores"}, "no existe el nodo"),
            ("api-routing-route", {"origin": "flores", "destination": "coban", "algorithm": "bfs"}, "Algoritmo inválido"),
            ("api-routing-route", {"origin": "flores", "destination": "coban", "departure": "mañana"}, "Hora de salida"),
            ("api-routes-optimize", {"depot": "ciudad-guatemala", "stops": []}, "al menos una parada"),
            ("api-routes-optimize", {"depot": "ciudad-guatemala", "stops": ["flores"] * 51}, "Máximo 50"),
        ]
        for name, payload, message in cases:
            response = self.post(name, payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertIn(message, response.json()["error"])
        bad = self.client.get(reverse("api-traffic-profile"), {"band": "hora-pico"})
        self.assertEqual(bad.status_code, 400)

    def test_empty_graph_explains_what_to_run(self):
        from logistics.models import Edge
        Edge.objects.all().delete()
        response = self.post("api-routing-route", {"origin": "flores", "destination": "coban"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("build_graph", response.json()["error"])
