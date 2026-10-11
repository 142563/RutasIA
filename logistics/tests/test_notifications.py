"""Avisos por correo (RUT-55 y A1 de RUT-68): Resend se simula con un mock de httpx.post."""
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

from logistics.application.notifications import Message, dispatch, format_moment, notify_delivered, safely
from logistics.application.notifications.recipients import staff_recipients
from logistics.domain.notifications import Event
from logistics.models import Depot, Driver, NotificationLog, Order, Route, RouteStop, UserProfile
from logistics.routing.graph import invalidate_graph

POST = "logistics.application.notifications.transport.httpx.post"


def make_user(name, role, email=""):
    user = User.objects.create_user(username=name, password="clave-segura-123", email=email)
    UserProfile.objects.create(user=user, role=role)
    return user


def ok_response(*args, **kwargs):
    return mock.Mock(raise_for_status=mock.Mock(), json=lambda: {"id": "re_1"})


@override_settings(RESEND_API_KEY="test", NOTIFY_FROM="enruta <entregas@enruta.world>", SITE_URL="https://enruta.test")
class DeliveryEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.depot = Depot.objects.create(name="Bodega Test", latitude=14.6, longitude=-90.5)
        cls.driver_user = make_user("carlos", UserProfile.Role.DRIVER)
        cls.driver = Driver.objects.create(user=cls.driver_user, name="Carlos Pérez", license_number="A-1")

    def make_route(self, client_email="cliente@example.com", dispatcher_email="desp@example.com", demo=False):
        creator = make_user("desp-%s" % User.objects.count(), UserProfile.Role.DISPATCHER, dispatcher_email)
        departure = timezone.now()
        route = Route.objects.create(
            depot=self.depot, driver=self.driver, departure_at=departure, driving_minutes=60, total_km=30,
            finish_at=departure + timedelta(hours=2), created_by=creator)
        stops = []
        for i in (1, 2):
            order = Order.objects.create(
                recipient=f"Cliente <{i}>", address="Zona 1", latitude=14.6, longitude=-90.5,
                weight_kg=Decimal("5"), status=Order.Status.ASSIGNED, recipient_email=client_email, is_demo=demo)
            stops.append(RouteStop.objects.create(
                route=route, order=order, sequence=i, eta=departure + timedelta(minutes=30 * i)))
        return route, stops

    def mark(self, stop, status="delivered", reason=""):
        self.client.force_login(self.driver_user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("api-driver-stop-update", kwargs={"stop_id": stop.id}),
                json.dumps({"status": status, "reason": reason}), content_type="application/json")

    def test_delivery_emails_only_the_customer(self):
        # El despachador ya no recibe un correo por cada entrega: solo excepciones y resumen (§14.2)
        _, stops = self.make_route()
        with mock.patch(POST, side_effect=ok_response) as post:
            response = self.mark(stops[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(post.call_count, 1)
        call = post.call_args.kwargs
        self.assertEqual(call["json"]["to"], ["cliente@example.com"])
        self.assertEqual(call["json"]["subject"], f"Tu pedido {stops[0].order.code} fue entregado")
        self.assertEqual(call["headers"]["Authorization"], "Bearer test")
        self.assertEqual(call["timeout"], 8)
        self.assertIn("Carlos Pérez", call["json"]["text"])
        # Lo que viene del usuario se escapa en el HTML, no en el texto
        self.assertIn("Cliente &lt;1&gt;", call["json"]["html"])
        self.assertNotIn("Cliente <1>", call["json"]["html"])
        self.assertIn("Cliente <1>", call["json"]["text"])
        log = NotificationLog.objects.get()
        self.assertEqual((log.event, log.status, log.provider_id), ("delivered", "sent", "re_1"))

    def test_without_client_email_nothing_is_sent(self):
        _, stops = self.make_route(client_email="")
        with mock.patch(POST) as post:
            self.mark(stops[0])
        post.assert_not_called()

    def test_demo_orders_never_email(self):
        _, stops = self.make_route(demo=True)
        with mock.patch(POST) as post:
            self.mark(stops[0])
        post.assert_not_called()

    @override_settings(RESEND_API_KEY="")
    def test_without_api_key_nothing_leaves_but_it_is_logged(self):
        _, stops = self.make_route()
        with mock.patch(POST) as post:
            response = self.mark(stops[0])
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()
        self.assertEqual(NotificationLog.objects.get().status, NotificationLog.Status.SKIPPED)

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
        self.assertEqual(NotificationLog.objects.filter(status=NotificationLog.Status.FAILED).count(), 2)

    def test_same_event_is_not_sent_twice(self):
        _, stops = self.make_route()
        with mock.patch(POST, side_effect=ok_response) as post:
            self.mark(stops[0])
            notify_delivered(stops[0].id)
        self.assertEqual(post.call_count, 1)

    def test_failed_delivery_sends_nothing_yet(self):
        _, stops = self.make_route()
        with mock.patch(POST) as post:
            response = self.mark(stops[0], status="failed", reason="No estaba")
        self.assertEqual(response.status_code, 200)
        post.assert_not_called()

    def test_format_moment_uses_guatemala_time(self):
        moment = datetime(2026, 10, 10, 20, 32, tzinfo=dt_timezone.utc)
        self.assertEqual(format_moment(moment), "10 de octubre, 14:32")


@override_settings(RESEND_API_KEY="test")
class DispatchTests(TestCase):
    def message(self, to, key=""):
        return Message(event=Event.ORDER_RECEIVED, audience=NotificationLog.Audience.CUSTOMER, to=to,
                       subject="Asunto", html="<p>Hola</p>", text="Hola", dedupe_key=key)

    def test_several_messages_go_in_one_batch(self):
        response = mock.Mock(raise_for_status=mock.Mock(), json=lambda: {"data": [{"id": "a"}, {"id": "b"}]})
        with mock.patch(POST, return_value=response) as post:
            sent = dispatch([self.message("a@example.com"), self.message("b@example.com")])
        self.assertEqual(sent, ["a@example.com", "b@example.com"])
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith("/emails/batch"))
        self.assertEqual([e["to"] for e in post.call_args.kwargs["json"]], [["a@example.com"], ["b@example.com"]])
        self.assertEqual(sorted(NotificationLog.objects.values_list("provider_id", flat=True)), ["a", "b"])

    def test_failed_batch_is_retried_one_by_one(self):
        def fake(url, **kwargs):
            if url.endswith("/batch"):
                raise httpx.HTTPStatusError("422", request=mock.Mock(), response=mock.Mock())
            if kwargs["json"]["to"] == ["malo@example.com"]:
                raise httpx.ConnectError("rechazado")
            return ok_response()
        with mock.patch(POST, side_effect=fake), self.assertLogs("logistics.application.notifications", "WARNING"):
            sent = dispatch([self.message("malo@example.com"), self.message("bueno@example.com")])
        self.assertEqual(sent, ["bueno@example.com"])
        self.assertEqual(NotificationLog.objects.filter(status="failed").get().recipient, "malo@example.com")

    def test_welcome_subject_can_be_kept_out_of_the_log(self):
        message = self.message("nuevo@example.com")
        message.keep_subject = False
        with mock.patch(POST, side_effect=ok_response):
            dispatch([message])
        self.assertEqual(NotificationLog.objects.get().subject, "")

    def test_errors_inside_an_event_never_escape(self):
        def broken():
            raise ValueError("plantilla rota")
        with self.assertLogs("logistics.application.notifications", "WARNING"):
            self.assertEqual(safely(broken), [])


class RecipientMatrixTests(TestCase):
    def test_roles_and_scopes(self):
        admin = make_user("ana", UserProfile.Role.ADMIN, "ana@example.com")
        make_user("sin-correo", UserProfile.Role.ADMIN, "")
        creator = make_user("desp", UserProfile.Role.DISPATCHER, "desp@example.com")
        other = make_user("otro", UserProfile.Role.DISPATCHER, "otro@example.com")
        inactive = make_user("baja", UserProfile.Role.DISPATCHER, "baja@example.com")
        inactive.is_active = False
        inactive.save()
        driver_user = make_user("cond", UserProfile.Role.DRIVER, "cond@example.com")
        driver = Driver.objects.create(user=driver_user, name="Cond", license_number="B-2")
        depot = Depot.objects.create(name="B", latitude=14.6, longitude=-90.5)
        now = timezone.now()
        route = Route.objects.create(depot=depot, driver=driver, departure_at=now, driving_minutes=1, total_km=1,
                                     finish_at=now, created_by=creator)

        def emails(event, **kw):
            return sorted(u.email for u in staff_recipients(event, **kw))

        self.assertEqual(emails(Event.DELIVERY_FAILED, route=route), ["ana@example.com", "desp@example.com"])
        self.assertEqual(emails(Event.INCIDENT_REPORTED),
                         ["ana@example.com", "desp@example.com", "otro@example.com"])
        self.assertEqual(emails(Event.ROUTE_COMPLETED, route=route), ["desp@example.com"])
        self.assertEqual(emails(Event.ROUTE_ASSIGNED, route=route), ["cond@example.com"])
        self.assertEqual(emails(Event.ACCOUNT_CREATED, user=other), ["otro@example.com"])
        self.assertEqual(emails(Event.DELIVERED, route=route), [])
        self.assertNotIn(admin.email, emails(Event.ROUTE_COMPLETED, route=route))


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
