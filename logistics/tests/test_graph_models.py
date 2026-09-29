"""Restricciones de la BD del grafo nacional: protegen los supuestos de Dijkstra y A*."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from logistics.models import DayType, Edge, Node, TrafficBand, TrafficProfile


def make_node(code: str, lat: float = 14.63, lon: float = -90.51, **extra) -> Node:
    defaults = {"name": code.title(), "kind": Node.Kind.MUNICIPIO, "department": "GU"}
    defaults.update(extra)
    return Node.objects.create(code=code, latitude=lat, longitude=lon, **defaults)


class GraphModelConstraintTests(TestCase):
    def setUp(self):
        self.a = make_node("nodo-a", 14.63, -90.51)
        self.b = make_node("nodo-b", 14.66, -90.82)
        self.edge = Edge.objects.create(
            origin=self.a, destination=self.b, distance_km=55.0, duration_free_min=60.0, road="CA-1"
        )

    def assertViolates(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_edge_is_directed_both_directions_coexist(self):
        back = Edge.objects.create(origin=self.b, destination=self.a, distance_km=55.0, duration_free_min=75.0)
        self.assertNotEqual(back.duration_free_min, self.edge.duration_free_min)
        self.assertEqual(Edge.objects.count(), 2)

    def test_duplicate_direction_rejected(self):
        self.assertViolates(
            lambda: Edge.objects.create(origin=self.a, destination=self.b, distance_km=50.0, duration_free_min=55.0)
        )

    def test_self_loop_rejected(self):
        self.assertViolates(
            lambda: Edge.objects.create(origin=self.a, destination=self.a, distance_km=1.0, duration_free_min=1.0)
        )

    def test_non_positive_duration_rejected(self):
        self.assertViolates(
            lambda: Edge.objects.create(origin=self.b, destination=self.a, distance_km=55.0, duration_free_min=0.0)
        )

    def test_non_positive_distance_rejected(self):
        self.assertViolates(
            lambda: Edge.objects.create(origin=self.b, destination=self.a, distance_km=-1.0, duration_free_min=60.0)
        )

    def test_node_outside_guatemala_rejected(self):
        self.assertViolates(lambda: make_node("en-mexico", 19.43, -99.13))

    def test_multiplier_below_one_rejected(self):
        """Con m < 1 el costo bajaría de t0 y v_max dejaría de ser una cota válida."""
        self.assertViolates(
            lambda: TrafficProfile.objects.create(
                edge=self.edge, band=TrafficBand.PEAK_AM, day_type=DayType.WEEKDAY, multiplier=0.9
            )
        )

    def test_multiplier_one_or_more_accepted(self):
        for band, m in [(TrafficBand.NIGHT, 1.0), (TrafficBand.PEAK_AM, 1.8)]:
            TrafficProfile.objects.create(edge=self.edge, band=band, day_type=DayType.WEEKDAY, multiplier=m)
        self.assertEqual(self.edge.traffic_profiles.count(), 2)

    def test_one_profile_per_edge_band_and_day_type(self):
        TrafficProfile.objects.create(
            edge=self.edge, band=TrafficBand.PEAK_PM, day_type=DayType.WEEKEND, multiplier=1.2
        )
        self.assertViolates(
            lambda: TrafficProfile.objects.create(
                edge=self.edge, band=TrafficBand.PEAK_PM, day_type=DayType.WEEKEND, multiplier=1.3
            )
        )

    def test_there_are_seven_bands_and_two_day_types(self):
        self.assertEqual(len(TrafficBand.choices), 7)
        self.assertEqual(len(DayType.choices), 2)
