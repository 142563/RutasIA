"""C2: una sesión por sí sola no autoriza las herramientas del motor."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.test import TestCase
from django.urls import reverse

from logistics.models import UserProfile


class RoutingRoleTests(TestCase):
    ENDPOINTS = [
        ("api-routing-nodes", "GET", "nodes"),
        ("api-routing-route", "POST", "route"),
        ("api-routing-compare", "POST", "compare"),
        ("api-routing-explore", "POST", "explore"),
        ("api-routes-optimize", "POST", "optimize"),
        ("api-routing-best-departure", "GET", "best_departure"),
        ("api-traffic-profile", "GET", "traffic_profile"),
    ]

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in UserProfile.Role.values:
            user = User.objects.create_user(role)
            UserProfile.objects.create(user=user, role=role)
            cls.users[role] = user
        cls.users["unprofiled"] = User.objects.create_user("sin-perfil")
        cls.users["superuser"] = User.objects.create_superuser("superusuario", password="prueba-local")

    def request(self, name, method):
        if method == "POST":
            return self.client.post(reverse(name), "{}", content_type="application/json")
        return self.client.get(reverse(name))

    def test_role_matrix_for_every_endpoint(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            for name, method, service in self.ENDPOINTS:
                with self.subTest(role=role, endpoint=name), patch(
                    "logistics.presentation.routing_views._run",
                    return_value=JsonResponse({"ok": True, "marker": service}),
                ) as run:
                    response = self.request(name, method)
                    self.assertEqual(run.call_count, int(role in ("admin", "dispatcher", "superuser")))
                    if role in ("admin", "dispatcher", "superuser"):
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()["marker"], service)
                        self.assertEqual(run.call_args.args[0].__name__, service)
                    else:
                        self.assertEqual(response.status_code, 403)
                        self.assertEqual(response.json()["error"], "No tienes permisos para esta acción.")

    def test_anonymous_requests_remain_unauthorized(self):
        for name, method, _service in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                self.assertEqual(self.request(name, method).status_code, 401)

    def test_driver_is_denied_before_parsing_or_running_search(self):
        self.client.force_login(self.users["driver"])
        for name, method, _service in self.ENDPOINTS:
            if method == "POST":
                with self.subTest(endpoint=name):
                    response = self.client.post(reverse(name), "bad-json", content_type="application/json")
                    self.assertEqual(response.status_code, 403)
