"""Vista del conductor: ruta de hoy, iniciar ruta y marcar paradas (aislamiento entre conductores)."""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from logistics.models import Depot, Driver, Order, Route, RouteStop, UserProfile


def make_user(name, role):
    user = User.objects.create_user(username=name, password="clave-segura-123")
    UserProfile.objects.create(user=user, role=role)
    return user


class DriverApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.depot = Depot.objects.create(name="Bodega Test", latitude=14.6, longitude=-90.5)
        cls.user_a = make_user("carlos", UserProfile.Role.DRIVER)
        cls.user_b = make_user("marta", UserProfile.Role.DRIVER)
        cls.dispatcher = make_user("despachador", UserProfile.Role.DISPATCHER)
        cls.orphan = make_user("sin-conductor", UserProfile.Role.DRIVER)
        cls.driver_a = Driver.objects.create(user=cls.user_a, name="Carlos", license_number="A-1")
        cls.driver_b = Driver.objects.create(user=cls.user_b, name="Marta", license_number="B-1")

    def make_route(self, driver, n_stops=2, departure=None, status=Route.Status.PLANNED):
        departure = departure or timezone.localtime().replace(hour=14, minute=0)
        route = Route.objects.create(
            depot=self.depot, driver=driver, departure_at=departure, driving_minutes=60, total_km=30,
            finish_at=departure + timedelta(hours=2), status=status)
        stops = []
        for i in range(1, n_stops + 1):
            order = Order.objects.create(
                recipient=f"Cliente {i}", phone="5555-000%d" % i, address="Zona 1", latitude=14.6, longitude=-90.5,
                weight_kg=Decimal("5"), status=Order.Status.ASSIGNED)
            stops.append(RouteStop.objects.create(route=route, order=order, sequence=i, eta=departure + timedelta(minutes=30 * i)))
        return route, stops

    def post(self, name, payload=None, **kwargs):
        return self.client.post(reverse(name, kwargs=kwargs), json.dumps(payload or {}), content_type="application/json")

    # --- hoy ---
    def test_today_lists_only_own_routes_of_today_plus_in_progress(self):
        mine, _ = self.make_route(self.driver_a)
        self.make_route(self.driver_b)
        old, _ = self.make_route(self.driver_a, departure=timezone.now() - timedelta(days=3))
        running, _ = self.make_route(self.driver_a, departure=timezone.now() - timedelta(days=1), status=Route.Status.IN_PROGRESS)
        self.make_route(self.driver_a, departure=timezone.now() - timedelta(days=2), status=Route.Status.COMPLETED)
        self.client.force_login(self.user_a)
        data = self.client.get(reverse("api-driver-today")).json()
        ids = [r["id"] for r in data["routes"]]
        self.assertEqual(ids, [running.id, mine.id])
        self.assertNotIn(old.id, ids)
        self.assertEqual(data["driver"]["name"], "Carlos")
        stop = data["routes"][1]["stops"][0]
        for key in ("id", "eta", "phone", "address", "lat", "lng", "status", "reason", "recipient"):
            self.assertIn(key, stop)

    def test_today_requires_driver_role_and_a_linked_driver(self):
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.client.get(reverse("api-driver-today")).status_code, 403)
        self.client.force_login(self.orphan)
        response = self.client.get(reverse("api-driver-today"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("conductor asociado", response.json()["error"])
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api-driver-today")).status_code, 401)

    # --- iniciar ---
    def test_start_route_sets_started_at_and_orders_in_transit(self):
        route, stops = self.make_route(self.driver_a)
        self.client.force_login(self.user_a)
        data = self.post("api-driver-route-start", route_id=route.id).json()
        self.assertEqual(data["route"]["status"], "in_progress")
        self.assertIsNotNone(data["route"]["started_at"])
        route.refresh_from_db()
        self.assertEqual(route.status, Route.Status.IN_PROGRESS)
        self.assertTrue(all(s.order.status == Order.Status.IN_TRANSIT for s in RouteStop.objects.filter(route=route).select_related("order")))
        # Iniciar dos veces no se permite
        self.assertEqual(self.post("api-driver-route-start", route_id=route.id).status_code, 400)

    # --- paradas ---
    def test_deliver_and_fail_complete_the_route(self):
        route, (s1, s2) = self.make_route(self.driver_a)
        self.client.force_login(self.user_a)
        data = self.post("api-driver-stop-update", {"status": "delivered"}, stop_id=s1.id).json()
        self.assertEqual(data["route"]["status"], "in_progress")  # iniciada al marcar la primera
        route.refresh_from_db()
        self.assertIsNotNone(route.started_at)
        s1.refresh_from_db()
        self.assertEqual(s1.status, RouteStop.Status.DELIVERED)
        self.assertIsNotNone(s1.delivered_at)
        self.assertEqual(s1.order.status, Order.Status.DELIVERED)

        data = self.post("api-driver-stop-update", {"status": "failed", "reason": "Nadie en casa"}, stop_id=s2.id).json()
        self.assertEqual(data["route"]["status"], "completed")
        self.assertIsNotNone(data["route"]["completed_at"])
        s2.refresh_from_db()
        self.assertEqual((s2.status, s2.reason, s2.order.status), ("failed", "Nadie en casa", Order.Status.FAILED))

    def test_failed_requires_reason_and_valid_status(self):
        _, (s1, _s2) = self.make_route(self.driver_a)
        self.client.force_login(self.user_a)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "failed"}, stop_id=s1.id).status_code, 400)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "failed", "reason": "  "}, stop_id=s1.id).status_code, 400)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "pending"}, stop_id=s1.id).status_code, 400)
        s1.refresh_from_db()
        self.assertEqual(s1.status, RouteStop.Status.PENDING)

    def test_stop_cannot_be_marked_twice(self):
        _, (s1, _s2) = self.make_route(self.driver_a)
        self.client.force_login(self.user_a)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "delivered"}, stop_id=s1.id).status_code, 200)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "failed", "reason": "x"}, stop_id=s1.id).status_code, 400)

    # --- aislamiento ---
    def test_driver_cannot_see_or_modify_another_drivers_route(self):
        route_b, (stop_b, _) = self.make_route(self.driver_b)
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(reverse("api-driver-today")).json()["routes"], [])
        self.assertEqual(self.post("api-driver-route-start", route_id=route_b.id).status_code, 404)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "delivered"}, stop_id=stop_b.id).status_code, 404)
        route_b.refresh_from_db()
        stop_b.refresh_from_db()
        self.assertEqual(route_b.status, Route.Status.PLANNED)
        self.assertIsNone(route_b.started_at)
        self.assertEqual(stop_b.status, RouteStop.Status.PENDING)
        self.assertEqual(stop_b.order.status, Order.Status.ASSIGNED)

    def test_dispatcher_cannot_use_driver_endpoints(self):
        route, (stop, _) = self.make_route(self.driver_a)
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.post("api-driver-route-start", route_id=route.id).status_code, 403)
        self.assertEqual(self.post("api-driver-stop-update", {"status": "delivered"}, stop_id=stop.id).status_code, 403)
