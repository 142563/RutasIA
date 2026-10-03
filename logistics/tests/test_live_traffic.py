"""RUT-39: verificar una ruta con el tráfico de ahora (Google mockeado, nunca se llama de verdad)."""
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from logistics.application.live_traffic import MAX_INTERMEDIATES, sample_intermediates
from logistics.models import Depot, Driver, Node, Order, Route, RouteStop, UserProfile


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeHttp:
    """Sustituye a httpx.Client: guarda lo que se le envía y responde segundos fijos por consulta."""

    def __init__(self, seconds=(1800, 1800), status=200):
        self.seconds = list(seconds)
        self.status = status
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append((url, json, headers))
        if self.status != 200:
            return FakeResponse(self.status, {"error": "boom"})
        secs = self.seconds[len(self.calls) - 1]
        return FakeResponse(200, {"routes": [{"duration": f"{secs}s", "staticDuration": f"{secs}s", "distanceMeters": 5000}]})


def user_with(name, role):
    user = User.objects.create_user(username=name, password="clave-segura-123")
    UserProfile.objects.create(user=user, role=role)
    return user


class SampleTests(SimpleTestCase):
    def test_few_intermediates_kept(self):
        self.assertEqual(sample_intermediates(["a", "b", "c", "d"]), ["b", "c"])
        self.assertEqual(sample_intermediates(["a", "b"]), [])

    def test_many_intermediates_subsampled_keeping_order(self):
        codes = [f"n{i}" for i in range(100)]
        out = sample_intermediates(codes)
        self.assertEqual(len(out), MAX_INTERMEDIATES)
        self.assertEqual(out, sorted(out, key=lambda c: int(c[1:])))
        self.assertEqual(out[0], "n1")
        self.assertEqual(out[-1], "n98")


@override_settings(GOOGLE_ROUTES_API_KEY="clave-falsa")
class LiveCheckApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for code, lat, lng in [("a", 14.6, -90.5), ("b", 14.7, -90.4), ("c", 14.8, -90.3), ("d", 14.9, -90.2)]:
            Node.objects.create(code=code, name=code.upper(), kind=Node.Kind.CABECERA, department="01", latitude=lat, longitude=lng)
        cls.depot = Depot.objects.create(name="Bodega", latitude=14.6, longitude=-90.5)
        cls.admin = user_with("admin1", UserProfile.Role.ADMIN)
        cls.dispatcher = user_with("desp", UserProfile.Role.DISPATCHER)
        cls.user_a = user_with("carlos", UserProfile.Role.DRIVER)
        cls.user_b = user_with("marta", UserProfile.Role.DRIVER)
        cls.driver_a = Driver.objects.create(user=cls.user_a, name="Carlos", license_number="A-1")
        cls.driver_b = Driver.objects.create(user=cls.user_b, name="Marta", license_number="B-1")

    def setUp(self):
        cache.clear()
        self.route, self.stops = self.make_route(self.driver_a)

    def make_route(self, driver):
        dep = timezone.now().replace(microsecond=0)
        etas = [dep + timedelta(minutes=30), dep + timedelta(minutes=70)]
        legs = [
            {"nodes": ["a", "b", "c"], "minutes": 30, "km": 20, "arrive_at": etas[0].isoformat()},
            {"nodes": ["c", "d"], "minutes": 30, "km": 15, "arrive_at": etas[1].isoformat()},
            {"nodes": ["d", "a"], "minutes": 50, "km": 40, "arrive_at": (dep + timedelta(minutes=130)).isoformat()},
        ]
        route = Route.objects.create(
            depot=self.depot, driver=driver, departure_at=dep, driving_minutes=110, total_km=75,
            finish_at=dep + timedelta(minutes=130), legs=legs, status=Route.Status.IN_PROGRESS)
        stops = []
        for i, eta in enumerate(etas, start=1):
            order = Order.objects.create(
                recipient=f"Cliente {i}", phone="5555-0001", address="Zona 1", latitude=14.6, longitude=-90.5,
                weight_kg=Decimal("5"), status=Order.Status.ASSIGNED)
            stops.append(RouteStop.objects.create(route=route, order=order, sequence=i, eta=eta))
        return route, stops

    def check(self, route=None, http=None):
        http = http or FakeHttp((1800, 1800, 3000))
        with mock.patch("logistics.routing.google.httpx.Client", return_value=http):
            response = self.client.post(reverse("api-v2-route-live-check", kwargs={"route_id": (route or self.route).id}))
        return response, http

    def test_body_uses_our_astar_nodes_as_intermediates(self):
        self.client.force_login(self.dispatcher)
        response, http = self.check()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(http.calls), 3)  # 2 paradas + regreso
        url, body, headers = http.calls[0]
        self.assertTrue(url.endswith("computeRoutes"))
        self.assertEqual(headers["X-Goog-Api-Key"], "clave-falsa")
        self.assertEqual(body["routingPreference"], "TRAFFIC_AWARE_OPTIMAL")
        self.assertIn("departureTime", body)
        self.assertEqual(body["origin"]["location"]["latLng"], {"latitude": 14.6, "longitude": -90.5})
        self.assertEqual(body["destination"]["location"]["latLng"], {"latitude": 14.8, "longitude": -90.3})
        self.assertEqual(body["intermediates"], [{"via": True, "location": {"latLng": {"latitude": 14.7, "longitude": -90.4}}}])
        self.assertNotIn("intermediates", http.calls[1][1])  # tramo directo c -> d

    def test_differences_and_late_message(self):
        self.client.force_login(self.admin)
        data = self.check()[0].json()
        self.assertTrue(data["ok"])
        self.assertEqual([x["google_minutes"] for x in data["legs"]], [30.0, 30.0, 50.0])
        self.assertEqual(data["diff_minutes"], 0.0)
        self.assertTrue(data["confirmed"])
        self.assertIn("confirma", data["message"])

        cache.clear()
        data = self.check(http=FakeHttp((3300, 1800, 3000)))[0].json()  # 55 min vs 30 estimados en el tramo 1
        self.assertEqual(data["legs"][0]["diff_minutes"], 25.0)
        self.assertFalse(data["confirmed"])
        self.assertIn("más tráfico del previsto", data["message"])
        self.assertIn("25 min más tarde", data["message"])
        # La nueva hora de cada parada arrastra el retraso acumulado; lo guardado no cambia.
        self.assertEqual(data["stops"][0]["diff_minutes"], 25.0)
        self.assertEqual(data["stops"][1]["diff_minutes"], 25.0)
        self.assertNotEqual(data["stops"][0]["stored_eta"], data["stops"][0]["google_eta"])
        self.stops[0].refresh_from_db()
        self.assertEqual(self.stops[0].eta.isoformat(), data["stops"][0]["stored_eta"])

    def test_only_pending_legs_are_checked(self):
        self.stops[0].status = RouteStop.Status.DELIVERED
        self.stops[0].save()
        self.client.force_login(self.dispatcher)
        data, http = self.check()
        data = data.json()
        self.assertEqual(len(http.calls), 2)
        self.assertEqual([x["index"] for x in data["legs"]], [1, 2])

    def test_cache_five_minutes(self):
        self.client.force_login(self.dispatcher)
        first, http = self.check()
        self.assertFalse(first.json()["cached"])
        second, http2 = self.check()
        self.assertTrue(second.json()["cached"])
        self.assertEqual(http2.calls, [])
        self.assertEqual(second.json()["checked_at"], first.json()["checked_at"])

    @override_settings(GOOGLE_ROUTES_API_KEY="")
    def test_without_key_returns_400(self):
        self.client.force_login(self.dispatcher)
        response, _ = self.check()
        self.assertEqual(response.status_code, 400)
        self.assertIn("llave de Google", response.json()["error"])

    def test_google_error_returns_502(self):
        self.client.force_login(self.dispatcher)
        response, _ = self.check(http=FakeHttp(status=500))
        self.assertEqual(response.status_code, 502)
        self.assertIn("Google", response.json()["error"])

    def test_permissions(self):
        self.client.force_login(self.user_a)
        self.assertEqual(self.check()[0].status_code, 200)
        cache.clear()
        self.client.force_login(self.user_b)
        self.assertEqual(self.check()[0].status_code, 404)
        self.client.logout()
        self.assertNotEqual(self.check()[0].status_code, 200)

    def test_finished_route_has_nothing_to_check(self):
        self.route.status = Route.Status.COMPLETED
        self.route.save()
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.check()[0].status_code, 400)


class RefreshTrafficCommandTests(SimpleTestCase):
    def test_runs_calibration_without_asking(self):
        with mock.patch("logistics.management.commands.refresh_traffic.call_command") as call:
            out = StringIO()
            call_command("refresh_traffic", stdout=out)
        self.assertEqual(call.call_args.args[0], "calibrate_traffic")
        self.assertTrue(call.call_args.kwargs["yes"])
        self.assertNotIn("refresh", call.call_args.kwargs)  # respeta la caché de 7 días
