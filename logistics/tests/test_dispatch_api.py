"""RUT-16: detalle de ruta, Inicio, Monitoreo y Reportes del despachador."""
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from logistics.models import (
    Depot, Driver, Edge, Incident, Node, Order, RerouteProposal, Route, RouteStop, UserProfile,
)


class DispatchApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dispatcher = User.objects.create_user(username="despachador", password="clave-segura-123")
        UserProfile.objects.create(user=cls.dispatcher, role=UserProfile.Role.DISPATCHER)
        cls.driver_user = User.objects.create_user(username="conductor", password="clave-segura-123")
        UserProfile.objects.create(user=cls.driver_user, role=UserProfile.Role.DRIVER)
        cls.depot = Depot.objects.create(name="Bodega", latitude=14.6, longitude=-90.5)
        cls.driver = Driver.objects.create(name="Luis", license_number="L-1")
        cls.a = Node.objects.create(code="a", name="Alfa", kind="cabecera", department="GU", latitude=14.6, longitude=-90.5)
        cls.b = Node.objects.create(code="b", name="Beta", kind="cabecera", department="SA", latitude=14.3, longitude=-90.8)
        cls.edge = Edge.objects.create(origin=cls.a, destination=cls.b, distance_km=40, duration_free_min=50)

    def setUp(self):
        self.client.force_login(self.dispatcher)
        self.now = timezone.now()

    def make_order(self, n, status=Order.Status.ASSIGNED):
        return Order.objects.create(recipient=f"Cliente {n}", address=f"Calle {n}", latitude=14.6, longitude=-90.5,
                                    weight_kg=5, status=status)

    def make_route(self, status=Route.Status.IN_PROGRESS, driving=100, shortest=130, departure=None):
        departure = departure or self.now - timedelta(hours=1)
        return Route.objects.create(
            depot=self.depot, driver=self.driver, departure_at=departure, driving_minutes=driving,
            total_km=80, shortest_minutes=shortest, finish_at=departure + timedelta(hours=3), status=status,
            legs=[{"nodes": ["a", "b"], "minutes": 50}])

    def add_stop(self, route, seq, eta_offset_min, status=RouteStop.Status.PENDING, delivered_offset_min=None, reason=""):
        eta = self.now + timedelta(minutes=eta_offset_min)
        return RouteStop.objects.create(
            route=route, order=self.make_order(f"{route.id}-{seq}"), sequence=seq, eta=eta, status=status,
            reason=reason,
            delivered_at=eta + timedelta(minutes=delivered_offset_min) if delivered_offset_min is not None else None)

    # --- permisos ---
    def test_only_dispatch_roles(self):
        route = self.make_route()
        urls = [reverse("api-v2-route-detail", args=[route.id]), reverse("api-v2-dashboard"),
                reverse("api-v2-monitoring"), reverse("api-v2-reports")]
        self.client.force_login(self.driver_user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.logout()
        for url in urls:
            self.assertNotEqual(self.client.get(url).status_code, 200, url)

    # --- detalle ---
    def test_route_detail_timeline(self):
        route = self.make_route()
        self.add_stop(route, 1, -60, RouteStop.Status.DELIVERED, delivered_offset_min=5)
        self.add_stop(route, 2, -40, RouteStop.Status.DELIVERED, delivered_offset_min=30)
        self.add_stop(route, 3, -20, RouteStop.Status.FAILED, reason="Cliente ausente")
        self.add_stop(route, 4, -5)
        self.add_stop(route, 5, 30)
        RerouteProposal.objects.create(route=route, current_minutes=60, proposed_minutes=42, summary="Por Palín: −18 min")
        data = self.client.get(reverse("api-v2-route-detail", args=[route.id])).json()
        self.assertTrue(data["ok"])
        timings = [s["timing"] for s in data["route"]["stops"]]
        self.assertEqual(timings, ["on_time", "late", "failed", "overdue", "pending"])
        self.assertEqual(data["route"]["stops"][0]["diff_minutes"], 5.0)
        self.assertEqual(data["route"]["stops"][1]["diff_minutes"], 30.0)
        self.assertIsNone(data["route"]["stops"][4]["diff_minutes"])
        self.assertEqual(data["route"]["progress"], {"delivered": 2, "failed": 1, "total": 5})
        self.assertEqual(data["route"]["minutes_saved"], 30.0)
        self.assertEqual(data["legs"][0]["nodes"], ["a", "b"])
        self.assertEqual(data["reroutes"][0]["minutes_saved"], 18.0)
        self.assertEqual(data["late_tolerance_min"], 15)

    def test_route_detail_404(self):
        response = self.client.get(reverse("api-v2-route-detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    # --- Inicio ---
    def test_dashboard_kpis(self):
        running = self.make_route()
        self.add_stop(running, 1, -30, RouteStop.Status.DELIVERED, delivered_offset_min=20)  # tarde hoy
        self.add_stop(running, 2, -10)  # pendiente con ETA pasada
        self.add_stop(running, 3, 40)
        planned = self.make_route(Route.Status.PLANNED, departure=self.now + timedelta(minutes=1))
        self.add_stop(planned, 1, 90)
        self.make_route(Route.Status.COMPLETED)
        self.make_order("libre", status=Order.Status.PENDING)
        Order.objects.create(code="LEG-1", weight_kg=1)  # pedido clásico (sin ubicación): no cuenta
        data = self.client.get(reverse("api-v2-dashboard")).json()
        self.assertEqual(data["routes_in_progress"], 1)
        self.assertEqual(data["delayed_stops"], 2)
        self.assertEqual(data["unassigned_orders"], 1)
        self.assertEqual(data["deliveries_today"], 1)
        self.assertLessEqual(data["routes_planned_today"], 1)

    def test_dashboard_empty(self):
        data = self.client.get(reverse("api-v2-dashboard")).json()
        for key in ("routes_in_progress", "routes_planned_today", "delayed_stops", "unassigned_orders", "deliveries_today"):
            self.assertEqual(data[key], 0)

    # --- Monitoreo ---
    def test_monitoring_routes_incidents_proposals(self):
        route = self.make_route()
        self.add_stop(route, 1, -50, RouteStop.Status.DELIVERED, delivered_offset_min=10)
        self.add_stop(route, 2, -25)
        self.make_route(Route.Status.COMPLETED)
        active = Incident.objects.create(kind="accident", multiplier=2, note="Choque", route=route)
        active.edges.add(self.edge)
        Incident.objects.create(kind="closure", blocked=True, resolved_at=self.now)
        Incident.objects.create(kind="traffic", multiplier=1.5, ends_at=self.now - timedelta(hours=1))
        RerouteProposal.objects.create(route=route, incident=active, current_minutes=60, proposed_minutes=40)
        RerouteProposal.objects.create(route=route, current_minutes=60, proposed_minutes=40,
                                       status=RerouteProposal.Status.ACCEPTED)
        data = self.client.get(reverse("api-v2-monitoring")).json()
        self.assertEqual([r["code"] for r in data["routes"]], [route.code])
        item = data["routes"][0]
        self.assertEqual(item["progress"], {"delivered": 1, "failed": 0, "total": 2})
        self.assertEqual(item["next_stop"]["sequence"], 2)
        self.assertGreaterEqual(item["delay_minutes"], 24)
        self.assertEqual(item["pending_reroutes"], 1)
        self.assertEqual(len(data["incidents"]), 1)
        self.assertEqual(data["incidents"][0]["edges"], ["Alfa → Beta"])
        self.assertEqual(len(data["proposals"]), 1)

    # --- Reportes ---
    def test_reports_metrics_without_experiments(self):
        route = self.make_route(driving=100, shortest=130)
        self.add_stop(route, 1, -60, RouteStop.Status.DELIVERED, delivered_offset_min=5)
        self.add_stop(route, 2, -40, RouteStop.Status.DELIVERED, delivered_offset_min=30)
        self.add_stop(route, 3, -20, RouteStop.Status.FAILED, reason="Cliente ausente")
        self.add_stop(route, 4, -10, RouteStop.Status.FAILED)
        with tempfile.TemporaryDirectory() as tmp, mock.patch("logistics.application.dispatch.experiments_dir",
                                                              return_value=Path(tmp)):
            data = self.client.get(reverse("api-v2-reports")).json()
        self.assertEqual(data["minutes_saved"]["total"], 30.0)
        self.assertEqual(data["punctuality"], {"delivered": 2, "on_time": 1, "pct": 50.0, "tolerance_min": 15})
        self.assertEqual({r["reason"]: r["count"] for r in data["failed_by_reason"]},
                         {"Cliente ausente": 1, "Sin motivo": 1})
        self.assertEqual(data["experiments"], [])

    def test_reports_empty_has_null_punctuality(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("logistics.application.dispatch.experiments_dir",
                                                              return_value=Path(tmp)):
            data = self.client.get(reverse("api-v2-reports")).json()
        self.assertIsNone(data["punctuality"]["pct"])
        self.assertEqual(data["minutes_saved"]["total"], 0)

    def test_reports_reads_experiment_csv_with_data_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "e1_correctitud.csv").write_text(
                "profile,pairs,equal,pct_equal,max_abs_diff,data_source\n"
                "km,100,100,100.0,0,edges=estimate;traffic=synthetic\n"
                "peak_am/weekday,100,99,99.0,0,edges=estimate;traffic=synthetic\n", encoding="utf-8")
            (Path(tmp) / "e2_eficiencia.csv").write_text(
                "profile,origin,destination,dijkstra_expanded,astar_expanded,dijkstra_ms,astar_ms,same_cost,data_source\n"
                "km,a,b,50,20,0.5,0.2,True,edges=google;traffic=google\n", encoding="utf-8")
            (Path(tmp) / "e3_impacto_trafico.csv").write_text("basura\n", encoding="utf-8")  # dañado: se omite
            with mock.patch("logistics.application.dispatch.experiments_dir", return_value=Path(tmp)):
                data = self.client.get(reverse("api-v2-reports")).json()
        by_key = {e["key"]: e for e in data["experiments"]}
        self.assertEqual(set(by_key), {"e1", "e2"})
        self.assertEqual(by_key["e1"]["summary"]["pct_equal"], 99.5)
        self.assertFalse(by_key["e1"]["is_real_data"])
        self.assertEqual(by_key["e1"]["data_sources"], ["edges=estimate;traffic=synthetic"])
        self.assertTrue(by_key["e2"]["is_real_data"])
        self.assertEqual(by_key["e2"]["summary"]["reduction_pct"], 60.0)
