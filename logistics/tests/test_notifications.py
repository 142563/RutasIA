"""Correos de entrega (RUT-55): Resend se simula con un mock de httpx.post."""
import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest import mock

import httpx
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from logistics.application.notifications import format_moment
from logistics.models import Depot, Driver, Order, Route, RouteStop, UserProfile
from logistics.routing.graph import invalidate_graph

POST = "logistics.application.notifications.httpx.post"


def make_user(name, role, email=""):
    user = User.objects.create_user(username=name, password="clave-segura-123", email=email)
    UserProfile.objects.create(user=user, role=role)
    return user


def ok_response(*args, **kwargs):
    return mock.Mock(raise_for_status=mock.Mock())


@override_settings(RESEND_API_KEY="test", NOTIFY_FROM="enruta <entregas@enruta.world>", SITE_URL="https://enruta.test")
class DeliveryEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.depot = Depot.objects.create(name="Bodega Test", latitude=14.6, longitude=-90.5)
        cls.driver_user = make_user("carlos", UserProfile.Role.DRIVER)
        cls.driver = Driver.objects.create(user=cls.driver_user, name="Carlos Pérez", license_number="A-1")

    def make_route(self, client_email="cliente@example.com", dispatcher_email="desp@example.com"):
        creator = make_user("desp-%s" % User.objects.count(), UserProfile.Role.DISPATCHER, dispatcher_email)
        departure = timezone.now()
        route = Route.objects.create(
            depot=self.depot, driver=self.driver, departure_at=departure, driving_minutes=60, total_km=30,
            finish_at=departure + timedelta(hours=2), created_by=creator)
        stops = []
        for i in (1, 2):
            order = Order.objects.create(
                recipient=f"Cliente <{i}>", address="Zona 1", latitude=14.6, longitude=-90.5,
                weight_kg=Decimal("5"), status=Order.Status.ASSIGNED, recipient_email=client_email)
            stops.append(RouteStop.objects.create(
                route=route, order=order, sequence=i, eta=departure + timedelta(minutes=30 * i)))
        return route, stops

    def mark(self, stop, status="delivered", reason=""):
        self.client.force_login(self.driver_user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("api-driver-stop-update", kwargs={"stop_id": stop.id}),
                json.dumps({"status": status, "reason": reason}), content_type="application/json")

    def test_delivery_sends_one_email_per_recipient(self):
        _, stops = self.make_route()
        with mock.patch(POST, side_effect=ok_response) as post:
            response = self.mark(stops[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_count, 2)
        calls = {c.kwargs["json"]["to"][0]: c.kwargs for c in post.call_args_list}
        client = calls["cliente@example.com"]
        self.assertEqual(client["json"]["subject"], f"Tu pedido {stops[0].order.code} fue entregado")
        self.assertEqual(client["headers"]["Authorization"], "Bearer test")
        self.assertEqual(client["timeout"], 8)
        self.assertNotIn("enruta.test", client["json"]["html"])
        self.assertIn("Carlos Pérez", client["json"]["text"])
        desp = calls["desp@example.com"]
        self.assertEqual(desp["json"]["subject"], f"Entregado: {stops[0].order.code} · Cliente <1>")
        self.assertIn("1 de 2 paradas", desp["json"]["text"])
        self.assertIn("https://enruta.test/rutas/", desp["json"]["text"])
        # Lo que viene del usuario se escapa en el HTML
        self.assertIn("Cliente &lt;1&gt;", desp["json"]["html"])
        self.assertNotIn("Cliente <1>", desp["json"]["html"])

    def test_without_client_email_only_dispatcher(self):
        _, stops = self.make_route(client_email="")
        with mock.patch(POST, side_effect=ok_response) as post:
            self.mark(stops[0])
        self.assertEqual([c.kwargs["json"]["to"] for c in post.call_args_list], [["desp@example.com"]])

    def test_without_any_email_nothing_is_sent(self):
        _, stops = self.make_route(client_email="", dispatcher_email="")
        with mock.patch(POST) as post:
            self.mark(stops[0])
        post.assert_not_called()

    @override_settings(RESEND_API_KEY="")
    def test_without_api_key_nothing_is_sent(self):
        _, stops = self.make_route()
        with mock.patch(POST) as post:
            response = self.mark(stops[0])
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()

    def test_http_failures_do_not_break_the_delivery(self):
        for failure in (httpx.ConnectError("sin red"), None):
            _, stops = self.make_route()
            if failure is None:
                bad = mock.Mock()
                bad.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=mock.Mock(), response=mock.Mock())
                patcher = mock.patch(POST, return_value=bad)
            else:
                patcher = mock.patch(POST, side_effect=failure)
            with patcher, self.assertLogs("logistics.application.notifications", level="WARNING"):
                response = self.mark(stops[0])
            self.assertEqual(response.status_code, 200)
            stops[0].refresh_from_db()
            self.assertEqual(stops[0].status, RouteStop.Status.DELIVERED)

    def test_one_failed_email_does_not_block_the_other(self):
        _, stops = self.make_route()

        def fail_for_client(*args, **kwargs):
            if kwargs["json"]["to"] == ["cliente@example.com"]:
                raise httpx.ConnectError("sin red")
            return ok_response()

        from logistics.application.notifications import notify_delivery
        with mock.patch(POST, side_effect=fail_for_client) as post:
            with mock.patch("logistics.application.driver.notify_delivery_safe"):
                self.mark(stops[0])
            with self.assertLogs("logistics.application.notifications", level="WARNING"):
                sent = notify_delivery(stops[0].id)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(sent, ["desp@example.com"])

    def test_failed_delivery_sends_nothing(self):
        _, stops = self.make_route()
        with mock.patch(POST) as post:
            response = self.mark(stops[0], status="failed", reason="No estaba")
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()

    def test_format_moment_uses_guatemala_time(self):
        moment = datetime(2026, 10, 10, 20, 32, tzinfo=dt_timezone.utc)
        self.assertEqual(format_moment(moment), "10 de octubre, 14:32")


class OrderEmailFieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        cls.dispatcher = make_user("despachador", UserProfile.Role.DISPATCHER)

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.dispatcher)

    def create(self, **extra):
        payload = {"recipient": "Lucía", "address": "Zona 1", "latitude": 14.8360, "longitude": -91.5170,
                   "weight_kg": 4.5, **extra}
        return self.client.post(reverse("api-v2-orders"), json.dumps(payload), content_type="application/json")

    def test_invalid_email_is_rejected_in_spanish(self):
        response = self.create(recipient_email="no-es-correo")
        self.assertEqual(response.status_code, 400)
        self.assertIn("correo", response.json()["error"].lower())
        self.assertEqual(Order.objects.count(), 0)

    def test_valid_and_empty_email(self):
        response = self.create(recipient_email="  lucia@example.com ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["order"]["recipient_email"], "lucia@example.com")
        self.assertEqual(Order.objects.get().recipient_email, "lucia@example.com")
        self.assertEqual(self.create().json()["order"]["recipient_email"], "")
