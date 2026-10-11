import json
from io import StringIO
from unittest.mock import patch

import httpx
from django.contrib.auth.models import User
from django.urls import reverse
from logistics.models import UserProfile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from logistics.models import Edge, RouteSample
from logistics.routing.build import fill_polylines
from logistics.routing.google import ROUTE_FIELD_MASK, RouteResult, RoutesClient
from logistics.tests.test_build_graph import FakeRoutesClient, make_node


class GeometryClientTests(SimpleTestCase):
    def test_requests_and_parses_high_quality_encoded_geometry(self):
        def handler(request):
            self.assertEqual(request.headers["X-Goog-FieldMask"], ROUTE_FIELD_MASK)
            body = json.loads(request.content)
            self.assertEqual(body["routingPreference"], "TRAFFIC_UNAWARE")
            self.assertEqual(body["polylineQuality"], "HIGH_QUALITY")
            return httpx.Response(200, json={"routes": [{"duration": "60s", "distanceMeters": 1000,
                                                       "polyline": {"encodedPolyline": "??AA"}}]})
        client = RoutesClient("mock", http=httpx.Client(transport=httpx.MockTransport(handler)))
        self.assertEqual(client.compute_route((0, 0), (1, 1), traffic=False).polyline, "??AA")


class GeometryTests(TestCase):
    def setUp(self):
        self.a = make_node("a", 14.6, -90.5)
        self.b = make_node("b", 14.7, -90.6)
        self.edge = Edge.objects.create(origin=self.a, destination=self.b, distance_km=5,
                                       duration_free_min=10, source="manual")

    def test_fill_preserves_weights_and_uses_cache_without_second_call(self):
        client = FakeRoutesClient()
        report = fill_polylines(client)
        self.assertEqual(report.requests, 1)
        self.edge.refresh_from_db()
        self.assertTrue(self.edge.polyline)
        self.assertEqual((self.edge.distance_km, self.edge.duration_free_min, self.edge.source), (5, 10, "manual"))
        self.edge.polyline = ""
        self.edge.save(update_fields=["polyline"])
        second = FakeRoutesClient()
        self.assertEqual(fill_polylines(second).requests, 0)
        self.assertEqual(fill_polylines(second).edges_updated, 0)

    def test_empty_geometry_is_not_saved_and_inactive_edges_are_skipped(self):
        with patch.object(FakeRoutesClient, "compute_route", return_value=RouteResult(60, 60, 1000)):
            self.assertEqual(fill_polylines(FakeRoutesClient()).edges_skipped, 1)
        self.assertFalse(RouteSample.objects.exists())
        self.edge.is_active = False
        self.edge.save(update_fields=["is_active"])
        self.assertEqual(fill_polylines(FakeRoutesClient()).requests, 0)

    def test_api_requires_session_and_respects_direction_and_limit(self):
        url = "/api/routing/geometry/"
        self.assertNotEqual(self.client.get(url).status_code, 200)
        # La geometría es de despacho (RUT-86): un usuario sin rol de despacho recibe 403
        plain = User.objects.create_user("sin-rol")
        UserProfile.objects.create(user=plain, role=UserProfile.Role.DRIVER)
        self.client.force_login(plain)
        self.assertEqual(self.client.get(reverse("api-routing-geometry")).status_code, 403)
        dispatcher = User.objects.create_user("geometry")
        UserProfile.objects.create(user=dispatcher, role=UserProfile.Role.DISPATCHER)
        self.client.force_login(dispatcher)
        self.edge.polyline = "??AA"
        self.edge.save(update_fields=["polyline"])
        data = self.client.get(url, {"edges": json.dumps([["a", "b"], ["b", "a"]])}).json()
        self.assertEqual(data["edges"], [{"from": "a", "to": "b", "polyline": "??AA"}])
        for invalid in ["bad", "{}", json.dumps([["a", "b"]] * 501), '[[1,"b"]]']:
            self.assertEqual(self.client.get(url, {"edges": invalid}).status_code, 400)

    def test_command_only_fills_geometry(self):
        with patch("logistics.management.commands.build_graph.RoutesClient", return_value=FakeRoutesClient()), patch(
            "logistics.management.commands.build_graph.apply_road_classes"
        ) as apply:
            call_command("build_graph", "--polylines-only", stdout=StringIO())
            apply.assert_not_called()
        self.edge.refresh_from_db()
        self.assertTrue(self.edge.polyline)
