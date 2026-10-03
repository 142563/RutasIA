"""RUT-34: Configuración (bodegas, pilotos, camiones, usuarios) en /api/v2/fleet/."""
import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from logistics.models import Depot, Driver, UserProfile, Vehicle
from logistics.routing.graph import invalidate_graph

PASSWORD = "clave-segura-123"


def make_user(username, role):
    user = User.objects.create_user(username=username, password=PASSWORD)
    UserProfile.objects.create(user=user, role=role)
    return user


class FleetApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin1", UserProfile.Role.ADMIN)
        cls.dispatcher = make_user("despachador", UserProfile.Role.DISPATCHER)
        cls.driver_user = make_user("conductor", UserProfile.Role.DRIVER)

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.admin)

    def url(self, kind, item_id=None):
        if item_id is None:
            return reverse("api-v2-fleet", args=[kind])
        return reverse("api-v2-fleet-item", args=[kind, item_id])

    def post(self, kind, payload):
        return self.client.post(self.url(kind), json.dumps(payload), content_type="application/json")

    def patch(self, kind, item_id, payload):
        return self.client.patch(self.url(kind, item_id), json.dumps(payload), content_type="application/json")

    # --- permisos ---
    def test_invalid_kind_is_404(self):
        self.assertEqual(self.client.get(self.url("camiones")).status_code, 404)

    def test_permissions(self):
        self.client.force_login(self.dispatcher)
        for kind in ("depots", "drivers", "vehicles"):
            self.assertEqual(self.client.get(self.url(kind)).status_code, 200)
        self.assertEqual(self.client.get(self.url("users")).status_code, 403)
        self.assertEqual(self.post("depots", {"name": "X"}).status_code, 403)
        self.client.force_login(self.driver_user)
        self.assertEqual(self.client.get(self.url("depots")).status_code, 403)
        self.client.logout()
        self.assertIn(self.client.get(self.url("depots")).status_code, (302, 401, 403))

    # --- bodegas ---
    def test_depot_create_with_nearest_node(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        call_command("build_graph", "--estimate", stdout=StringIO())
        invalidate_graph()
        response = self.post("depots", {"name": "Central", "address": "Zona 12", "latitude": 14.6349, "longitude": -90.5069})
        self.assertEqual(response.status_code, 201)
        depot = response.json()["depot"]
        self.assertIsNotNone(depot["node"])
        self.assertTrue(depot["is_active"])

    def test_depot_without_graph_has_no_node(self):
        depot = self.post("depots", {"name": "Central", "latitude": 14.6, "longitude": -90.5}).json()["depot"]
        self.assertIsNone(depot["node"])

    def test_depot_validation(self):
        out = self.post("depots", {"name": "Mex", "latitude": 19.4, "longitude": -99.1})
        self.assertEqual(out.status_code, 400)
        self.assertIn("fuera de Guatemala", out.json()["error"])
        self.assertIn("nombre", self.post("depots", {"name": " ", "latitude": 14.6, "longitude": -90.5}).json()["error"])
        self.assertIn("ubicación", self.post("depots", {"name": "A"}).json()["error"])
        self.post("depots", {"name": "A", "latitude": 14.6, "longitude": -90.5})
        dup = self.post("depots", {"name": "A", "latitude": 14.6, "longitude": -90.5})
        self.assertEqual(dup.status_code, 400)
        self.assertIn("Ya existe", dup.json()["error"])

    def test_delete_deactivates_and_patch_reactivates(self):
        depot = Depot.objects.create(name="B", latitude=14.6, longitude=-90.5)
        response = self.client.delete(self.url("depots", depot.id))
        self.assertEqual(response.status_code, 200)
        depot.refresh_from_db()
        self.assertFalse(depot.is_active)
        self.patch("depots", depot.id, {"is_active": True})
        depot.refresh_from_db()
        self.assertTrue(depot.is_active)
        self.assertEqual(self.client.get(self.url("depots", 99999)).status_code, 404)

    # --- pilotos ---
    def test_driver_with_new_account(self):
        response = self.post("drivers", {"name": "Pedro", "phone": "5555", "license_number": "L-1",
                                         "username": "pedro", "password": "otra-clave-larga"})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertNotIn("password", json.dumps(body))
        driver = Driver.objects.get(license_number="L-1")
        self.assertEqual(driver.user.username, "pedro")
        self.assertEqual(driver.user.profile.role, UserProfile.Role.DRIVER)
        self.assertTrue(driver.user.check_password("otra-clave-larga"))

    def test_driver_validation_and_unique_license(self):
        short = self.post("drivers", {"name": "P", "license_number": "L-2", "username": "p", "password": "corta"})
        self.assertEqual(short.status_code, 400)
        self.assertIn("10 caracteres", short.json()["error"])
        self.assertFalse(Driver.objects.exists())
        self.post("drivers", {"name": "P", "license_number": "L-3"})
        dup = self.post("drivers", {"name": "Q", "license_number": "L-3"})
        self.assertEqual(dup.status_code, 400)
        self.assertIn("licencia", dup.json()["error"])

    def test_driver_link_unlink_existing_user(self):
        driver = Driver.objects.create(name="Ana", license_number="L-4")
        self.assertEqual(self.patch("drivers", driver.id, {"user_id": self.driver_user.id}).status_code, 200)
        driver.refresh_from_db()
        self.assertEqual(driver.user, self.driver_user)
        other = Driver.objects.create(name="Beto", license_number="L-5")
        self.assertEqual(self.patch("drivers", other.id, {"user_id": self.driver_user.id}).status_code, 400)
        self.assertEqual(self.patch("drivers", other.id, {"user_id": self.dispatcher.id}).status_code, 400)
        self.patch("drivers", driver.id, {"user_id": None})
        driver.refresh_from_db()
        self.assertIsNone(driver.user)

    # --- camiones ---
    def test_vehicle_create_defaults_and_plate_upper(self):
        driver = Driver.objects.create(name="Ana", license_number="L-6")
        response = self.post("vehicles", {"plate": "p-123abc", "capacity_kg": 1500, "driver_id": driver.id})
        self.assertEqual(response.status_code, 201)
        vehicle = response.json()["vehicle"]
        self.assertEqual(vehicle["plate"], "P-123ABC")
        self.assertGreater(vehicle["fuel_efficiency_km_l"], 0)
        self.assertEqual(vehicle["driver"]["name"], "Ana")

    def test_vehicle_validation(self):
        self.assertIn("capacidad", self.post("vehicles", {"plate": "A"}).json()["error"])
        self.assertIn("capacidad", self.post("vehicles", {"plate": "A", "capacity_kg": 0}).json()["error"])
        self.assertIn("capacidad", self.post("vehicles", {"plate": "A", "capacity_kg": "mucho"}).json()["error"])
        Vehicle.objects.create(plate="DUP", model="m", capacity_kg=1, fuel_efficiency_km_l=1, cost_per_km=1)
        self.assertIn("placa", self.post("vehicles", {"plate": "dup", "capacity_kg": 10}).json()["error"])

    def test_vehicle_patch_and_unassign_driver(self):
        driver = Driver.objects.create(name="Ana", license_number="L-7")
        vehicle = Vehicle.objects.create(plate="V1", model="m", capacity_kg=100, fuel_efficiency_km_l=5,
                                         cost_per_km=2, driver=driver)
        self.patch("vehicles", vehicle.id, {"capacity_kg": 900, "driver_id": None})
        vehicle.refresh_from_db()
        self.assertEqual(float(vehicle.capacity_kg), 900)
        self.assertIsNone(vehicle.driver)

    # --- usuarios ---
    def test_user_create_and_password_change(self):
        response = self.post("users", {"username": "nuevo", "full_name": "Nora Pérez", "role": "dispatcher",
                                       "password": "contraseña-larga"})
        self.assertEqual(response.status_code, 201)
        body = response.json()["user"]
        self.assertEqual(body["role"], "dispatcher")
        self.assertEqual(body["full_name"], "Nora Pérez")
        self.assertNotIn("password", body)
        user = User.objects.get(username="nuevo")
        self.patch("users", user.id, {"password": "otra-contraseña-larga"})
        user.refresh_from_db()
        self.assertTrue(user.check_password("otra-contraseña-larga"))
        self.assertEqual(self.patch("users", user.id, {"password": "corta"}).status_code, 400)

    def test_user_validation(self):
        self.assertEqual(self.post("users", {"username": "admin1", "role": "admin", "password": "contraseña-larga"}).status_code, 400)
        self.assertEqual(self.post("users", {"username": "x", "role": "jefe", "password": "contraseña-larga"}).status_code, 400)

    def test_admin_cannot_deactivate_or_demote_self(self):
        self.assertEqual(self.client.delete(self.url("users", self.admin.id)).status_code, 400)
        self.assertEqual(self.patch("users", self.admin.id, {"role": "dispatcher"}).status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.profile.role, UserProfile.Role.ADMIN)

    def test_deactivate_other_user(self):
        self.assertEqual(self.client.delete(self.url("users", self.dispatcher.id)).status_code, 200)
        self.dispatcher.refresh_from_db()
        self.assertFalse(self.dispatcher.is_active)
        self.assertTrue(User.objects.filter(pk=self.dispatcher.pk).exists())

    def test_list_shapes(self):
        self.assertEqual(len(self.client.get(self.url("users")).json()["users"]), 3)
        self.assertEqual(self.client.get(self.url("depots")).json()["depots"], [])
