from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from logistics.models import Depot, Edge, Node, Order, Route, RouteStop, TrafficProfile


class PrepararCommandTests(TestCase):
    def run_preparar(self):
        out = StringIO()
        call_command("preparar", password="demo-password-123", sin_frontend=True, stdout=out)
        return out.getvalue()

    def test_prepares_everything_offline(self):
        output = self.run_preparar()
        self.assertTrue(Node.objects.exists())
        self.assertTrue(Edge.objects.exists())
        self.assertTrue(TrafficProfile.objects.exists())
        self.assertTrue(Depot.objects.exists())
        self.assertTrue(Order.objects.filter(is_demo=True).exists())
        for username in ("admin", "despachador", "conductor"):
            self.assertTrue(User.objects.get(username=username).check_password("demo-password-123"))
        self.assertIn("Todo listo", output)
        # Historia de demostración: una ruta en curso con la primera entrega hecha
        route = Route.objects.get()
        self.assertEqual(route.status, Route.Status.IN_PROGRESS)
        self.assertEqual(route.driver.user.username, "conductor")
        self.assertEqual(route.stops.filter(status=RouteStop.Status.DELIVERED).count(), 1)
        self.assertTrue(Order.objects.filter(status=Order.Status.PENDING).exists())

    def test_second_run_keeps_existing_edges(self):
        self.run_preparar()
        Edge.objects.update(source=Edge.Source.GOOGLE)
        output = self.run_preparar()
        # No reemplaza datos reales por estimados
        self.assertFalse(Edge.objects.exclude(source=Edge.Source.GOOGLE).exists())
        self.assertIn("se conservan", output)
        self.assertEqual(Route.objects.count(), 1)  # no repite la historia de demostración
