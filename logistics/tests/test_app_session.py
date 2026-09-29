"""Día 6: sesión por API para la app React, roles y servido de la SPA."""
import json
from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from logistics.models import Driver, UserProfile
from logistics.presentation.serializers import role_for


def make_user(username, role=None, password="clave-segura-123", **extra):
    user = User.objects.create_user(username=username, password=password, **extra)
    if role:
        UserProfile.objects.create(user=user, role=role)
    return user


class SessionApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        make_user("despachador", UserProfile.Role.DISPATCHER, first_name="Luis")

    def csrf_token(self):
        self.client.get(reverse("api-auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def post(self, name, payload, token=None):
        headers = {"HTTP_X_CSRFTOKEN": token} if token else {}
        return self.client.post(reverse(name), json.dumps(payload), content_type="application/json", **headers)

    def test_login_session_logout(self):
        self.assertEqual(self.client.get(reverse("api-auth-session")).status_code, 401)
        response = self.post("api-auth-login", {"username": "despachador", "password": "clave-segura-123"},
                             self.csrf_token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "dispatcher")
        self.assertEqual(response.json()["user"]["role_label"], "Despachador")

        session = self.client.get(reverse("api-auth-session")).json()
        self.assertEqual(session["user"]["full_name"], "Luis")

        # login rota el token CSRF: se vuelve a leer la cookie
        logout = self.post("api-auth-logout", {}, self.client.cookies["csrftoken"].value)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get(reverse("api-auth-session")).status_code, 401)

    def test_wrong_password(self):
        response = self.post("api-auth-login", {"username": "despachador", "password": "otra"}, self.csrf_token())
        self.assertEqual(response.status_code, 400)
        self.assertIn("incorrectos", response.json()["error"])

    def test_login_requires_csrf(self):
        response = self.post("api-auth-login", {"username": "despachador", "password": "clave-segura-123"})
        self.assertEqual(response.status_code, 403)

    def test_api_redirect_to_login_becomes_401_json(self):
        response = self.client.get(reverse("api-routing-nodes"))
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])

    def test_config_is_public(self):
        data = self.client.get(reverse("api-config")).json()
        self.assertIn("google_maps_api_key", data)

    def test_config_hints_demo_users_only_in_debug(self):
        with self.settings(DEBUG=False):
            self.assertFalse(self.client.get(reverse("api-config")).json()["demo_users"])
        with self.settings(DEBUG=True):
            self.assertTrue(self.client.get(reverse("api-config")).json()["demo_users"])


class RoleTests(TestCase):
    def test_user_without_profile_gets_least_privilege(self):
        self.assertEqual(role_for(make_user("sinperfil")), UserProfile.Role.DRIVER)
        root = User.objects.create_superuser("root", password="x-123456789")
        self.assertEqual(role_for(root), UserProfile.Role.ADMIN)

    def test_legacy_roles_are_migrated(self):
        migration = import_module("logistics.migrations.0008_roles_dispatcher_driver")
        for i, old in enumerate(("supervisor", "operator")):
            UserProfile.objects.create(user=make_user(f"viejo{i}"), role=old)
        migration.forwards(apps, None)
        self.assertEqual(set(UserProfile.objects.values_list("role", flat=True)), {"dispatcher"})

    def test_seed_demo_users_requires_password_and_links_driver(self):
        with self.assertRaisesMessage(CommandError, "contraseña"):
            call_command("seed_demo_users", "--password", "corta", stdout=StringIO())
        call_command("seed_demo_users", "--password", "una-clave-larga-1", stdout=StringIO())
        call_command("seed_demo_users", "--password", "una-clave-larga-1", stdout=StringIO())
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(User.objects.get(username="despachador").profile.role, UserProfile.Role.DISPATCHER)
        self.assertTrue(User.objects.get(username="admin").is_superuser)
        driver = Driver.objects.get(user__username="conductor")
        self.assertEqual(driver.user.profile.role, UserProfile.Role.DRIVER)


class SpaTests(TestCase):
    def test_serves_help_page_when_build_is_missing(self):
        with TemporaryDirectory() as tmp, override_settings(FRONTEND_DIST=Path(tmp)):
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "npm run build")

    def test_serves_index_for_client_routes(self):
        with TemporaryDirectory() as tmp, override_settings(FRONTEND_DIST=Path(tmp)):
            (Path(tmp) / "app").mkdir()
            (Path(tmp) / "app" / "index.html").write_text("<div id=root></div>", encoding="utf-8")
            for path in ("/", "/pedidos", "/laboratorio/"):
                response = self.client.get(path)
                self.assertContains(response, "<div id=root></div>", msg_prefix=path)
            self.assertIn("csrftoken", response.cookies)

    def test_classic_ui_moved_to_clasico(self):
        self.client.force_login(make_user("viejo", UserProfile.Role.ADMIN))
        response = self.client.get("/clasico/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/logistics/app.")  # app.js o app.<hash>.js
