"""RUT-35: asignar, reasignar y cancelar rutas, con disponibilidad por horario y capacidad."""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from logistics.models import Depot, Driver, Order, Route, UserProfile, Vehicle
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.graph import invalidate_graph


class AssignmentApiTests(TestCase):
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
        self.drivers = list(Driver.objects.order_by("id"))
        self.vehicles = list(Vehicle.objects.order_by("id"))

    def post(self, name, payload, *args):
        return self.client.post(reverse(name, args=args), json.dumps(payload), content_type="application/json")

    def make_route(self, count=1, departure="2026-10-06T07:30", offset=0, **extra):
        ids = [o.id for o in self.pending[offset:offset + count]]
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": ids,
                                               "departure": departure, **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return Route.objects.get(code=response.json()["route"]["code"])

    def assign(self, route, payload):
        return self.post("api-v2-route-assign", payload, route.id)

    # --- asignar ---------------------------------------------------------------

    def test_assign_driver_and_vehicle_to_planned_route(self):
        route = self.make_route()
        response = self.assign(route, {"driver_id": self.drivers[0].id, "vehicle_id": self.vehicles[1].id})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["route"]
        self.assertEqual(data["driver_id"], self.drivers[0].id)
        self.assertEqual(data["vehicle_id"], self.vehicles[1].id)
        route.refresh_from_db()
        self.assertEqual(route.driver, self.drivers[0])

    def test_vehicle_with_fixed_driver_suggests_him(self):
        route = self.make_route()
        vehicle = self.vehicles[0]
        response = self.assign(route, {"vehicle_id": vehicle.id})
        data = response.json()
        self.assertTrue(data["suggested_driver"])
        self.assertEqual(data["route"]["driver_id"], vehicle.driver_id)

    def test_null_clears_assignment(self):
        route = self.make_route(driver_id=self.drivers[0].id)
        response = self.assign(route, {"driver_id": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["route"]["driver_id"])

    def test_overlapping_route_blocks_driver_and_vehicle(self):
        first = self.make_route(driver_id=self.drivers[1].id, vehicle_id=self.vehicles[1].id)
        second = self.make_route(offset=1)  # mismo horario
        bad_driver = self.assign(second, {"driver_id": self.drivers[1].id})
        self.assertEqual(bad_driver.status_code, 400)
        self.assertIn(f"ocupado en la ruta {first.code}", bad_driver.json()["error"])
        bad_vehicle = self.assign(second, {"vehicle_id": self.vehicles[1].id})
        self.assertEqual(bad_vehicle.status_code, 400)
        self.assertIn(first.code, bad_vehicle.json()["error"])

    def test_other_day_does_not_overlap(self):
        self.make_route(driver_id=self.drivers[1].id)
        later = self.make_route(offset=1, departure="2026-10-07T07:30")
        self.assertEqual(self.assign(later, {"driver_id": self.drivers[1].id}).status_code, 200)

    def test_capacity_exceeded(self):
        tiny = Vehicle.objects.create(plate="M-001", model="Moto", capacity_kg=Decimal("10"),
                                      fuel_efficiency_km_l=Decimal("30"), cost_per_km=Decimal("1"))
        heavy = next(i for i, o in enumerate(self.pending) if o.weight_kg > 10)
        route = self.make_route(offset=heavy)
        response = self.assign(route, {"vehicle_id": tiny.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No cabe", response.json()["error"])

    def test_inactive_driver_and_vehicle_rejected(self):
        route = self.make_route()
        Driver.objects.filter(pk=self.drivers[2].pk).update(is_active=False)
        Vehicle.objects.filter(pk=self.vehicles[2].pk).update(is_active=False)
        self.assertIn("inactivo", self.assign(route, {"driver_id": self.drivers[2].id}).json()["error"])
        self.assertIn("inactivo", self.assign(route, {"vehicle_id": self.vehicles[2].id}).json()["error"])

    def test_only_planned_routes_are_assigned(self):
        route = self.make_route()
        Route.objects.filter(pk=route.pk).update(status=Route.Status.IN_PROGRESS)
        response = self.assign(route, {"driver_id": self.drivers[0].id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("planificada", response.json()["error"])
        self.assertEqual(self.assign(Route(id=99999), {"driver_id": 1}).status_code, 404)

    def test_planner_applies_same_validations(self):
        self.make_route(driver_id=self.drivers[1].id)
        ids = [self.pending[1].id]
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": ids,
                                               "departure": "2026-10-06T07:30", "driver_id": self.drivers[1].id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("ocupado", response.json()["error"])
        self.assertEqual(Route.objects.count(), 1)
        self.assertEqual(Order.objects.get(pk=ids[0]).status, Order.Status.PENDING)

    # --- opciones --------------------------------------------------------------

    def test_options_show_availability(self):
        first = self.make_route(driver_id=self.drivers[1].id, vehicle_id=self.vehicles[1].id)
        second = self.make_route(offset=1)
        Driver.objects.filter(pk=self.drivers[0].pk).update(user=self.driver_user)
        Driver.objects.filter(pk=self.drivers[3].pk).update(is_active=False)
        data = self.client.get(reverse("api-v2-assignment-options"), {"route_id": second.id}).json()
        drivers = {d["id"]: d for d in data["drivers"]}
        self.assertNotIn(self.drivers[3].id, drivers)  # inactivos no se listan
        self.assertTrue(drivers[self.drivers[1].id]["busy"])
        self.assertEqual(drivers[self.drivers[1].id]["busy_route"]["code"], first.code)
        self.assertFalse(drivers[self.drivers[2].id]["busy"])
        self.assertTrue(drivers[self.drivers[0].id]["has_mobile_account"])
        self.assertFalse(drivers[self.drivers[2].id]["has_mobile_account"])
        vehicles = {v["id"]: v for v in data["vehicles"]}
        self.assertTrue(vehicles[self.vehicles[1].id]["busy"])
        self.assertTrue(all(v["fits"] is not None for v in vehicles.values()))
        self.assertEqual(data["total_weight_kg"], float(self.pending[1].weight_kg))

    def test_options_by_date_and_not_found(self):
        self.make_route(driver_id=self.drivers[1].id)
        same_day = self.client.get(reverse("api-v2-assignment-options"), {"departure": "2026-10-06T08:00"}).json()
        self.assertTrue(next(d for d in same_day["drivers"] if d["id"] == self.drivers[1].id)["busy"])
        other_day = self.client.get(reverse("api-v2-assignment-options"), {"departure": "2026-10-08T08:00"}).json()
        self.assertFalse(next(d for d in other_day["drivers"] if d["id"] == self.drivers[1].id)["busy"])
        self.assertIsNone(other_day["vehicles"][0]["fits"])
        missing = self.client.get(reverse("api-v2-assignment-options"), {"route_id": 99999})
        self.assertEqual(missing.status_code, 404)

    # --- cancelar --------------------------------------------------------------

    def test_cancel_releases_orders_and_keeps_stops(self):
        route = self.make_route(count=3)
        ids = list(route.stops.values_list("order_id", flat=True))
        response = self.post("api-v2-route-cancel", {"reason": "Cliente pidió reprogramar"}, route.id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["route"]["status"], "canceled")
        self.assertEqual(response.json()["released_orders"], 3)
        self.assertEqual(set(Order.objects.filter(id__in=ids).values_list("status", flat=True)), {"pending"})
        self.assertEqual(route.stops.count(), 3)
        self.assertEqual(route.stops.first().reason, "Cliente pidió reprogramar")
        # Ya se pueden volver a planificar
        again = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": ids,
                                            "departure": "2026-10-06T07:30"})
        self.assertEqual(again.status_code, 201)

    def test_canceled_route_frees_driver(self):
        route = self.make_route(driver_id=self.drivers[1].id)
        other = self.make_route(offset=1)
        self.post("api-v2-route-cancel", {}, route.id)
        self.assertEqual(self.assign(other, {"driver_id": self.drivers[1].id}).status_code, 200)

    def test_cannot_cancel_in_progress_or_twice(self):
        route = self.make_route()
        Route.objects.filter(pk=route.pk).update(status=Route.Status.IN_PROGRESS)
        self.assertEqual(self.post("api-v2-route-cancel", {}, route.id).status_code, 400)
        Route.objects.filter(pk=route.pk).update(status=Route.Status.CANCELED)
        self.assertEqual(self.post("api-v2-route-cancel", {}, route.id).status_code, 400)

    # --- permisos --------------------------------------------------------------

    def test_roles(self):
        route = self.make_route()
        self.client.force_login(self.driver_user)
        self.assertEqual(self.assign(route, {"driver_id": self.drivers[0].id}).status_code, 403)
        self.assertEqual(self.post("api-v2-route-cancel", {}, route.id).status_code, 403)
        self.assertEqual(self.client.get(reverse("api-v2-assignment-options")).status_code, 403)
        admin = User.objects.create_user(username="admin", password="clave-segura-123")
        UserProfile.objects.create(user=admin, role=UserProfile.Role.ADMIN)
        self.client.force_login(admin)
        self.assertEqual(self.assign(route, {"driver_id": self.drivers[0].id}).status_code, 200)
        self.client.logout()
        self.assertIn(self.client.get(reverse("api-v2-assignment-options")).status_code, (302, 401, 403))
