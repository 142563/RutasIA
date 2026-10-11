import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from logistics.models import Depot, Driver, Route, UserProfile, VehiclePosition
from logistics.tests.test_driver_api import make_user


class PositionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("gps-driver", UserProfile.Role.DRIVER)
        cls.other_user = make_user("gps-other", UserProfile.Role.DRIVER)
        cls.dispatcher = make_user("gps-dispatcher", UserProfile.Role.DISPATCHER)
        cls.admin = make_user("gps-admin", UserProfile.Role.ADMIN)
        cls.orphan = make_user("gps-orphan", UserProfile.Role.DRIVER)
        cls.driver = Driver.objects.create(user=cls.user, name="GPS", license_number="GPS-1")
        cls.other = Driver.objects.create(user=cls.other_user, name="Otro", license_number="GPS-2")
        depot = Depot.objects.create(name="GPS", latitude=14.6, longitude=-90.5)
        now = timezone.now()
        cls.route = Route.objects.create(depot=depot, driver=cls.driver, status=Route.Status.IN_PROGRESS,
                                        driving_minutes=60, total_km=30, departure_at=now, finish_at=now + timedelta(hours=1))
        cls.other_route = Route.objects.create(depot=depot, driver=cls.other, status=Route.Status.IN_PROGRESS,
                                              driving_minutes=60, total_km=30, departure_at=now, finish_at=now + timedelta(hours=1))

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, **fields):
        payload = {"route_id": self.route.id, "lat": 14.6, "lng": -90.5} | fields
        return self.client.post("/api/driver/position/", json.dumps(payload), content_type="application/json")

    def read(self, **params):
        return self.client.get(f"/api/v2/routes/{self.route.id}/positions/", params)

    def test_stores_only_owned_active_route_and_server_time(self):
        now = timezone.now()
        with patch("logistics.application.positions.timezone.now", return_value=now):
            response = self.post(recorded_at="2000-01-01T00:00:00Z", speed_kmh=30, heading=180, accuracy_m=8)
        self.assertEqual(response.status_code, 201)
        position = VehiclePosition.objects.get()
        self.assertEqual((position.route_id, position.driver_id, position.source), (self.route.id, self.driver.id, "phone"))
        self.assertEqual(position.recorded_at, now)
        self.assertEqual((position.speed_kmh, position.heading, position.accuracy_m), (30, 180, 8))

    def test_another_route_and_finished_routes_never_store(self):
        self.assertEqual(self.post(route_id=self.other_route.id).status_code, 404)
        for status in [Route.Status.PLANNED, Route.Status.COMPLETED, Route.Status.CANCELED]:
            Route.objects.filter(pk=self.route.pk).update(status=status)
            self.assertEqual(self.post().status_code, 400)
        self.assertEqual(VehiclePosition.objects.count(), 0)

    def test_validation_rejects_invalid_non_finite_and_spoofed_source(self):
        for fields in [
            {"lat": 91}, {"lng": -181}, {"lat": True}, {"lat": "14.6"}, {"lat": None},
            {"lat": float("nan")}, {"lng": float("inf")}, {"lat": 10 ** 400},
            {"speed_kmh": -1}, {"speed_kmh": 301}, {"heading": 360}, {"heading": -1},
            {"accuracy_m": -1}, {"accuracy_m": float("inf")}, {"source": "tracker"},
            {"route_id": True}, {"route_id": "1"}, {"route_id": -1},
        ]:
            with self.subTest(fields=fields):
                self.assertEqual(self.post(**fields).status_code, 400)
        self.assertFalse(VehiclePosition.objects.exists())
        self.driver.refresh_from_db()
        self.assertIsNone(self.driver.last_position_at)
        self.assertEqual(self.post(speed_kmh=None, heading=None, accuracy_m=None).status_code, 201)

    def test_rate_limit_is_per_driver_and_accepts_exact_five_seconds(self):
        now = timezone.now()
        with patch("logistics.application.positions.timezone.now", return_value=now):
            self.assertEqual(self.post().status_code, 201)
        other_route = Route.objects.create(depot=self.route.depot, driver=self.driver,
                                          driving_minutes=60, total_km=30, status=Route.Status.IN_PROGRESS, departure_at=now, finish_at=now)
        with patch("logistics.application.positions.timezone.now", return_value=now + timedelta(seconds=4.99)):
            self.assertEqual(self.post(route_id=other_route.id).status_code, 429)
        with patch("logistics.application.positions.timezone.now", return_value=now + timedelta(seconds=5)):
            self.assertEqual(self.post(route_id=other_route.id).status_code, 201)
        self.assertEqual(VehiclePosition.objects.count(), 2)

    def test_permissions_and_http_methods(self):
        self.assertEqual(self.read().status_code, 403)
        for user in [self.dispatcher, self.admin]:
            self.client.force_login(user)
            self.assertEqual(self.post().status_code, 403)
            self.assertEqual(self.read().status_code, 200)
        self.client.force_login(self.orphan)
        self.assertEqual(self.post().status_code, 400)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/driver/position/").status_code, 405)
        self.client.logout()
        self.assertEqual(self.post().status_code, 401)
        self.assertEqual(self.read().status_code, 401)

    def test_history_prevents_clock_reset_from_bypassing_rate_limit(self):
        now = timezone.now()
        with patch("logistics.application.positions.timezone.now", return_value=now):
            self.assertEqual(self.post().status_code, 201)
            Driver.objects.filter(pk=self.driver.pk).update(last_position_at=None)
            self.assertEqual(self.post().status_code, 429)
        self.assertEqual(VehiclePosition.objects.count(), 1)

    def test_read_returns_latest_and_recent_ordered_trace_and_since(self):
        now = timezone.now()
        old = VehiclePosition.objects.create(route=self.route, driver=self.driver, lat=14.6, lng=-90.5,
                                             recorded_at=now - timedelta(hours=1))
        first = VehiclePosition.objects.create(route=self.route, driver=self.driver, lat=14.7, lng=-90.5,
                                               recorded_at=now - timedelta(minutes=2))
        last = VehiclePosition.objects.create(route=self.route, driver=self.driver, lat=14.8, lng=-90.5,
                                              recorded_at=now)
        VehiclePosition.objects.create(route=self.other_route, driver=self.other, lat=14.9, lng=-90.5)
        self.client.force_login(self.dispatcher)
        data = self.read().json()
        self.assertEqual(data["latest"]["id"], last.id)
        self.assertEqual([p["id"] for p in data["positions"]], [first.id, last.id])
        self.assertEqual([p["id"] for p in self.read(since=first.recorded_at.isoformat()).json()["positions"]], [last.id])
        for since in ["no", "2026-10-11T12:00:00", "2026-99-99T00:00:00Z"]:
            self.assertEqual(self.read(since=since).status_code, 400)
        self.assertEqual(self.client.get("/api/v2/routes/999999/positions/").status_code, 404)
        VehiclePosition.objects.filter(pk__in=[first.pk, last.pk]).delete()
        self.assertEqual(self.read().json()["latest"]["id"], old.id)
        self.assertEqual(self.read().json()["positions"], [])

    def test_read_is_bounded_and_csrf_is_required(self):
        now = timezone.now()
        VehiclePosition.objects.bulk_create([VehiclePosition(route=self.route, driver=self.driver, lat=14.6, lng=-90.5,
                                                              recorded_at=now - timedelta(seconds=i)) for i in range(400)])
        self.client.force_login(self.admin)
        self.assertEqual(len(self.read().json()["positions"]), 360)
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post("/api/driver/position/", json.dumps({"route_id": self.route.id, "lat": 14.6, "lng": -90.5}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
