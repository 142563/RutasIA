"""Mapas lentos (2026-10-14): toda la red viajaba con ~445 000 puntos a cada mapa.

La geometría ahora se simplifica una vez, queda en memoria y la red completa se pide
en una sola solicitud. Estas pruebas cubren ese error.
"""
import math

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from logistics.application import road_geometry as rg
from logistics.application.routing import geometry
from logistics.models import Edge, UserProfile
from logistics.routing.astar import compute_v_max
from logistics.routing.build import estimated_graph_from_seed
from logistics.routing.graph import TIME, invalidate_graph
from logistics.tests.test_build_graph import make_node


def winding_road(n=2000, lat=14.6, lng=-90.5):
    """Carretera densa: avanza ~30 km con un zigzag de ±3 m (ruido que no se ve en el mapa)."""
    return [(lat + i * 1.5e-4, lng + i * 1e-4 + (2.5e-5 if i % 2 else 0)) for i in range(n)]


def max_deviation_deg(original, simplified):
    """Distancia máxima de un punto original al trazo simplificado (en grados, con cos(lat))."""
    scale = math.cos(math.radians(original[0][0]))
    def seg_dist(p, a, b):
        px, py, ax, ay, bx, by = p[1] * scale, p[0], a[1] * scale, a[0], b[1] * scale, b[0]
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    return max(min(seg_dist(p, a, b) for a, b in zip(simplified, simplified[1:])) for p in original)


class SimplifyTests(SimpleTestCase):
    def test_encode_decode_round_trip(self):
        points = [(14.63491, -90.50691), (14.6, -90.6), (15.0, -91.25), (13.9, -89.1)]
        self.assertEqual(rg.decode(rg.encode(points)), points)

    def test_simplify_keeps_ends_reduces_points_and_stays_within_tolerance(self):
        road = winding_road()
        simple = rg.simplify(road)
        self.assertEqual((simple[0], simple[-1]), (road[0], road[-1]))
        self.assertLess(len(simple), len(road) / 20)
        self.assertLessEqual(max_deviation_deg(road, simple), rg.TOLERANCE_DEG * 1.0001)

    def test_short_lines_untouched(self):
        self.assertEqual(rg.simplify([(1, 1), (2, 2)]), [(1, 1), (2, 2)])


class NetworkGeometryTests(TestCase):
    def setUp(self):
        invalidate_graph()
        rg.invalidate()
        a, b, c = make_node("a", 14.6, -90.5), make_node("b", 14.9, -90.3), make_node("c", 15.0, -90.1)
        dense = rg.encode(winding_road())
        for origin, destination in ((a, b), (b, a), (b, c)):
            Edge.objects.create(origin=origin, destination=destination, distance_km=30, duration_free_min=30,
                                source="manual", polyline=dense)
        Edge.objects.create(origin=a, destination=c, distance_km=40, duration_free_min=40, source="manual",
                            polyline=dense, is_active=False)

    def test_whole_network_in_one_light_response(self):
        data = geometry({"all": "1"})
        self.assertEqual({(e["from"], e["to"]) for e in data["edges"]}, {("a", "b"), ("b", "a"), ("b", "c")})
        original = sum(len(rg.decode(e.polyline)) for e in Edge.objects.filter(is_active=True))
        sent = sum(len(rg.decode(e["polyline"])) for e in data["edges"])
        self.assertLess(sent, original / 20)

    def test_repeated_requests_do_not_hit_the_database(self):
        geometry({"all": "1"})
        with self.assertNumQueries(0):
            geometry({"all": "1"})
            geometry({"edges": '[["a", "b"], ["c", "b"]]'})

    def test_cache_follows_graph_changes(self):
        self.assertEqual(len(geometry({"all": "1"})["edges"]), 3)
        Edge.objects.filter(origin__code="b", destination__code="c").first().delete()  # señal: invalida el grafo
        self.assertEqual(len(geometry({"all": "1"})["edges"]), 2)

    def test_api_all_requires_session(self):
        url = "/api/routing/geometry/?all=1"
        self.assertIn(self.client.get(url).status_code, (302, 401, 403))
        user = User.objects.create_user("despacho", password="clave-segura-123")
        UserProfile.objects.create(user=user, role=UserProfile.Role.DISPATCHER)
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["edges"]), 3)


class VmaxCacheTests(SimpleTestCase):
    def test_v_max_computed_once_per_weights_list(self):
        g = estimated_graph_from_seed()
        weights = g.weights(TIME)
        first = compute_v_max(g, weights)
        self.assertIs(g._vmax_cache[id(weights)][0], weights)
        self.assertEqual(compute_v_max(g, weights), first)
        slower = [w * 2 for w in weights]  # otra lista: se calcula aparte (y es la mitad)
        self.assertAlmostEqual(compute_v_max(g, slower), first / 2, places=9)
