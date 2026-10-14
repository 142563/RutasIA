"""Tráfico en vivo al planificar (híbrido): Google mide los tramos que eligió A*.

Nunca se llama a Google de verdad: un cliente falso reemplaza a RoutesClient.
"""
import json
import time
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from logistics.application import live_planning
from logistics.application.live_planning import CALIBRATED, LIVE
from logistics.application.routing import get_graph
from logistics.models import Depot, Driver, Order, Route, UserProfile, Vehicle
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.google import RouteResult, RoutesApiError
from logistics.routing.graph import invalidate_graph
from logistics.routing.traffic import GT_TZ


class FakeClient:
    """Cada tramo dura `minutes` minutos en vivo. Registra cada consulta."""
    calls: list = []
    minutes = 25.0
    delay = 0.0
    fail = False

    def __init__(self, *args, **kwargs):
        pass

    def compute_route(self, origin, destination, intermediates=(), departure_time=None, traffic=True, geometry=True):
        FakeClient.calls.append({"departure": departure_time, "traffic": traffic, "geometry": geometry,
                                 "intermediates": len(intermediates)})
        if FakeClient.delay:
            time.sleep(FakeClient.delay)
        if FakeClient.fail:
            raise RoutesApiError("falla simulada")
        return RouteResult(FakeClient.minutes * 60, FakeClient.minutes * 60, 1000)


def no_key(*args, **kwargs):
    raise RoutesApiError("Falta GOOGLE_ROUTES_API_KEY")


@override_settings(LIVE_TRAFFIC=True, LIVE_TRAFFIC_TIMEOUT_S=5, LIVE_TRAFFIC_DAILY_REQUESTS=1000)
class LivePlanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        invalidate_graph()
        call_command("seed_demo_data", stdout=StringIO())
        cls.depot = Depot.objects.get(name="Bodega Central")
        cls.user = User.objects.create_user(username="despachador", password="clave-segura-123")
        UserProfile.objects.create(user=cls.user, role=UserProfile.Role.DISPATCHER)

    def setUp(self):
        cache.clear()
        invalidate_graph()
        FakeClient.calls, FakeClient.minutes, FakeClient.delay, FakeClient.fail = [], 25.0, 0.0, False
        self.client.force_login(self.user)
        self.ids = list(Order.objects.filter(is_demo=True, status=Order.Status.PENDING)
                        .order_by("id").values_list("id", flat=True)[:4])
        patcher = patch.object(live_planning, "RoutesClient", FakeClient)
        patcher.start()
        self.addCleanup(patcher.stop)

    def plan(self, departure="2026-10-20T08:00", **extra):
        response = self.client.post(reverse("api-v2-routes-plan"), json.dumps(
            {"depot_id": self.depot.id, "order_ids": self.ids, "departure": departure, **extra}),
            content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_minutes_and_etas_come_from_google_live(self):
        data = self.plan()
        self.assertEqual(data["traffic_source"], LIVE)
        self.assertIsNotNone(data["traffic_queried_at"])
        for key in ("fastest", "shortest"):
            variant = data[key]
            self.assertTrue(all(leg["minutes"] == 25.0 for leg in variant["legs"]))
            self.assertEqual(variant["driving_minutes"], 25.0 * len(variant["legs"]))
            etas = [datetime.fromisoformat(s["eta"]) for s in variant["stops"]]
            # Llegada = salida + 25 min de manejo, y cada parada suma 10 min de servicio
            start = datetime.fromisoformat(data["departure"])
            for i, eta in enumerate(etas):
                self.assertEqual(eta, start + timedelta(minutes=25 * (i + 1) + 10 * i))
        # Solo tiempos (sin geometría), con tráfico y por los nodos de nuestro A*
        self.assertTrue(all(c["traffic"] and not c["geometry"] for c in FakeClient.calls))

    def test_future_departure_is_sent_to_google(self):
        self.plan("2030-01-07T09:30")
        first = min(c["departure"] for c in FakeClient.calls)
        self.assertEqual(first.astimezone(GT_TZ).replace(tzinfo=None), datetime(2030, 1, 7, 9, 30))

    def test_past_departure_uses_now(self):
        before = datetime.now(tz=GT_TZ)
        self.plan("2020-01-07T09:30")
        self.assertTrue(all(c["departure"] >= before for c in FakeClient.calls))

    def test_cache_avoids_repeating_identical_queries(self):
        self.plan()
        first = len(FakeClient.calls)
        self.assertGreater(first, 0)
        self.plan()
        self.assertEqual(len(FakeClient.calls), first)

    def test_google_failure_falls_back_to_calibrated_without_mixing(self):
        with override_settings(LIVE_TRAFFIC=False):
            calibrated = self.plan()
        FakeClient.fail = True
        data = self.plan()
        self.assertEqual(data["traffic_source"], CALIBRATED)
        self.assertTrue(data["traffic_note"])
        self.assertEqual(data["fastest"]["driving_minutes"], calibrated["fastest"]["driving_minutes"])

    def test_slow_google_falls_back_to_calibrated(self):
        FakeClient.delay = 0.5
        with override_settings(LIVE_TRAFFIC_TIMEOUT_S=0.2):
            data = self.plan()
        self.assertEqual(data["traffic_source"], CALIBRATED)
        self.assertIn("tardó", data["traffic_note"])

    def test_missing_key_falls_back_to_calibrated(self):
        with patch.object(live_planning, "RoutesClient", no_key):
            data = self.plan()
        self.assertEqual(data["traffic_source"], CALIBRATED)
        self.assertIn("llave", data["traffic_note"])

    def test_daily_cap(self):
        with override_settings(LIVE_TRAFFIC_DAILY_REQUESTS=1):
            data = self.plan()
        self.assertEqual(data["traffic_source"], CALIBRATED)
        self.assertEqual(FakeClient.calls, [])

    def test_confirmed_route_stores_source_and_query_time(self):
        self.plan()
        driver = Driver.objects.first()
        vehicle = Vehicle.objects.filter(capacity_kg__gte=500).first()
        calls = len(FakeClient.calls)
        response = self.client.post(reverse("api-v2-routes"), json.dumps(
            {"depot_id": self.depot.id, "order_ids": self.ids, "departure": "2026-10-20T08:00", "criterion": "time",
             "driver_id": driver.id, "vehicle_id": vehicle.id}), content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        route = Route.objects.get()
        self.assertEqual(route.traffic_source, LIVE)
        self.assertIsNotNone(route.traffic_queried_at)
        self.assertEqual(route.driving_minutes, 25.0 * len(route.legs))
        self.assertEqual(len(FakeClient.calls), calls)  # confirmar reutiliza la caché
        self.assertEqual(response.json()["route"]["traffic_source"], LIVE)

    def test_fifty_stops_under_thirty_seconds_with_slow_google(self):
        """Tesis: < 30 s con 50 paradas, aun si cada consulta a Google tarda 0.3 s."""
        FakeClient.delay = 0.3
        codes = [c for c in get_graph().codes if c != "ciudad-guatemala"]
        stops = (codes * 2)[:50]
        started = time.perf_counter()
        response = self.client.post(reverse("api-routes-optimize"), json.dumps(
            {"depot": "ciudad-guatemala", "stops": stops, "departure": "2026-10-20T08:00", "return_to_depot": True}),
            content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["traffic_source"], LIVE)
        self.assertLess(time.perf_counter() - started, 30)
        self.assertLess(data["response_seconds"], 30)


class TestsNeverCallGoogleTests(TestCase):
    def test_live_traffic_is_off_while_testing(self):
        self.assertTrue(settings.TESTING)
        self.assertFalse(settings.LIVE_TRAFFIC)
