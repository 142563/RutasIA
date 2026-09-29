"""Validación de los datos semilla del grafo nacional y del comando que los carga."""
from collections import Counter, defaultdict, deque
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from logistics.models import GT_LAT_MAX, GT_LAT_MIN, GT_LON_MAX, GT_LON_MIN, GuatemalaDepartment, Node
from logistics.routing.seed_data import NODES, ROAD_SEGMENTS

CODES = {n.code for n in NODES}


class SeedDataTests(SimpleTestCase):
    def test_expected_size(self):
        self.assertEqual(len(NODES), 108)
        self.assertEqual(len(ROAD_SEGMENTS), 130)

    def test_codes_are_unique(self):
        self.assertEqual(len(CODES), len(NODES))

    def test_one_cabecera_per_department(self):
        cabeceras = Counter(n.department for n in NODES if n.kind == Node.Kind.CABECERA)
        self.assertEqual(set(cabeceras), set(GuatemalaDepartment.values))
        self.assertTrue(all(count == 1 for count in cabeceras.values()), cabeceras)

    def test_valid_kinds_and_departments(self):
        for n in NODES:
            self.assertIn(n.kind, Node.Kind.values, n.code)
            self.assertIn(n.department, GuatemalaDepartment.values, n.code)

    def test_all_nodes_inside_guatemala(self):
        for n in NODES:
            self.assertTrue(GT_LAT_MIN <= n.latitude <= GT_LAT_MAX, n.code)
            self.assertTrue(GT_LON_MIN <= n.longitude <= GT_LON_MAX, n.code)

    def test_segments_reference_existing_nodes_without_duplicates(self):
        seen = set()
        for s in ROAD_SEGMENTS:
            self.assertIn(s.a, CODES, s)
            self.assertIn(s.b, CODES, s)
            self.assertNotEqual(s.a, s.b, s)
            key = frozenset((s.a, s.b))
            self.assertNotIn(key, seen, f"tramo duplicado: {s}")
            seen.add(key)

    def test_every_node_has_a_segment(self):
        used = {s.a for s in ROAD_SEGMENTS} | {s.b for s in ROAD_SEGMENTS}
        self.assertEqual(CODES - used, set())

    def test_candidate_network_is_connected(self):
        """Búsqueda en anchura desde la capital: toda la red debe ser alcanzable."""
        adjacency = defaultdict(set)
        for s in ROAD_SEGMENTS:
            adjacency[s.a].add(s.b)
            adjacency[s.b].add(s.a)
        reached, queue = {"ciudad-guatemala"}, deque(["ciudad-guatemala"])
        while queue:
            for neighbor in adjacency[queue.popleft()] - reached:
                reached.add(neighbor)
                queue.append(neighbor)
        self.assertEqual(CODES - reached, set())


class SeedGraphNodesCommandTests(TestCase):
    def test_command_is_idempotent(self):
        call_command("seed_graph_nodes", stdout=StringIO())
        Node.objects.filter(code="flores").update(name="Nombre cambiado")
        out = StringIO()
        call_command("seed_graph_nodes", stdout=out)

        self.assertEqual(Node.objects.count(), 108)
        self.assertEqual(Node.objects.filter(kind=Node.Kind.CABECERA).count(), 22)
        self.assertEqual(Node.objects.get(code="flores").name, "Flores")
        self.assertIn("0 nuevos", out.getvalue())
