"""Día 4: franjas horarias y calibración de perfiles de tráfico."""
from datetime import datetime, timezone as dt_timezone
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from logistics.models import DayType, Edge, Node, TrafficBand, TrafficProfile
from logistics.routing.build import build_estimated
from logistics.routing.calibration import (
    PROFILES, calibrate_from_google, calibrate_synthetic, synthetic_multiplier,
)
from logistics.routing.google import MatrixElement
from logistics.routing.traffic import (
    GT_TZ, band_for, day_type_for, profile_for, representative_departure,
)


def gt(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=GT_TZ)


class BandTests(SimpleTestCase):
    def test_band_boundaries(self):
        cases = {
            (0, 10): TrafficBand.NIGHT, (4, 59): TrafficBand.NIGHT, (5, 0): TrafficBand.DAWN,
            (6, 59): TrafficBand.DAWN, (7, 0): TrafficBand.PEAK_AM, (8, 59): TrafficBand.PEAK_AM,
            (9, 0): TrafficBand.MID_MORNING, (12, 0): TrafficBand.MIDDAY, (14, 0): TrafficBand.AFTERNOON,
            (17, 0): TrafficBand.PEAK_PM, (19, 59): TrafficBand.PEAK_PM, (20, 0): TrafficBand.NIGHT,
            (23, 30): TrafficBand.NIGHT,
        }
        for (h, m), band in cases.items():
            self.assertEqual(band_for(gt(2026, 10, 6, h, m)), band, f"{h:02d}:{m:02d}")

    def test_utc_is_converted_to_guatemala_time(self):
        # 13:00 UTC = 07:00 en Guatemala (UTC−6)
        self.assertEqual(band_for(datetime(2026, 10, 6, 13, 0, tzinfo=dt_timezone.utc)), TrafficBand.PEAK_AM)
        # 03:00 UTC del domingo = 21:00 del sábado en Guatemala
        self.assertEqual(profile_for(datetime(2026, 10, 4, 3, 0, tzinfo=dt_timezone.utc)),
                         (TrafficBand.NIGHT, DayType.WEEKEND))

    def test_naive_datetime_is_local(self):
        self.assertEqual(band_for(datetime(2026, 10, 6, 18, 0)), TrafficBand.PEAK_PM)

    def test_day_type(self):
        self.assertEqual(day_type_for(gt(2026, 10, 3, 10)), DayType.WEEKEND)  # sábado
        self.assertEqual(day_type_for(gt(2026, 10, 4, 10)), DayType.WEEKEND)  # domingo
        self.assertEqual(day_type_for(gt(2026, 10, 5, 10)), DayType.WEEKDAY)  # lunes

    def test_representative_departure_is_future_and_matches_profile(self):
        now = gt(2026, 10, 6, 9, 0)  # martes
        for band, day_type in PROFILES:
            departure = representative_departure(band, day_type, now)
            self.assertGreater(departure, now)
            self.assertEqual(profile_for(departure), (band, day_type))


class TrafficAwareFakeClient:
    """Google falso: duración = staticDuration × factor de la franja de salida.

    De noche el factor es 0.9: Google estima MENOS que staticDuration.
    """

    FACTORS = {TrafficBand.PEAK_AM: 1.8, TrafficBand.PEAK_PM: 1.5, TrafficBand.NIGHT: 0.9}

    def __init__(self):
        self.requests_made = 0
        self.elements_requested = 0

    def compute_route_matrix(self, origins, destinations, departure_time=None, traffic=False):
        self.requests_made += 1
        self.elements_requested += len(destinations)
        factor = self.FACTORS.get(band_for(departure_time), 1.1) if traffic else 1.0
        return [MatrixElement(0, j, "", 10000.0, 600.0 * factor, 600.0) for j in range(len(destinations))]


def make_node(code, lat, lon):
    return Node.objects.create(code=code, name=code, kind=Node.Kind.MUNICIPIO, department="GU",
                               latitude=lat, longitude=lon)


class GoogleCalibrationTests(TestCase):
    def setUp(self):
        a, b = make_node("a", 14.6, -90.5), make_node("b", 14.6, -90.6)
        self.edge = Edge.objects.create(origin=a, destination=b, distance_km=10, duration_free_min=10.0)
        self.estimated = Edge.objects.create(origin=b, destination=a, distance_km=10, duration_free_min=10.0,
                                             source=Edge.Source.ESTIMATE)

    def test_t0_is_min_observed_and_all_multipliers_at_least_one(self):
        report = calibrate_from_google(TrafficAwareFakeClient(), now=gt(2026, 10, 6, 9))
        self.edge.refresh_from_db()
        self.assertAlmostEqual(self.edge.duration_free_min, 9.0)  # 600 s × 0.9 de noche
        profiles = TrafficProfile.objects.filter(edge=self.edge)
        self.assertEqual(profiles.count(), 14)
        self.assertTrue(all(p.multiplier >= 1.0 for p in profiles))
        night = profiles.get(band=TrafficBand.NIGHT, day_type=DayType.WEEKDAY)
        peak = profiles.get(band=TrafficBand.PEAK_AM, day_type=DayType.WEEKDAY)
        self.assertAlmostEqual(night.multiplier, 1.0)
        self.assertAlmostEqual(peak.multiplier, 1.8 / 0.9)
        self.assertEqual(report.edges_calibrated, 1)

    def test_estimated_edges_are_not_calibrated_with_google(self):
        report = calibrate_from_google(TrafficAwareFakeClient(), now=gt(2026, 10, 6, 9))
        self.assertFalse(TrafficProfile.objects.filter(edge=self.estimated).exists())
        self.assertEqual(report.edges_skipped[0][2], "arista no verificada con Google")


class SyntheticCalibrationTests(TestCase):
    def setUp(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()

    def test_synthetic_profiles_are_complete_idempotent_and_valid(self):
        out = StringIO()
        call_command("calibrate_traffic", "--synthetic", stdout=out)
        call_command("calibrate_traffic", "--synthetic", stdout=StringIO())
        edges = Edge.objects.count()
        self.assertEqual(TrafficProfile.objects.count(), edges * 14)
        self.assertFalse(TrafficProfile.objects.filter(multiplier__lt=1.0).exists())
        self.assertIn("SINTÉTICOS", out.getvalue())

    def test_capital_peaks_are_directional(self):
        """Pico mañana: entrar a la capital es más lento que salir; pico tarde, al revés."""
        calibrate_synthetic()
        mixco, trebol = Node.objects.get(code="mixco"), Node.objects.get(code="el-trebol")
        inbound = Edge.objects.get(origin=mixco, destination=trebol)
        outbound = Edge.objects.get(origin=trebol, destination=mixco)

        def m(edge, band):
            return TrafficProfile.objects.get(edge=edge, band=band, day_type=DayType.WEEKDAY).multiplier

        self.assertGreater(m(inbound, TrafficBand.PEAK_AM), m(outbound, TrafficBand.PEAK_AM))
        self.assertLess(m(inbound, TrafficBand.PEAK_PM), m(outbound, TrafficBand.PEAK_PM))

    def test_synthetic_never_overwrites_google_profiles(self):
        edge = Edge.objects.first()
        TrafficProfile.objects.create(edge=edge, band=TrafficBand.PEAK_AM, day_type=DayType.WEEKDAY,
                                      multiplier=2.3, source="google_routes")
        calibrate_synthetic()
        kept = TrafficProfile.objects.get(edge=edge, band=TrafficBand.PEAK_AM, day_type=DayType.WEEKDAY)
        self.assertEqual((kept.multiplier, kept.source), (2.3, "google_routes"))

    def test_synthetic_multiplier_floor(self):
        import random
        rng = random.Random(1)
        for band, day in PROFILES:
            for near in (True, False):
                for inbound in (True, False):
                    self.assertGreaterEqual(synthetic_multiplier(band, day, near, inbound, rng), 1.0)
