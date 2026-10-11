"""Diseño de los correos (RUT-68): cada plantilla se renderiza con su contexto real y trae lo esencial."""
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from logistics.application import notifications as n
from logistics.models import (
    Depot, Driver, Incident, Node, Order, RerouteProposal, Route, RouteStop, UserProfile,
)

POST = "logistics.application.notifications.transport.httpx.post"


def ok_response(*args, **kwargs):
    return mock.Mock(raise_for_status=mock.Mock(), json=lambda: {"id": "re_1"})


def mails(post):
    out = []
    for call in post.call_args_list:
        body = call.kwargs["json"]
        out.extend(body if isinstance(body, list) else [body])
    return out


@override_settings(RESEND_API_KEY="test", NOTIFY_FROM="enruta <a@enruta.world>", SITE_URL="https://enruta.test")
class EmailDesignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name, role, email):
            u = User.objects.create_user(username=name, password="clave-segura-123", email=email,
                                         first_name=name.capitalize(), last_name="Prueba")
            UserProfile.objects.create(user=u, role=role)
            return u
        role = UserProfile.Role
        cls.admin = user("admin1", role.ADMIN, "admin@example.com")
        cls.creator = user("desp1", role.DISPATCHER, "despachador@example.com")
        cls.driver_user = user("carlos", role.DRIVER, "carlos@example.com")
        cls.depot = Depot.objects.create(name="Bodega Zona 12", latitude=14.6, longitude=-90.5)
        cls.driver = Driver.objects.create(user=cls.driver_user, name="Carlos Pérez Gómez", license_number="A-1")
        cls.node = Node.objects.create(code="antigua", name="Antigua Guatemala", kind=Node.Kind.CABECERA,
                                       department="SA", latitude=14.56, longitude=-90.73)
        now = timezone.now()
        cls.route = Route.objects.create(
            depot=cls.depot, driver=cls.driver, departure_at=now + timedelta(hours=1), driving_minutes=95,
            total_km=48.3, finish_at=now + timedelta(hours=4), created_by=cls.creator, service_min=10,
            status=Route.Status.IN_PROGRESS, started_at=now - timedelta(minutes=100))
        cls.order = Order.objects.create(
            recipient="Marta Ruiz", phone="4444-9999", address="3a calle 12-34, zona 2, Antigua Guatemala",
            latitude=14.56, longitude=-90.73, weight_kg=Decimal("4"), recipient_email="marta@example.com",
            node=cls.node, status=Order.Status.ASSIGNED)
        cls.stop = RouteStop.objects.create(route=cls.route, order=cls.order, sequence=1,
                                            eta=now + timedelta(hours=2))

    def run_event(self, fn, *args):
        with mock.patch(POST, side_effect=ok_response) as post:
            sent = fn(*args)
        self.assertTrue(sent, fn.__name__)
        return mails(post)

    def check(self, name, mail_list, label):
        self.assertTrue(mail_list)
        mail = mail_list[0]
        self.assertIn(label, mail["html"], name)
        self.assertRegex(mail["html"], r"display:none[^>]*>[^<\s]", f"{name}: sin preheader")
        self.assertIn("Es un aviso automático", mail["html"])
        self.assertNotRegex(mail["text"], r"<[a-z/][^>]*>", f"{name}: etiquetas HTML en el texto")
        self.assertIn(label.upper(), mail["text"].upper())
        self.assertNotIn("{{", mail["html"] + mail["text"])
        out = os.environ.get("EMAIL_PREVIEW_DIR")
        if out:  # vistas previas para revisar el diseño a ojo
            Path(out).mkdir(parents=True, exist_ok=True)
            Path(out, f"{name}.html").write_text(mail["html"], encoding="utf-8")
            Path(out, f"{name}.txt").write_text(mail["text"], encoding="utf-8")

    def test_customer_emails(self):
        self.check("order_received", self.run_event(n.customer.notify_order_received, self.order.id), "Recibido")
        self.check("route_scheduled", self.run_event(n.customer.notify_route_scheduled, self.route.id), "Programado")
        started = self.run_event(n.customer.notify_route_started, self.route.id)
        self.check("route_started", started, "En camino")
        self.assertIn("Carlos", started[0]["html"])
        self.assertNotIn("Pérez", started[0]["html"])
        self.stop.status, self.stop.reason = RouteStop.Status.FAILED, "Nadie en casa"
        self.stop.save()
        failed = self.run_event(n.customer.notify_delivery_failed, self.stop.id)
        self.check("delivery_failed", failed, "No entregado")
        self.assertIn("Nadie en casa", failed[0]["text"])
        self.stop.status, self.stop.delivered_at = RouteStop.Status.DELIVERED, timezone.now()
        self.stop.save()
        self.check("delivered", self.run_event(n.customer.notify_delivered, self.stop.id), "Entregado")

    def test_staff_emails(self):
        self.check("staff_route_assigned", self.run_event(n.staff.notify_route_assigned, self.route.id), "Nueva ruta")
        self.stop.status, self.stop.reason = RouteStop.Status.FAILED, "Dirección no existe"
        self.stop.save()
        self.check("staff_delivery_failed", self.run_event(n.staff.notify_delivery_failed, self.stop.id),
                   "No entregado")
        incident = Incident.objects.create(kind=Incident.Kind.LANDSLIDE, blocked=True, note="Derrumbe en el km 52",
                                           reported_by=self.driver_user)
        self.check("staff_incident_reported", self.run_event(n.staff.notify_incident_reported, incident.id),
                   "Acción requerida")
        proposal = RerouteProposal.objects.create(
            route=self.route, incident=incident, current_minutes=80, proposed_minutes=62,
            summary="Nueva ruta por Palín: -18 min")
        self.check("staff_reroute_pending", self.run_event(n.staff.notify_reroute_pending, proposal.id),
                   "Acción requerida")
        proposal.status = RerouteProposal.Status.ACCEPTED
        proposal.save()
        self.check("staff_reroute_approved", self.run_event(n.staff.notify_reroute_approved, proposal.id),
                   "Ruta actualizada")
        Route.objects.filter(pk=self.route.pk).update(status=Route.Status.COMPLETED, completed_at=timezone.now())
        done = self.run_event(n.staff.notify_route_completed, self.route.id)
        self.check("staff_route_completed", done, "Terminada")
        self.assertIn("Dirección no existe", done[0]["html"])
        Route.objects.filter(pk=self.route.pk).update(status=Route.Status.CANCELED)
        self.check("staff_route_canceled",
                   self.run_event(n.staff.notify_route_canceled, self.route.id, self.driver.id), "Cancelada")
