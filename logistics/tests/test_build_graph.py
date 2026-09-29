"""Día 2: cliente de Google Routes, build_graph y grafo en memoria."""
import json
from io import StringIO

import httpx
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from logistics.models import DayType, Edge, Node, RouteSample, TrafficBand, TrafficProfile
from logistics.routing.build import build_estimated, build_from_google, estimate_segment
from logistics.routing.geo import haversine_km
from logistics.routing.google import (
    FIELD_MASK, MATRIX_URL, MatrixElement, RoutesApiError, RoutesClient, parse_matrix_response,
)
from logistics.routing.graph import DISTANCE, TIME, RoadGraph, load_graph
from logistics.routing.seed_data import ROAD_SEGMENTS, RoadSegment


class RoutesClientTests(SimpleTestCase):
    def test_parses_elements_statuses_and_proto3_defaults(self):
        elements = parse_matrix_response([
            # originIndex/destinationIndex en 0 vienen omitidos (proto3)
            {"status": {}, "condition": "ROUTE_EXISTS", "distanceMeters": 55000,
             "duration": "3600s", "staticDuration": "3300s"},
            {"originIndex": 0, "destinationIndex": 1, "condition": "ROUTE_NOT_FOUND"},
            {"destinationIndex": 2, "status": {"code": 3, "message": "Invalid waypoint"}},
        ])
        first, not_found, error = elements
        self.assertEqual((first.origin_index, first.destination_index), (0, 0))
        self.assertTrue(first.ok)
        self.assertEqual((first.distance_m, first.duration_s, first.static_duration_s), (55000.0, 3600.0, 3300.0))
        self.assertFalse(not_found.ok)
        self.assertEqual(not_found.status, "ROUTE_NOT_FOUND")
        self.assertEqual(error.status, "Invalid waypoint")
        self.assertIsNone(error.distance_m)

    def test_sends_key_field_mask_and_waypoints(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=[{"distanceMeters": 1000, "duration": "60s", "staticDuration": "60s"}])

        client = RoutesClient(api_key="clave-de-prueba", http=httpx.Client(transport=httpx.MockTransport(handler)))
        result = client.compute_route_matrix([(14.6, -90.5)], [(14.7, -90.8)])

        self.assertEqual(captured["url"], MATRIX_URL)
        self.assertEqual(captured["headers"]["X-Goog-Api-Key"], "clave-de-prueba")
        self.assertEqual(captured["headers"]["X-Goog-FieldMask"], FIELD_MASK)
        self.assertEqual(captured["body"]["routingPreference"], "TRAFFIC_UNAWARE")
        self.assertEqual(captured["body"]["origins"][0]["waypoint"]["location"]["latLng"],
                         {"latitude": 14.6, "longitude": -90.5})
        self.assertEqual(result[0].duration_s, 60.0)
        self.assertEqual(client.elements_requested, 1)

    def test_http_error_raises(self):
        client = RoutesClient(api_key="x", http=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(403, text="API key not valid"))))
        with self.assertRaisesMessage(RoutesApiError, "403"):
            client.compute_route_matrix([(14.6, -90.5)], [(14.7, -90.8)])

    @override_settings(GOOGLE_ROUTES_API_KEY="")
    def test_missing_key_is_explained(self):
        with self.assertRaisesMessage(RoutesApiError, "GOOGLE_ROUTES_API_KEY"):
            RoutesClient()


class FakeRoutesClient:
    """Responde como Google: km por carretera = 1.2 × línea recta, a 50 km/h.

    `distance_override` fuerza la distancia de pares concretos (para simular
    que una ruta pasa por otro nodo) y `missing` simula ROUTE_NOT_FOUND.
    """

    def __init__(self, distance_override=None, missing=()):
        self.distance_override = distance_override or {}
        self.missing = set(missing)
        self.requests_made = 0
        self.elements_requested = 0

    def compute_route_matrix(self, origins, destinations, departure_time=None, traffic=False):
        self.requests_made += 1
        self.elements_requested += len(origins) * len(destinations)
        (olat, olon), = origins
        result = []
        for j, (dlat, dlon) in enumerate(destinations):
            key = ((olat, olon), (dlat, dlon))
            if key in self.missing:
                result.append(MatrixElement(0, j, "ROUTE_NOT_FOUND", None, None, None))
                continue
            km = self.distance_override.get(key, haversine_km(olat, olon, dlat, dlon) * 1.2)
            seconds = km / 50 * 3600
            result.append(MatrixElement(0, j, "", km * 1000, seconds, seconds))
        return result


def make_node(code, lat, lon):
    return Node.objects.create(code=code, name=code.upper(), kind=Node.Kind.MUNICIPIO,
                               department="GU", latitude=lat, longitude=lon)


class BuildFromGoogleTests(TestCase):
    def setUp(self):
        # A, B y C casi en línea recta; D aparte.
        self.a = make_node("a", 14.60, -90.50)
        self.b = make_node("b", 14.60, -90.70)
        self.c = make_node("c", 14.60, -90.90)
        self.d = make_node("d", 14.90, -90.70)
        self.segments = [
            RoadSegment("a", "b", "CA-1"), RoadSegment("b", "c", "CA-1"),
            RoadSegment("a", "c", "CA-1", needs_check=True), RoadSegment("b", "d", "RN"),
        ]
        pa, pc = (self.a.latitude, self.a.longitude), (self.c.latitude, self.c.longitude)
        via_b = haversine_km(*pa, self.b.latitude, self.b.longitude) * 1.2 * 2
        # Google dice que A–C mide lo mismo que A–B–C: el tramo pasa por B.
        self.client = FakeRoutesClient(distance_override={(pa, pc): via_b, (pc, pa): via_b})

    def test_creates_two_directed_edges_per_segment(self):
        report = build_from_google(self.client, segments=self.segments)
        self.assertEqual(report.edges_created, 8)
        self.assertEqual(Edge.objects.count(), 8)
        self.assertEqual(RouteSample.objects.count(), 8)
        edge = Edge.objects.get(origin=self.a, destination=self.b)
        self.assertEqual(edge.source, Edge.Source.GOOGLE)
        self.assertAlmostEqual(edge.duration_free_min, edge.distance_km / 50 * 60)
        self.assertIsNotNone(edge.verified_at)

    def test_detects_redundant_segment_that_passes_through_another_node(self):
        report = build_from_google(self.client, segments=self.segments)
        self.assertCountEqual(report.redundant, [("a", "c"), ("c", "a")])
        self.assertFalse(Edge.objects.get(origin=self.a, destination=self.c).is_active)
        self.assertTrue(Edge.objects.get(origin=self.a, destination=self.b).is_active)

    def test_is_idempotent_and_uses_cached_samples(self):
        build_from_google(self.client, segments=self.segments)
        second_client = FakeRoutesClient()
        report = build_from_google(second_client, segments=self.segments)
        self.assertEqual(Edge.objects.count(), 8)
        self.assertEqual(report.edges_created, 0)
        self.assertEqual(second_client.requests_made, 0)  # todo salió de la caché

    def test_route_not_found_is_reported_and_skipped(self):
        pb, pd = (self.b.latitude, self.b.longitude), (self.d.latitude, self.d.longitude)
        report = build_from_google(FakeRoutesClient(missing={(pb, pd)}), segments=self.segments)
        self.assertIn(("b", "d", "ROUTE_NOT_FOUND"), report.not_found)
        self.assertFalse(Edge.objects.filter(origin=self.b, destination=self.d).exists())
        self.assertTrue(Edge.objects.filter(origin=self.d, destination=self.b).exists())


class BuildEstimatedTests(TestCase):
    def setUp(self):
        call_command("seed_graph_nodes", stdout=StringIO())

    def test_estimate_builds_whole_graph_offline(self):
        out = StringIO()
        call_command("build_graph", "--estimate", stdout=out)
        self.assertEqual(Edge.objects.count(), 2 * len(ROAD_SEGMENTS))
        self.assertFalse(Edge.objects.exclude(source=Edge.Source.ESTIMATE).exists())
        self.assertIn("ESTIMADAS", out.getvalue())
        call_command("build_graph", "--estimate", stdout=StringIO())
        self.assertEqual(Edge.objects.count(), 2 * len(ROAD_SEGMENTS))

    def test_estimate_never_overwrites_google_edges(self):
        a, b = Node.objects.get(code="ciudad-guatemala"), Node.objects.get(code="el-trebol")
        Edge.objects.create(origin=a, destination=b, distance_km=4.2, duration_free_min=12.0,
                            source=Edge.Source.GOOGLE)
        build_estimated()
        edge = Edge.objects.get(origin=a, destination=b)
        self.assertEqual((edge.source, edge.duration_free_min), (Edge.Source.GOOGLE, 12.0))

    def test_estimate_formula(self):
        a, b = Node.objects.get(code="chimaltenango"), Node.objects.get(code="tecpan")
        km, minutes = estimate_segment(a, b)
        self.assertAlmostEqual(km, haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * 1.3)
        self.assertAlmostEqual(minutes, km)  # a 60 km/h, 1 km = 1 min

    @override_settings(GOOGLE_ROUTES_API_KEY="")
    def test_google_mode_without_key_explains_offline_option(self):
        with self.assertRaisesMessage(CommandError, "--estimate"):
            call_command("build_graph", stdout=StringIO())


class RoadGraphTests(SimpleTestCase):
    def setUp(self):
        self.graph = RoadGraph.from_lists(
            nodes=[("a", "A", 14.6, -90.5), ("b", "B", 14.6, -90.7), ("c", "C", 14.9, -90.7)],
            edges=[("a", "b", 22.0, 20.0), ("b", "a", 22.0, 30.0), ("b", "c", 40.0, 45.0)],
            multipliers={(TrafficBand.PEAK_AM, DayType.WEEKDAY): [1.5, 1.0, 2.0]},
        )

    def test_adjacency_is_directed(self):
        a, b, c = (self.graph.node_index(x) for x in "abc")
        self.assertEqual([v for v, _ in self.graph.adj[a]], [b])
        self.assertEqual(sorted(v for v, _ in self.graph.adj[b]), [a, c])
        self.assertEqual(self.graph.adj[c], [])

    def test_weights_by_profile_and_criterion(self):
        self.assertEqual(self.graph.weights(TIME), [20.0, 30.0, 45.0])
        self.assertEqual(self.graph.weights(TIME, TrafficBand.PEAK_AM, DayType.WEEKDAY), [30.0, 30.0, 90.0])
        # Franja sin calibrar: m = 1
        self.assertEqual(self.graph.weights(TIME, TrafficBand.NIGHT, DayType.WEEKEND), [20.0, 30.0, 45.0])
        self.assertEqual(self.graph.weights(DISTANCE), [22.0, 22.0, 40.0])

    def test_nearest_node(self):
        self.assertEqual(self.graph.codes[self.graph.nearest_node(14.88, -90.71)], "c")

    def test_unknown_node_code(self):
        with self.assertRaisesMessage(KeyError, "zzz"):
            self.graph.node_index("zzz")


class LoadGraphTests(TestCase):
    def test_loads_active_edges_and_profiles_and_invalidates(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        graph = load_graph()
        self.assertEqual(graph.node_count, 108)
        self.assertEqual(graph.edge_count, 2 * len(ROAD_SEGMENTS))
        self.assertEqual(graph.sources["edges"], "estimate")
        self.assertIs(load_graph(), graph)  # cacheado en el proceso

        edge = Edge.objects.first()
        TrafficProfile.objects.create(edge=edge, band=TrafficBand.PEAK_PM, day_type=DayType.WEEKDAY,
                                      multiplier=1.7, source="synthetic")
        reloaded = load_graph()
        self.assertIsNot(reloaded, graph)  # la señal invalidó el grafo
        position = reloaded.edge_db_ids.index(edge.id)
        self.assertAlmostEqual(
            reloaded.weights(TIME, TrafficBand.PEAK_PM, DayType.WEEKDAY)[position], edge.duration_free_min * 1.7)
