"""Día 8: planificador con tráfico (más rápida vs más corta) y rutas confirmadas."""
import json
import random
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from logistics.models import Depot, Driver, Order, Route, RouteStop, UserProfile, Vehicle
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.graph import invalidate_graph


class PlanningApiTests(TestCase):
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
        cls.driver_user = User.objects.create_user(username="conductor", password="clave-segura-123")
        UserProfile.objects.create(user=cls.driver_user, role=UserProfile.Role.DRIVER)

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.user)
        self.pending = list(Order.objects.filter(is_demo=True, status=Order.Status.PENDING).order_by("id"))

    def post(self, name, payload):
        return self.client.post(reverse(name), json.dumps(payload), content_type="application/json")

    def plan(self, ids, departure="2026-10-06T07:30", **extra):
        return self.post("api-v2-routes-plan", {"depot_id": self.depot.id, "order_ids": ids, "departure": departure, **extra})

    def test_plan_returns_both_variants_with_etas_and_departure_options(self):
        ids = [o.id for o in self.pending[:4]]
        data = self.plan(ids).json()
        self.assertEqual(data["band"], "peak_am")
        for key in ("fastest", "shortest"):
            variant = data[key]
            self.assertEqual(sorted(s["order_id"] for s in variant["stops"]), sorted(ids))
            etas = [s["eta"] for s in variant["stops"]]
            self.assertEqual(etas, sorted(etas))
            self.assertEqual(len(variant["legs"]), 5)  # 4 paradas + regreso a bodega
            self.assertGreater(variant["expanded"], 0)
        self.assertEqual(len(data["departure_options"]), 7)
        self.assertAlmostEqual(data["minutes_saved"],
                               data["shortest"]["driving_minutes"] - data["fastest"]["driving_minutes"], places=1)

    def test_fastest_never_slower_than_shortest(self):
        """Propiedad: con el mismo tráfico, la más rápida nunca tarda más que la más corta."""
        rng = random.Random(8)
        for departure in ("2026-10-06T06:30", "2026-10-06T07:30", "2026-10-06T17:45", "2026-10-10T12:00"):
            for _ in range(4):
                ids = [o.id for o in rng.sample(self.pending, rng.randint(2, 7))]
                data = self.plan(ids, departure).json()
                self.assertLessEqual(data["fastest"]["driving_minutes"], data["shortest"]["driving_minutes"] + 1e-6)
                self.assertGreaterEqual(data["minutes_saved"], 0)

    def test_confirm_saves_route_stops_and_assigns_orders(self):
        ids = [o.id for o in self.pending[:3]]
        driver = Driver.objects.first()
        vehicle = Vehicle.objects.filter(capacity_kg__gte=500).first()
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": ids,
                                               "departure": "2026-10-06T07:30", "criterion": "time",
                                               "driver_id": driver.id, "vehicle_id": vehicle.id})
        self.assertEqual(response.status_code, 201, response.content)
        route = Route.objects.get(code=response.json()["route"]["code"])
        self.assertEqual(route.driver, driver)
        self.assertEqual(route.created_by, self.user)
        self.assertEqual(RouteStop.objects.filter(route=route).count(), 3)
        self.assertEqual(list(route.stops.values_list("sequence", flat=True)), [1, 2, 3])
        self.assertGreaterEqual(route.shortest_minutes, route.driving_minutes - 1e-6)
        self.assertEqual(set(Order.objects.filter(id__in=ids).values_list("status", flat=True)), {"assigned"})
        self.assertIn("edges=estimate", route.data_source)

        listed = self.client.get(reverse("api-v2-routes")).json()["routes"]
        self.assertEqual(listed[0]["code"], route.code)

        again = self.plan(ids)
        self.assertEqual(again.status_code, 400)
        self.assertIn("ya no están pendientes", again.json()["error"])

    def test_vehicle_capacity_is_checked(self):
        tiny = Vehicle.objects.create(plate="M-001", model="Moto", capacity_kg=Decimal("10"),
                                      fuel_efficiency_km_l=Decimal("30"), cost_per_km=Decimal("1"))
        heavy = [o.id for o in self.pending if o.weight_kg > 10][:2]
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": heavy, "vehicle_id": tiny.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("capacidad", response.json()["error"])
        self.assertFalse(Route.objects.exists())

    def test_validation_and_permissions(self):
        cases = [
            ({"depot_id": 9999, "order_ids": [self.pending[0].id]}, "bodega"),
            ({"depot_id": self.depot.id, "order_ids": []}, "al menos un pedido"),
            ({"depot_id": self.depot.id, "order_ids": [999999]}, "no existen"),
            ({"depot_id": self.depot.id, "order_ids": [self.pending[0].id], "service_min": 500}, "servicio"),
        ]
        for payload, message in cases:
            response = self.post("api-v2-routes-plan", payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertIn(message, response.json()["error"])
        self.client.force_login(self.driver_user)
        self.assertEqual(self.plan([self.pending[0].id]).status_code, 403)
