"""Día 7: pedidos con dirección y bodegas (/api/v2/)."""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from logistics.domain.exceptions import PlanningError
from logistics.models import Depot, Order, UserProfile, Vehicle
from logistics.routing.graph import invalidate_graph


def make_user(username, role):
    user = User.objects.create_user(username=username, password="clave-segura-123")
    UserProfile.objects.create(user=user, role=role)
    return user


class OrdersApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        cls.dispatcher = make_user("despachador", UserProfile.Role.DISPATCHER)
        cls.driver = make_user("conductor", UserProfile.Role.DRIVER)

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.dispatcher)

    def create(self, **overrides):
        payload = {"recipient": "Lucía Morales", "phone": "5555-1234", "address": "12 calle 3-40, zona 1",
                   "reference": "Portón negro", "latitude": 14.8360, "longitude": -91.5170,
                   "weight_kg": 4.5, "package_count": 1, "priority": "high"}
        payload.update(overrides)
        return self.client.post(reverse("api-v2-orders"), json.dumps(payload), content_type="application/json")

    def test_create_assigns_nearest_node_on_the_server(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        order = response.json()["order"]
        self.assertEqual(order["node"]["code"], "quetzaltenango")
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["status_label"], "Pendiente")
        self.assertTrue(order["code"].startswith("PED-"))

    def test_validation_messages(self):
        cases = [
            ({"recipient": ""}, "destinatario"),
            ({"address": " "}, "dirección"),
            ({"latitude": None}, "ubicación"),
            ({"latitude": 19.43, "longitude": -99.13}, "fuera de Guatemala"),
            ({"weight_kg": 0}, "peso"),
            ({"weight_kg": "abc"}, "peso"),
            ({"package_count": 0}, "bulto"),
            ({"priority": "urgente"}, "Prioridad"),
        ]
        for overrides, message in cases:
            response = self.create(**overrides)
            self.assertEqual(response.status_code, 400, overrides)
            self.assertIn(message, response.json()["error"])

    def test_list_filters_search_and_counts(self):
        self.create(recipient="Farmacia San Rafael", latitude=14.5361, longitude=-91.6778)
        second = self.create(recipient="Mario Chávez")
        Order.objects.filter(id=second.json()["order"]["id"]).update(status=Order.Status.DELIVERED)

        data = self.client.get(reverse("api-v2-orders")).json()
        self.assertEqual(data["counts"], {"pending": 1, "delivered": 1, "all": 2})
        pending = self.client.get(reverse("api-v2-orders"), {"status": "pending"}).json()["orders"]
        self.assertEqual([o["recipient"] for o in pending], ["Farmacia San Rafael"])
        found = self.client.get(reverse("api-v2-orders"), {"q": "retalhuleu"}).json()["orders"]
        self.assertEqual(len(found), 1)  # búsqueda también por municipio (nodo)
        by_ids = self.client.get(reverse("api-v2-orders"), {"ids": str(second.json()["order"]["id"])}).json()
        self.assertEqual(len(by_ids["orders"]), 1)

    def test_driver_cannot_manage_orders(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(reverse("api-v2-orders")).status_code, 403)
        self.assertEqual(self.create().status_code, 403)

    def test_demo_seed_creates_depot_and_orders(self):
        call_command("seed_demo_data", stdout=StringIO())
        call_command("seed_demo_data", stdout=StringIO())
        self.assertEqual(Depot.objects.count(), 1)
        self.assertEqual(Order.objects.filter(is_demo=True).count(), 20)
        depots = self.client.get(reverse("api-v2-depots")).json()["depots"]
        self.assertEqual(depots[0]["name"], "Bodega Central")
        self.assertEqual(depots[0]["node"]["code"], "el-trebol")
