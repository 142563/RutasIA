"""Tipo de carretera y "Evitar terracería" (RUT-37).

La terracería solo se penaliza en los pesos de BÚSQUEDA (×UNPAVED_PENALTY ≥ 1);
los minutos que ve el usuario siguen siendo los reales.
"""
import math

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from django.contrib.auth.models import User

from logistics.models import Edge, Node, UserProfile
from logistics.routing.astar import astar
from logistics.routing.build import apply_road_classes, build_estimated, estimated_graph_from_seed
from logistics.routing.dijkstra import dijkstra
from logistics.routing.graph import DISTANCE, TIME, UNPAVED, UNPAVED_PENALTY, RoadGraph, invalidate_graph
from logistics.routing.multistop import plan_multistop
from logistics.routing.seed_data import UNPAVED_SEGMENTS, RoadSegment
from logistics.routing.traffic import GT_TZ

from datetime import datetime


def triangle(classes):
    """A→B directo (30 min, clase dada) o A→C→B asfaltado (25 + 25 min)."""
    return RoadGraph.from_lists(
        nodes=[("a", "A", 14.6, -90.5), ("b", "B", 14.7, -90.4), ("c", "C", 14.65, -90.3)],
        edges=[("a", "b", 20, 30), ("a", "c", 30, 25), ("c", "b", 30, 25)],
        road_classes=classes,
    )


class SearchWeightsTests(SimpleTestCase):
    def test_only_unpaved_edges_are_penalized_and_none_decrease(self):
        g = triangle([UNPAVED, "primary", "secondary"])
        base = g.weights(TIME)
        search = g.search_weights(TIME, avoid_unpaved=True)
        self.assertEqual(search, [30 * UNPAVED_PENALTY, 25, 25])
        self.assertTrue(all(s >= b for s, b in zip(search, base)))
        self.assertEqual(base, [30, 25, 25])  # la lista cacheada no se toca

    def test_without_avoid_the_weights_are_the_real_ones(self):
        g = triangle([UNPAVED, "primary", "secondary"])
        self.assertIs(g.search_weights(TIME), g.weights(TIME))

    def test_avoids_unpaved_when_there_is_an_alternative(self):
        g = triangle([UNPAVED, "primary", "secondary"])
        r = astar(g, g.search_weights(TIME, avoid_unpaved=True), 0, 1)
        self.assertEqual(r.path, [0, 2, 1])
        self.assertEqual(r.total(g.weights(TIME)), 50)  # minutos reales, no penalizados
        self.assertEqual(g.unpaved_km(r.edges), 0)

    def test_allowing_unpaved_takes_the_faster_road(self):
        g = triangle([UNPAVED, "primary", "secondary"])
        r = astar(g, g.search_weights(TIME, avoid_unpaved=False), 0, 1)
        self.assertEqual(r.path, [0, 1])
        self.assertEqual(g.unpaved_km(r.edges), 20)

    def test_unpaved_is_still_used_when_it_is_the_only_road(self):
        g = RoadGraph.from_lists(
            nodes=[("a", "A", 14.6, -90.5), ("b", "B", 14.7, -90.4)],
            edges=[("a", "b", 20, 30)], road_classes=[UNPAVED],
        )
        r = astar(g, g.search_weights(TIME, avoid_unpaved=True), 0, 1)
        self.assertTrue(r.found)
        self.assertEqual(r.total(g.weights(TIME)), 30)

    def test_astar_equals_dijkstra_with_unpaved_penalty_on_the_national_graph(self):
        g = estimated_graph_from_seed()
        self.assertIn(UNPAVED, g.road_classes)
        for criterion in (TIME, DISTANCE):
            w = g.search_weights(criterion, avoid_unpaved=True)
            for s in range(0, g.node_count, 7):
                for t in range(0, g.node_count, 5):
                    a, d = astar(g, w, s, t), dijkstra(g, w, s, t)
                    self.assertTrue(math.isclose(a.cost, d.cost, rel_tol=1e-9, abs_tol=1e-9), (s, t, criterion))

    def test_multistop_reports_real_minutes_when_avoiding(self):
        g = triangle([UNPAVED, "primary", "secondary"])
        departure = datetime(2026, 10, 6, 10, 0, tzinfo=GT_TZ)
        plan = plan_multistop(g, 0, [1], departure, service_min=0, avoid_unpaved=True)
        self.assertEqual(plan.legs[0].search.path, [0, 2, 1])
        self.assertAlmostEqual(plan.driving_minutes, 50)

    def test_seed_classes(self):
        self.assertEqual(RoadSegment("a", "b", "CA-9").road_class, "primary")
        self.assertEqual(RoadSegment("a", "b", "RN-5").road_class, "secondary")
        pair = sorted(next(iter(UNPAVED_SEGMENTS)))
        self.assertEqual(RoadSegment(pair[0], pair[1], "RN").road_class, UNPAVED)


class RoadClassDbTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command("seed_graph_nodes", verbosity=0)
        build_estimated()
        invalidate_graph()
        user = User.objects.create_user("desp", password="x" * 12)
        UserProfile.objects.update_or_create(user=user, defaults={"role": UserProfile.Role.DISPATCHER})
        self.client.force_login(user)

    def tearDown(self):
        invalidate_graph()

    def test_build_stores_the_class_and_apply_fixes_old_edges(self):
        self.assertTrue(Edge.objects.filter(road_class=Edge.RoadClass.UNPAVED).exists())
        self.assertTrue(Edge.objects.filter(road_class=Edge.RoadClass.PRIMARY, road__startswith="CA").exists())
        Edge.objects.update(road_class=Edge.RoadClass.SECONDARY)
        self.assertGreater(apply_road_classes(), 0)
        self.assertTrue(Edge.objects.filter(road_class=Edge.RoadClass.UNPAVED).exists())

    def test_route_api_avoids_unpaved_by_default_and_reports_it(self):
        a, b = sorted(next(iter(UNPAVED_SEGMENTS)))
        url = reverse("api-routing-route")
        avoided = self.client.post(url, {"origin": a, "destination": b}, content_type="application/json").json()
        allowed = self.client.post(url, {"origin": a, "destination": b, "allow_unpaved": True},
                                   content_type="application/json").json()
        self.assertTrue(avoided["avoid_unpaved"])
        self.assertFalse(allowed["avoid_unpaved"])
        self.assertGreater(allowed["route"]["unpaved_km"], 0)
        self.assertLessEqual(avoided["route"]["unpaved_km"], allowed["route"]["unpaved_km"])
        self.assertTrue(Node.objects.filter(code=a).exists())
