"""RUT-40: archivado de pedidos que dejó la interfaz anterior."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from logistics.models import Depot, Order, Route, RouteStop


def make_order(status, located=True, **extra):
    data = {"weight_kg": Decimal("5"), "status": status}
    if located:
        data.update(latitude=14.6, longitude=-90.5)
    data.update(extra)
    return Order.objects.create(**data)


class ArchiveLegacyOrdersTests(TestCase):
    def setUp(self):
        self.legacy_pending = make_order(Order.Status.PENDING, located=False)
        self.legacy_transit = make_order(Order.Status.IN_TRANSIT, located=False)
        self.legacy_delivered = make_order(Order.Status.DELIVERED, located=False)
        self.stuck = make_order(Order.Status.IN_TRANSIT, reference="cerca del parque")
        self.fresh = make_order(Order.Status.PENDING)
        self.routed = make_order(Order.Status.IN_TRANSIT)
        depot = Depot.objects.create(name="B", latitude=14.6, longitude=-90.5)
        now = timezone.now()
        route = Route.objects.create(depot=depot, status=Route.Status.IN_PROGRESS, departure_at=now,
                                     driving_minutes=60, total_km=30, finish_at=now + timedelta(hours=2))
        RouteStop.objects.create(route=route, order=self.routed, sequence=1, eta=timezone.now() + timedelta(hours=1))

    def run_command(self, *args):
        out = StringIO()
        call_command("archive_legacy_orders", *args, stdout=out)
        return out.getvalue()

    def test_without_apply_only_lists(self):
        text = self.run_command()
        self.assertIn("Pedidos viejos abiertos: 3", text)
        self.assertIn(self.legacy_pending.code, text)
        self.assertEqual(Order.objects.filter(status=Order.Status.CANCELED).count(), 0)

    def test_apply_cancels_legacy_and_keeps_the_rest(self):
        self.run_command("--apply")
        for order in (self.legacy_pending, self.legacy_transit, self.stuck):
            order.refresh_from_db()
            self.assertEqual(order.status, Order.Status.CANCELED)
            self.assertIn("Archivado", order.reference)
        self.stuck.refresh_from_db()
        self.assertIn("cerca del parque", self.stuck.reference)
        for order, status in ((self.legacy_delivered, Order.Status.DELIVERED),
                              (self.fresh, Order.Status.PENDING), (self.routed, Order.Status.IN_TRANSIT)):
            order.refresh_from_db()
            self.assertEqual(order.status, status)
        self.assertEqual(Order.objects.count(), 6)

    def test_second_run_finds_nothing(self):
        self.run_command("--apply")
        self.assertIn("Pedidos viejos abiertos: 0", self.run_command("--apply"))
