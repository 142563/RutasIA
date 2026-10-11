"""El desglose compara las mismas aristas, no dos rutas optimizadas distintas."""
from datetime import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from logistics.application.planning import _variant_payload
from logistics.routing.graph import RoadGraph
from logistics.routing.multistop import plan_multistop
from logistics.routing.traffic import GT_TZ


class TrafficBreakdownTests(SimpleTestCase):
    def test_each_leg_uses_its_own_band_and_excludes_service(self):
        graph = RoadGraph.from_lists(
            [("a", "A", 14.6, -90.5), ("b", "B", 14.7, -90.5)],
            [("a", "b", 10, 10), ("b", "a", 10, 20)],
            multipliers={("dawn", "weekday"): [2, 3], ("peak_am", "weekday"): [4, 1.5]},
        )
        plan = plan_multistop(graph, 0, [1], datetime(2026, 10, 6, 6, 50, tzinfo=GT_TZ),
                              service_min=10, return_to_depot=True)
        # Ida: 20 min; servicio: 10 min; regreso en pico: 30 min. Base: 10 + 20.
        order = SimpleNamespace(id=1, code="P-1", recipient="Cliente", address="Calle 1", node=None,
                                latitude=14.7, longitude=-90.5, weight_kg=1)
        data = _variant_payload({"graph": graph, "orders": [order]}, plan)
        self.assertEqual(data["driving_minutes"], 50)
        self.assertEqual(data["traffic_minutes"], 20)
        self.assertEqual([leg["free_minutes"] for leg in data["legs"]], [10, 20])
