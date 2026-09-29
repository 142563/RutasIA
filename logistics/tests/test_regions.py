from django.test import SimpleTestCase

from logistics.domain.regions import DEPARTMENT_REGION, REGIONS, region_of
from logistics.models import GuatemalaDepartment


class RegionTests(SimpleTestCase):
    def test_every_department_has_a_region(self):
        self.assertEqual(set(DEPARTMENT_REGION), {d.value for d in GuatemalaDepartment})
        self.assertTrue(set(DEPARTMENT_REGION.values()) <= set(REGIONS))

    def test_region_of(self):
        self.assertEqual(region_of("QZ"), {"code": "VI", "name": "Suroccidente"})
        self.assertEqual(region_of("GU"), {"code": "I", "name": "Metropolitana"})
        self.assertIsNone(region_of(""))
        self.assertIsNone(region_of(None))
