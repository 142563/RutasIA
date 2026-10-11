"""Avisos al personal por rol (A4, RUT-72): quién sí y quién no, asuntos, enlaces y "Avisos enviados"."""
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from logistics.application import notifications as n
from logistics.application.notification_log import mask_email
from logistics.models import (
    Depot, Driver, Incident, NotificationLog, Order, RerouteProposal, Route, RouteStop, UserProfile,
)

POST = "logistics.application.notifications.transport.httpx.post"
ROLE = UserProfile.Role


def make_user(name, role, email="", active=True):
    user = User.objects.create_user(username=name, password="clave-segura-123", email=email, is_active=active)
    UserProfile.objects.create(user=user, role=role)
    return user


def ok_response(*args, **kwargs):
    return mock.Mock(raise_for_status=mock.Mock(), json=lambda: {"id": "re_1"})


def payloads(post):
    """Correos enviados a Resend: una llamada por correo suelto o una lista si fueron en lote."""
    out = []
    for call in post.call_args_list:
        body = call.kwargs["json"]
        out.extend(body if isinstance(body, list) else [body])
    return out


def recipients(post):
    return sorted(p["to"][0] for p in payloads(post))


@override_settings(RESEND_API_KEY="test", NOTIFY_FROM="enruta <a@enruta.world>", SITE_URL="https://enruta.test")
class StaffNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.depot = Depot.objects.create(name="Bodega Test", latitude=14.6, longitude=-90.5)
        cls.admin = make_user("admin1", ROLE.ADMIN, "admin@example.com")
        cls.admin_no_mail = make_user("admin2", ROLE.ADMIN, "")
        cls.admin_inactive = make_user("admin3", ROLE.ADMIN, "off@example.com", active=False)
        cls.creator = make_user("desp1", ROLE.DISPATCHER, "creador@example.com")
        cls.other_dispatcher = make_user("desp2", ROLE.DISPATCHER, "otro@example.com")
        cls.driver_user = make_user("carlos", ROLE.DRIVER, "carlos@example.com")
        cls.driver = Driver.objects.create(user=cls.driver_user, name="Carlos Pérez", license_number="A-1")

    def make_route(self, status=Route.Status.PLANNED, driver=True):
        departure = timezone.now() + timedelta(hours=1)
        route = Route.objects.create(
            depot=self.depot, driver=self.driver if driver else None, departure_at=departure, driving_minutes=60,
            total_km=30.46, finish_at=departure + timedelta(hours=2), created_by=self.creator, status=status,
            service_min=10)
        stops = []
        for i in (1, 2):
            order = Order.objects.create(
                recipient=f"Cliente {i}", address="Zona 1", latitude=14.6, longitude=-90.5, weight_kg=Decimal("5"),
                status=Order.Status.ASSIGNED, recipient_email="")
            stops.append(RouteStop.objects.create(
                route=route, order=order, sequence=i, eta=departure + timedelta(minutes=30 * i)))
        return route, stops

    def call(self, fn, *args):
        with mock.patch(POST, side_effect=ok_response) as post:
            sent = fn(*args)
        return sent, post

    def test_route_assigned_goes_to_driver_only(self):
        route, _ = self.make_route()
        sent, post = self.call(n.staff.notify_route_assigned, route.id)
        self.assertEqual(sent, ["carlos@example.com"])
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], f"Nueva ruta asignada: {route.code}")
        self.assertIn("Bodega Test", body["text"])
        self.assertIn("2 paradas", body["text"])
        self.assertIn("30,5 km", body["text"])
        self.assertIn("80 min", body["text"])  # 60 de manejo + 2 paradas x 10
        self.assertIn("https://enruta.test/conductor", body["text"])
        log = NotificationLog.objects.get()
        self.assertEqual((log.audience, log.user_id, log.route_id), ("staff", self.driver_user.id, route.id))

    def test_route_assigned_not_repeated_and_skipped_without_driver_or_email(self):
        route, _ = self.make_route()
        self.call(n.staff.notify_route_assigned, route.id)
        sent, post = self.call(n.staff.notify_route_assigned, route.id)
        self.assertEqual(sent, [])
        post.assert_not_called()
        free, _ = self.make_route(driver=False)
        self.assertEqual(self.call(n.staff.notify_route_assigned, free.id)[0], [])
        self.driver_user.email = ""
        self.driver_user.save()
        other, _ = self.make_route()
        self.assertEqual(self.call(n.staff.notify_route_assigned, other.id)[0], [])
        self.driver_user.email = "carlos@example.com"
        self.driver_user.save()

    def test_route_assigned_ignores_inactive_driver(self):
        route, _ = self.make_route()
        self.driver_user.is_active = False
        self.driver_user.save()
        self.assertEqual(self.call(n.staff.notify_route_assigned, route.id)[0], [])
        self.driver_user.is_active = True
        self.driver_user.save()

    def test_route_canceled_uses_previous_driver_when_route_lost_it(self):
        route, _ = self.make_route(status=Route.Status.CANCELED, driver=False)
        sent, post = self.call(n.staff.notify_route_canceled, route.id, self.driver.id)
        self.assertEqual(sent, ["carlos@example.com"])
        self.assertEqual(post.call_args.kwargs["json"]["subject"], f"Ruta cancelada: {route.code}")
        self.assertEqual(self.call(n.staff.notify_route_canceled, route.id, None)[0], [])

    def test_delivery_failed_goes_to_admins_and_creator_only(self):
        route, stops = self.make_route(status=Route.Status.IN_PROGRESS)
        stop = stops[0]
        stop.status, stop.reason = RouteStop.Status.FAILED, "Nadie en casa"
        stop.save()
        sent, post = self.call(n.staff.notify_delivery_failed, stop.id)
        self.assertEqual(sorted(sent), ["admin@example.com", "creador@example.com"])
        self.assertNotIn("otro@example.com", recipients(post))
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], f"No entregado: {stop.order.code} · Cliente 1")
        self.assertIn("Nadie en casa", body["text"])
        self.assertIn("Carlos Pérez", body["text"])
        self.assertIn(f"https://enruta.test/rutas/{route.id}", body["text"])
        self.assertEqual(NotificationLog.objects.filter(order_id=stop.order_id).count(), 2)

    def test_delivery_failed_ignores_delivered_stop(self):
        _, stops = self.make_route()
        self.assertEqual(self.call(n.staff.notify_delivery_failed, stops[0].id)[0], [])

    def test_incident_goes_to_every_admin_and_dispatcher(self):
        route, _ = self.make_route(status=Route.Status.IN_PROGRESS)
        incident = Incident.objects.create(
            kind=Incident.Kind.LANDSLIDE, blocked=True, note="Derrumbe km 30", reported_by=self.driver_user,
            route=route)
        sent, post = self.call(n.staff.notify_incident_reported, incident.id)
        self.assertEqual(sorted(sent), ["admin@example.com", "creador@example.com", "otro@example.com"])
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], "Incidente reportado: Derrumbe")
        self.assertIn("Derrumbe km 30", body["text"])
        self.assertIn("bloqueado", body["text"])
        self.assertIn("carlos", body["text"])
        self.assertIn("https://enruta.test/", body["text"])
        self.assertNotIn("carlos@example.com", recipients(post))

    def test_route_completed_summary_goes_to_creator(self):
        route, stops = self.make_route(status=Route.Status.COMPLETED)
        route.started_at = timezone.now() - timedelta(minutes=95)
        route.completed_at = timezone.now()
        route.save()
        stops[0].status, stops[0].delivered_at = RouteStop.Status.DELIVERED, timezone.now()
        stops[0].save()
        stops[1].status, stops[1].reason = RouteStop.Status.FAILED, "Dirección incorrecta"
        stops[1].save()
        sent, post = self.call(n.staff.notify_route_completed, route.id)
        self.assertEqual(sent, ["creador@example.com"])
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], f"Ruta {route.code} terminada")
        self.assertIn("Entregados: 1 de 2", body["text"])
        self.assertIn("Dirección incorrecta", body["text"])
        self.assertIn("95 min reales contra 80 min estimados", body["text"])
        self.assertIn(f"https://enruta.test/rutas/{route.id}", body["text"])

    def test_route_completed_not_sent_before_completion(self):
        route, _ = self.make_route(status=Route.Status.IN_PROGRESS)
        self.assertEqual(self.call(n.staff.notify_route_completed, route.id)[0], [])

    def test_reroute_pending_goes_to_creator_and_approved_to_driver(self):
        route, _ = self.make_route(status=Route.Status.IN_PROGRESS)
        proposal = RerouteProposal.objects.create(
            route=route, current_minutes=100, proposed_minutes=82, summary="Nueva ruta por Palín: −18 min")
        sent, post = self.call(n.staff.notify_reroute_pending, proposal.id)
        self.assertEqual(sent, ["creador@example.com"])
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], f"Recálculo por aprobar en {route.code}")
        self.assertIn("Nueva ruta por Palín", body["text"])
        self.assertIn("18 min", body["text"])
        self.assertIn(f"https://enruta.test/rutas/{route.id}", body["text"])
        # Aún pendiente: al conductor no le llega nada hasta que se apruebe
        self.assertEqual(self.call(n.staff.notify_reroute_approved, proposal.id)[0], [])
        proposal.status = RerouteProposal.Status.ACCEPTED
        proposal.save()
        sent, post = self.call(n.staff.notify_reroute_approved, proposal.id)
        self.assertEqual(sent, ["carlos@example.com"])
        body = payloads(post)[-1]
        self.assertEqual(body["subject"], "Tu ruta cambió")
        self.assertIn("https://enruta.test/conductor", body["text"])

    def test_html_escapes_user_text(self):
        route, stops = self.make_route(status=Route.Status.IN_PROGRESS)
        stops[0].status, stops[0].reason = RouteStop.Status.FAILED, "<b>x</b>"
        stops[0].save()
        _, post = self.call(n.staff.notify_delivery_failed, stops[0].id)
        body = payloads(post)[-1]
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", body["html"])
        self.assertIn("<b>x</b>", body["text"])

    def mark(self, stop, status, reason=""):
        self.client.force_login(self.driver_user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("api-driver-stop-update", kwargs={"stop_id": stop.id}),
                json.dumps({"status": status, "reason": reason}), content_type="application/json")

    def test_real_flow_failed_stop_notifies_admin_and_creator(self):
        _, stops = self.make_route(status=Route.Status.IN_PROGRESS)
        with mock.patch(POST, side_effect=ok_response) as post:
            response = self.mark(stops[0], "failed", "Cerrado")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(recipients(post), ["admin@example.com", "creador@example.com"])

    def test_real_flow_last_stop_sends_summary(self):
        route, stops = self.make_route(status=Route.Status.IN_PROGRESS)
        Route.objects.filter(pk=route.pk).update(started_at=timezone.now() - timedelta(minutes=30))
        with mock.patch(POST, side_effect=ok_response) as post:
            self.mark(stops[0], "delivered")
            self.assertEqual(post.call_count, 0)  # entregar no avisa al despachador
            self.mark(stops[1], "delivered")
        self.assertEqual(recipients(post), ["creador@example.com"])
        self.assertEqual(post.call_args.kwargs["json"]["subject"], f"Ruta {route.code} terminada")


@override_settings(RESEND_API_KEY="")
class NotificationsEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        depot = Depot.objects.create(name="Bodega", latitude=14.6, longitude=-90.5)
        cls.admin = make_user("admin", ROLE.ADMIN, "admin@example.com")
        cls.dispatcher = make_user("desp", ROLE.DISPATCHER, "desp@example.com")
        cls.driver_user = make_user("conductor", ROLE.DRIVER, "c@example.com")
        departure = timezone.now()
        cls.route = Route.objects.create(
            depot=depot, departure_at=departure, driving_minutes=10, total_km=5, finish_at=departure)
        cls.order = Order.objects.create(
            recipient="Ana", address="Zona 1", latitude=14.6, longitude=-90.5, weight_kg=Decimal("1"))
        NotificationLog.objects.create(
            event="delivered", audience="customer", recipient="julio@gmail.com", subject="Secreto",
            status="sent", route=cls.route, order=cls.order)
        NotificationLog.objects.create(
            event="route_completed", audience="staff", recipient="x@y.com", status="skipped", route=cls.route)

    def get(self, user, **params):
        self.client.force_login(user)
        return self.client.get(reverse("api-v2-notifications"), params)

    def test_route_filter_masks_email_and_hides_body(self):
        response = self.get(self.admin, route=self.route.id)
        self.assertEqual(response.status_code, 200)
        items = response.json()["notifications"]
        self.assertEqual(len(items), 2)
        by_event = {i["event"]: i for i in items}
        delivered = by_event["delivered"]
        self.assertEqual(delivered["recipient"], "j***@gmail.com")
        self.assertEqual(delivered["event_label"], "Pedido entregado")
        self.assertEqual((delivered["status"], delivered["status_label"]), ("sent", "Enviado"))
        self.assertEqual(by_event["route_completed"]["status_label"], "Sin enviar")
        raw = response.content.decode()
        self.assertNotIn("julio@gmail.com", raw)
        self.assertNotIn("Secreto", raw)
        for forbidden in ("html", "text", "body", "subject", "error"):
            self.assertNotIn(forbidden, delivered)

    def test_order_filter_for_dispatcher(self):
        response = self.get(self.dispatcher, order=self.order.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i["event"] for i in response.json()["notifications"]], ["delivered"])

    def test_driver_is_forbidden_and_filter_is_required(self):
        self.assertEqual(self.get(self.driver_user, route=self.route.id).status_code, 403)
        self.assertEqual(self.get(self.admin).status_code, 400)
        self.assertEqual(self.get(self.admin, route="abc").status_code, 400)

    def test_anonymous_is_not_allowed(self):
        self.assertIn(self.client.get(reverse("api-v2-notifications"), {"route": 1}).status_code, (302, 401, 403))

    def test_limit_is_50(self):
        NotificationLog.objects.bulk_create([
            NotificationLog(event="delivered", audience="staff", recipient="a@b.com", status="sent", route=self.route)
            for _ in range(60)])
        self.assertEqual(len(self.get(self.admin, route=self.route.id).json()["notifications"]), 50)

    def test_mask_email(self):
        self.assertEqual(mask_email("julio@gmail.com"), "j***@gmail.com")
        self.assertEqual(mask_email("raro"), "***")
