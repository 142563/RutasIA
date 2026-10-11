"""Seguimiento público del pedido (A3, RUT-71): sin sesión, con datos mínimos."""
import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from logistics.models import Depot, Driver, Node, Order, Route, RouteStop


class PublicTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.depot = Depot.objects.create(name="Bodega Test", latitude=14.6, longitude=-90.5)
        cls.driver = Driver.objects.create(name="Carlos Pérez Gómez", phone="5555-1234", license_number="A-1")
        cls.node = Node.objects.create(
            code="antigua", name="Antigua Guatemala", kind=Node.Kind.CABECERA, department="SA",
            latitude=14.56, longitude=-90.73)

    def make_order(self, **extra):
        return Order.objects.create(
            recipient="Marta Ruiz", phone="4444-9999", address="3a calle 12-34 zona 2", latitude=14.5612,
            longitude=-90.7312, weight_kg=Decimal("4"), recipient_email="marta@example.com", node=self.node, **extra)

    def make_stop(self, order, route_status=Route.Status.PLANNED, **route_extra):
        now = timezone.now()
        route = Route.objects.create(
            depot=self.depot, driver=self.driver, departure_at=now, driving_minutes=30, total_km=20,
            finish_at=now + timedelta(hours=1), status=route_status, **route_extra)
        return RouteStop.objects.create(route=route, order=order, sequence=1, eta=now + timedelta(minutes=45))

    def get(self, token):
        return self.client.get(reverse("api-public-tracking", kwargs={"token": token}))

    def test_unknown_or_malformed_token_is_a_generic_404(self):
        for token in ("x" * 22, "corto", "a" * 80):
            response = self.get(token)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertEqual(response.json(), {"ok": False, "error": "No encontramos ese pedido."})

    def test_received_order_works_without_session(self):
        order = self.make_order()
        response = self.get(order.tracking_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = response.json()
        self.assertEqual(data["code"], order.code)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["status_label"], "Pendiente")
        self.assertEqual([s["done"] for s in data["timeline"]], [True, False, False, False])
        self.assertIsNone(data["window"])
        self.assertEqual(data["place"], {"municipality": "Antigua Guatemala", "region": "Central"})

    def test_scheduled_has_window_and_in_progress_shows_driver_first_name(self):
        order = self.make_order(status=Order.Status.ASSIGNED)
        stop = self.make_stop(order)
        data = self.get(order.tracking_token).json()
        self.assertIsNotNone(data["window"])
        self.assertIsNone(data["driver_name"])
        Route.objects.filter(pk=stop.route_id).update(status=Route.Status.IN_PROGRESS, started_at=timezone.now())
        Order.objects.filter(pk=order.pk).update(status=Order.Status.IN_TRANSIT)
        data = self.get(order.tracking_token).json()
        self.assertEqual(data["driver_name"], "Carlos")
        self.assertEqual([s["done"] for s in data["timeline"]], [True, True, True, False])

    def test_failed_says_we_will_contact(self):
        order = self.make_order(status=Order.Status.FAILED)
        stop = self.make_stop(order, Route.Status.IN_PROGRESS, started_at=timezone.now())
        RouteStop.objects.filter(pk=stop.pk).update(
            status=RouteStop.Status.FAILED, delivered_at=timezone.now(), reason="Nadie")
        data = self.get(order.tracking_token).json()
        self.assertEqual(data["timeline"][-1]["key"], "failed")
        self.assertIn("reprogramar", data["note"])
        self.assertIsNone(data["window"])

    def test_no_sensitive_data_leaks(self):
        order = self.make_order(status=Order.Status.IN_TRANSIT)
        stop = self.make_stop(order, Route.Status.IN_PROGRESS, started_at=timezone.now())
        RouteStop.objects.filter(pk=stop.pk).update(reason="privado")
        other = self.make_order()
        raw = self.get(order.tracking_token).content.decode()
        self.assertEqual(set(json.loads(raw)),
                         {"ok", "code", "status", "status_label", "timeline", "window", "place", "driver_name", "note"})
        for secret in ("4444-9999", "5555-1234", "3a calle", "14.56", "-90.73", "marta@example.com",
                       "Marta", "Gómez", other.code, other.tracking_token, "privado"):
            self.assertNotIn(secret, raw)

    def test_only_get_is_allowed(self):
        order = self.make_order()
        response = self.client.post(reverse("api-public-tracking", kwargs={"token": order.tracking_token}))
        self.assertEqual(response.status_code, 405)
