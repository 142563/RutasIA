"""RUT-15: incidentes (penalización / bloqueo) y recálculo con A*.

Motor: pesos con incidentes, A* == Dijkstra y ningún peso baja.
Aplicación: escenarios del protocolo (tráfico normal, congestión, cierre de vía).
"""
import json
import math
import random
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from logistics.application.incidents import (
    BLOCKED_MINUTES, incident_penalties, recompute_routes, weights_with_incidents,
)
from logistics.models import (
    Depot, Driver, Edge, Incident, Order, RerouteProposal, Route, RouteStop, UserProfile,
)
from logistics.routing.astar import astar, compute_v_max
from logistics.routing.build import build_estimated
from logistics.routing.calibration import calibrate_synthetic
from logistics.routing.dijkstra import dijkstra
from logistics.routing.geo import haversine_km
from logistics.routing.graph import TIME, RoadGraph, invalidate_graph
from logistics.routing.incidents import (
    BLOCKED, apply_penalties, combine_penalties, search_with_penalties, validate_multiplier,
)
from logistics.tests.test_search import PROFILES, random_multipliers, same_cost


def random_graph(seed: int, n: int = 22) -> RoadGraph:
    """Grafo aleatorio dirigido y conexo (anillo + atajos), con km ≥ recta y velocidades variadas."""
    rng = random.Random(seed)
    nodes = [(f"n{i}", f"N{i}", rng.uniform(14.0, 16.0), rng.uniform(-91.5, -89.5)) for i in range(n)]
    pairs = {(i, (i + 1) % n) for i in range(n)} | {((i + 1) % n, i) for i in range(n)}
    while len(pairs) < n * 3:
        a, b = rng.sample(range(n), 2)
        pairs.add((a, b))
    edges = []
    for a, b in sorted(pairs):
        straight = haversine_km(nodes[a][2], nodes[a][3], nodes[b][2], nodes[b][3])
        km = straight * rng.uniform(1.0, 1.6)
        edges.append((f"n{a}", f"n{b}", km, km / rng.uniform(30, 90) * 60))
    graph = RoadGraph.from_lists(nodes, edges)
    graph.multipliers = random_multipliers(graph.edge_count, seed)
    return graph


class PenaltyFunctionTests(SimpleTestCase):
    def test_apply_multiplies_and_blocks_without_mutating_input(self):
        base = [10.0, 20.0, 0.0, 5.0]
        original = list(base)
        result = apply_penalties(base, {0: 2.0, 2: BLOCKED, 3: 1.0})
        self.assertEqual(base, original)  # la lista cacheada no se toca
        self.assertIsNot(result, base)
        self.assertEqual(result, [20.0, 20.0, math.inf, 5.0])  # w = 0 bloqueado es inf, no nan

    def test_same_edge_penalties_multiply_and_block_wins(self):
        combined = combine_penalties([(1, 1.5), (1, 2.0), (2, 3.0), (2, BLOCKED), (3, BLOCKED), (3, 5.0)])
        self.assertEqual(combined, {1: 3.0, 2: BLOCKED, 3: BLOCKED})

    def test_multiplier_below_one_is_rejected(self):
        for bad in (0.99, 0, -3, float("nan"), "2", True):
            with self.assertRaises(ValueError, msg=str(bad)):
                validate_multiplier(bad)
        with self.assertRaises(ValueError):
            apply_penalties([1.0], {0: 0.5})

    def test_unknown_edge_is_an_error(self):
        with self.assertRaises(IndexError):
            apply_penalties([1.0], {3: 2.0})

    def test_no_weight_ever_goes_down(self):
        graph = random_graph(1)
        rng = random.Random(1)
        for _ in range(20):
            base = graph.weights(TIME, *rng.choice(PROFILES))
            penalties = combine_penalties(
                (rng.randrange(graph.edge_count), BLOCKED if rng.random() < 0.2 else rng.uniform(1.0, 6.0))
                for _ in range(15)
            )
            new = apply_penalties(base, penalties)
            self.assertTrue(all(b >= a for a, b in zip(base, new)))


class SearchWithIncidentsTests(SimpleTestCase):
    def test_astar_equals_dijkstra_with_random_incidents(self):
        """E1 con incidentes: costo(A*) == costo(Dijkstra), también cuando no hay ruta."""
        for seed in range(6):
            graph = random_graph(seed)
            rng = random.Random(100 + seed)
            for band, day in rng.sample(PROFILES, 4):
                base = graph.weights(TIME, band, day)
                penalties = combine_penalties(
                    (rng.randrange(graph.edge_count), BLOCKED if rng.random() < 0.25 else rng.uniform(1.0, 8.0))
                    for _ in range(rng.randint(3, 25))
                )
                weights = apply_penalties(base, penalties)
                v_max = compute_v_max(graph, base)  # de los pesos SIN incidentes
                for _ in range(25):
                    s, t = rng.sample(range(graph.node_count), 2)
                    d = dijkstra(graph, weights, s, t)
                    a = astar(graph, weights, s, t, v_max=v_max)
                    self.assertEqual(d.found, a.found)
                    if d.found:
                        self.assertTrue(same_cost(d.cost, a.cost), (seed, band, s, t, d.cost, a.cost))
                        self.assertTrue(all(weights[e] < math.inf for e in a.edges))
                    via_helper = search_with_penalties(graph, base, penalties, s, t)
                    self.assertEqual(via_helper.found, a.found)
                    if a.found:
                        self.assertTrue(same_cost(via_helper.cost, a.cost))

    def test_recomputing_vmax_on_penalized_weights_is_not_needed(self):
        """v_max sin incidentes sigue siendo cota: con incidentes el v_max recalculado solo baja."""
        graph = random_graph(3)
        base = graph.weights(TIME, *PROFILES[0])
        penalized = apply_penalties(base, {e: 5.0 for e in range(0, graph.edge_count, 2)})
        self.assertLessEqual(compute_v_max(graph, penalized), compute_v_max(graph, base) + 1e-12)

    def test_block_makes_route_avoid_the_edge(self):
        graph = RoadGraph.from_lists(
            nodes=[("a", "A", 14.60, -90.50), ("b", "B", 14.65, -90.60), ("d", "D", 14.70, -90.70)],
            edges=[("a", "b", 12, 10.0), ("b", "d", 12, 10.0), ("a", "d", 22, 25.0)],
        )
        a, d = graph.node_index("a"), graph.node_index("d")
        base = graph.weights(TIME)
        free = search_with_penalties(graph, base, {}, a, d)
        self.assertEqual(free.path_codes(graph), ["a", "b", "d"])
        blocked_edge = free.edges[0]
        result = search_with_penalties(graph, base, {blocked_edge: BLOCKED}, a, d)
        self.assertEqual(result.path_codes(graph), ["a", "d"])
        self.assertEqual(result.cost, 25.0)
        self.assertNotIn(blocked_edge, result.edges)
        # La lista cacheada del grafo sigue intacta
        self.assertEqual(graph.weights(TIME), [10.0, 10.0, 25.0])

    def test_congestion_reroutes_only_if_cheaper(self):
        graph = RoadGraph.from_lists(
            nodes=[("a", "A", 14.60, -90.50), ("b", "B", 14.65, -90.60), ("d", "D", 14.70, -90.70)],
            edges=[("a", "b", 12, 10.0), ("b", "d", 12, 10.0), ("a", "d", 22, 25.0)],
        )
        a, d = graph.node_index("a"), graph.node_index("d")
        base = graph.weights(TIME)
        mild = search_with_penalties(graph, base, {0: 1.2}, a, d)  # 22 < 25: se queda
        self.assertEqual(mild.path_codes(graph), ["a", "b", "d"])
        heavy = search_with_penalties(graph, base, {0: 2.0}, a, d)  # 30 > 25: cambia
        self.assertEqual(heavy.path_codes(graph), ["a", "d"])

    def test_all_blocked_means_no_route(self):
        graph = RoadGraph.from_lists(
            nodes=[("a", "A", 14.60, -90.50), ("b", "B", 14.65, -90.60)],
            edges=[("a", "b", 12, 10.0)],
        )
        for search in (dijkstra, astar):
            r = search(graph, apply_penalties(graph.weights(TIME), {0: BLOCKED}), 0, 1)
            self.assertFalse(r.found)
            self.assertEqual(r.path, [])


class IncidentApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_graph_nodes", stdout=StringIO())
        build_estimated()
        calibrate_synthetic()
        invalidate_graph()
        call_command("seed_demo_data", stdout=StringIO())
        cls.depot = Depot.objects.get(name="Bodega Central")
        cls.dispatcher = User.objects.create_user(username="despachador", password="clave-segura-123")
        UserProfile.objects.create(user=cls.dispatcher, role=UserProfile.Role.DISPATCHER)
        cls.driver_user = User.objects.create_user(username="conductor", password="clave-segura-123")
        UserProfile.objects.create(user=cls.driver_user, role=UserProfile.Role.DRIVER)
        cls.other_user = User.objects.create_user(username="otro", password="clave-segura-123")
        UserProfile.objects.create(user=cls.other_user, role=UserProfile.Role.DRIVER)
        cls.driver = Driver.objects.first()
        cls.driver.user = cls.driver_user
        cls.driver.save()

    def setUp(self):
        invalidate_graph()
        self.client.force_login(self.dispatcher)
        pending = list(Order.objects.filter(is_demo=True, status=Order.Status.PENDING).order_by("id"))
        self.route = self.make_route([o.id for o in pending[:3]])

    def post(self, name, payload, **kwargs):
        return self.client.post(reverse(name, kwargs=kwargs), json.dumps(payload), content_type="application/json")

    def make_route(self, order_ids) -> Route:
        departure = (timezone.now() + timedelta(hours=1)).isoformat()
        response = self.post("api-v2-routes", {"depot_id": self.depot.id, "order_ids": order_ids,
                                               "departure": departure, "driver_id": self.driver.id,
                                               "criterion": "time"})
        self.assertEqual(response.status_code, 201, response.content)
        return Route.objects.get(code=response.json()["route"]["code"])

    def edge_between(self, a: str, b: str) -> Edge:
        return Edge.objects.get(origin__code=a, destination__code=b)

    def leg_pairs(self):
        """(origen, destino) de cada arista de los tramos de la ruta."""
        return [(a, b) for leg in self.route.legs for a, b in zip(leg["nodes"], leg["nodes"][1:])]

    def report(self, edge_pairs, **effect):
        return self.post("api-traffic-incidents", {
            "edges": [{"from": a, "to": b} for a, b in edge_pairs], "route_id": self.route.id, **effect})

    def find_reroutable(self, **effect):
        """Primer tramo de la ruta cuya penalización produce una propuesta (hay alternativa)."""
        for a, b in dict.fromkeys(self.leg_pairs()):
            response = self.report([(a, b)], **effect)
            self.assertEqual(response.status_code, 201, response.content)
            data = response.json()
            if data["proposals"]:
                return (a, b), data
            self.post("api-traffic-incident-resolve", {}, incident_id=data["incident"]["id"])
        self.fail("Ningún tramo de la ruta de prueba tiene alternativa.")

    # --- tráfico normal --------------------------------------------------------

    def test_no_incident_means_no_proposal(self):
        graph_result = recompute_routes()
        self.assertEqual(graph_result["proposals"], [])
        self.assertFalse(RerouteProposal.objects.exists())
        listing = self.client.get(reverse("api-traffic-incidents")).json()
        self.assertEqual(listing["incidents"], [])
        self.assertEqual(listing["reroutes"], [])

    def test_incident_on_unused_edge_creates_no_proposal(self):
        used = set(self.leg_pairs())
        unused = next(e for e in Edge.objects.select_related("origin", "destination")
                      if (e.origin.code, e.destination.code) not in used)
        response = self.report([(unused.origin.code, unused.destination.code)], kind="closure")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["proposals"], [])

    def test_mild_incident_below_one_minute_saving_creates_no_proposal(self):
        a, b = self.leg_pairs()[0]
        response = self.report([(a, b)], kind="traffic", multiplier=1.0)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["proposals"], [])

    # --- congestión ------------------------------------------------------------

    def test_congestion_creates_proposal_with_savings(self):
        (a, b), data = self.find_reroutable(kind="traffic", multiplier=30)
        proposal = data["proposals"][0]
        self.assertGreaterEqual(proposal["minutes_saved"], 1.0)
        self.assertLess(proposal["proposed_minutes"], proposal["current_minutes"])
        self.assertFalse(proposal["current_blocked"])
        self.assertRegex(proposal["summary"], r"^Nueva ruta.*: −\d+ min$")
        self.assertEqual(proposal["status"], "pending")
        # La ruta nueva evita el tramo congestionado
        used = {(x, y) for leg in proposal["proposed_legs"] for x, y in zip(leg["nodes"], leg["nodes"][1:])}
        self.assertNotIn((a, b), used)
        self.assertEqual(data["incident"]["edges"][0]["from"]["code"], a)

    # --- cierre de vía ---------------------------------------------------------

    def test_closure_blocks_edge_and_route_avoids_it(self):
        (a, b), data = self.find_reroutable(kind="closure")
        self.assertTrue(data["incident"]["blocked"])
        proposal = data["proposals"][0]
        self.assertTrue(proposal["current_blocked"])
        self.assertGreaterEqual(proposal["current_minutes"], BLOCKED_MINUTES)
        used = {(x, y) for leg in proposal["proposed_legs"] for x, y in zip(leg["nodes"], leg["nodes"][1:])}
        self.assertNotIn((a, b), used)
        # Los pesos con incidentes dejan la arista en infinito y NO tocan los pesos cacheados
        from logistics.routing.graph import load_graph
        graph = load_graph()
        base = graph.weights(TIME, "peak_am", "weekday")
        snapshot = list(base)
        weights = weights_with_incidents(graph, base)
        self.assertEqual(base, snapshot)
        idx = graph.edge_db_ids.index(self.edge_between(a, b).id)
        self.assertEqual(weights[idx], math.inf)
        self.assertTrue(all(w >= b0 for b0, w in zip(base, weights)))

    def test_both_directions_blocks_reverse_edge_too(self):
        a, b = self.leg_pairs()[0]
        response = self.post("api-traffic-incidents", {
            "kind": "closure", "edges": [{"from": a, "to": b}], "both_directions": True})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(response.json()["incident"]["edges"]), 2)

    def test_accept_replaces_pending_legs_and_updates_etas(self):
        _edge, data = self.find_reroutable(kind="closure")
        proposal = data["proposals"][0]
        stops_before = list(self.route.stops.order_by("sequence").values_list("eta", flat=True))
        response = self.post("api-reroute-decision", {"decision": "accept"}, proposal_id=proposal["id"])
        self.assertEqual(response.status_code, 200, response.content)
        self.route.refresh_from_db()
        db_proposal = RerouteProposal.objects.get(pk=proposal["id"])
        self.assertEqual(db_proposal.status, RerouteProposal.Status.ACCEPTED)
        self.assertEqual(db_proposal.decided_by, self.dispatcher)
        for new in proposal["proposed_legs"]:
            self.assertEqual(self.route.legs[new["index"]]["nodes"], new["nodes"])
            self.assertNotIn("index", self.route.legs[new["index"]])
        self.assertAlmostEqual(self.route.driving_minutes, sum(l["minutes"] for l in self.route.legs), places=6)
        self.assertNotEqual(list(self.route.stops.order_by("sequence").values_list("eta", flat=True)), stops_before)
        # Ya resuelta: no se puede decidir dos veces
        again = self.post("api-reroute-decision", {"decision": "keep"}, proposal_id=proposal["id"])
        self.assertEqual(again.status_code, 400)

    def test_keep_only_records_the_decision(self):
        _edge, data = self.find_reroutable(kind="closure")
        legs_before = list(self.route.legs)
        response = self.post("api-reroute-decision", {"decision": "keep"}, proposal_id=data["proposals"][0]["id"])
        self.assertEqual(response.status_code, 200)
        self.route.refresh_from_db()
        self.assertEqual(self.route.legs, legs_before)
        self.assertEqual(RerouteProposal.objects.get(pk=data["proposals"][0]["id"]).status, "kept")

    def test_new_proposal_expires_previous_pending_one(self):
        _edge, first = self.find_reroutable(kind="closure")
        pairs = [(a, b) for a, b in dict.fromkeys(self.leg_pairs())]
        for a, b in pairs:
            response = self.report([(a, b)], kind="traffic", multiplier=40)
            if response.json()["proposals"]:
                break
        self.assertEqual(RerouteProposal.objects.get(pk=first["proposals"][0]["id"]).status, "expired")
        self.assertEqual(RerouteProposal.objects.filter(route=self.route, status="pending").count(), 1)

    def test_resolve_stops_applying_and_expires_its_proposals(self):
        _edge, data = self.find_reroutable(kind="closure")
        incident_id = data["incident"]["id"]
        response = self.post("api-traffic-incident-resolve", {}, incident_id=incident_id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(Incident.objects.get(pk=incident_id).resolved_at)
        self.assertEqual(RerouteProposal.objects.get(pk=data["proposals"][0]["id"]).status, "expired")
        from logistics.routing.graph import load_graph
        self.assertEqual(incident_penalties(load_graph()), {})
        active = self.client.get(reverse("api-traffic-incidents")).json()
        self.assertEqual(active["incidents"], [])
        history = self.client.get(reverse("api-traffic-incidents"), {"all": 1}).json()
        self.assertEqual(len(history["incidents"]), 1)
        self.assertFalse(history["incidents"][0]["active"])
        self.assertEqual(self.post("api-traffic-incident-resolve", {}, incident_id=incident_id).status_code, 400)

    def test_ended_incident_no_longer_applies(self):
        a, b = self.leg_pairs()[0]
        past = timezone.now() - timedelta(hours=2)
        incident = Incident.objects.create(kind="closure", blocked=True, starts_at=past - timedelta(hours=1),
                                           ends_at=past)
        incident.edges.add(self.edge_between(a, b))
        from logistics.routing.graph import load_graph
        self.assertEqual(incident_penalties(load_graph()), {})

    def test_existing_search_endpoint_ignores_incidents(self):
        """Esta tarea no cambia /api/routing/route: un cierre no altera su resultado."""
        payload = {"origin": "guatemala", "destination": "quetzaltenango", "algorithm": "astar"}
        before = self.client.post(reverse("api-routing-route"), json.dumps(payload), content_type="application/json").json()
        a, b = self.leg_pairs()[0]
        self.report([(a, b)], kind="closure")
        after = self.client.post(reverse("api-routing-route"), json.dumps(payload), content_type="application/json").json()
        self.assertEqual(before["minutes"] if "minutes" in before else before, after["minutes"] if "minutes" in after else after)

    # --- validaciones y permisos ----------------------------------------------

    def test_validation_messages(self):
        a, b = self.leg_pairs()[0]
        bad = [
            ({"kind": "meteoro", "edges": [{"from": a, "to": b}]}, "Tipo de incidente inválido"),
            ({"kind": "traffic"}, "al menos un tramo"),
            ({"kind": "traffic", "edges": [{"from": a, "to": "no-existe"}]}, "No hay un tramo"),
            ({"kind": "traffic", "edges": [999999]}, "No existe el tramo"),
            ({"kind": "traffic", "edges": [{"from": a, "to": b}], "multiplier": 0.5}, "≥ 1"),
            ({"kind": "traffic", "edges": [{"from": a, "to": b}], "multiplier": "x"}, "número"),
            ({"kind": "traffic", "edges": [{"from": a, "to": b}], "multiplier": 999}, "no puede pasar"),
            ({"kind": "traffic", "edges": [{"from": a, "to": b}], "route_id": 999999}, "ruta indicada"),
            ({"kind": "traffic", "edges": [{"from": a, "to": b}], "starts_at": "2026-10-06T08:00",
              "ends_at": "2026-10-06T07:00"}, "posterior"),
        ]
        for payload, fragment in bad:
            response = self.post("api-traffic-incidents", payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertIn(fragment, response.json()["error"], payload)
        self.assertFalse(Incident.objects.exists())

    def test_permissions(self):
        a, b = self.leg_pairs()[0]
        payload = {"kind": "accident", "edges": [{"from": a, "to": b}], "multiplier": 2}
        # Un conductor puede reportar y consultar, pero no resolver incidentes ajenos
        self.client.force_login(self.driver_user)
        created = self.post("api-traffic-incidents", payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["incident"]["reported_by"], "conductor")
        self.assertEqual(self.client.get(reverse("api-traffic-incidents")).status_code, 200)
        incident_id = created.json()["incident"]["id"]
        self.client.force_login(self.other_user)
        self.assertEqual(self.post("api-traffic-incident-resolve", {}, incident_id=incident_id).status_code, 403)
        self.client.force_login(self.driver_user)
        self.assertEqual(self.post("api-traffic-incident-resolve", {}, incident_id=incident_id).status_code, 200)
        self.client.logout()
        self.assertIn(self.client.get(reverse("api-traffic-incidents")).status_code, (302, 401, 403))

    def test_only_route_driver_or_dispatch_can_decide(self):
        _edge, data = self.find_reroutable(kind="closure")
        proposal_id = data["proposals"][0]["id"]
        self.client.force_login(self.other_user)
        self.assertEqual(self.post("api-reroute-decision", {"decision": "keep"}, proposal_id=proposal_id).status_code, 403)
        listing = self.client.get(reverse("api-traffic-incidents")).json()
        self.assertEqual(listing["reroutes"], [])  # no ve propuestas de rutas ajenas
        self.client.force_login(self.driver_user)
        listing = self.client.get(reverse("api-traffic-incidents")).json()
        self.assertEqual(len(listing["reroutes"]), 1)
        self.assertEqual(self.post("api-reroute-decision", {"decision": "quizás"}, proposal_id=proposal_id).status_code, 400)
        self.assertEqual(self.post("api-reroute-decision", {"decision": "accept"}, proposal_id=proposal_id).status_code, 200)

    def test_completed_or_delivered_legs_are_not_recalculated(self):
        """Solo cuentan los tramos pendientes: si ya se entregaron todas las paradas y se completó, no hay propuesta."""
        Route.objects.filter(pk=self.route.pk).update(status=Route.Status.COMPLETED)
        a, b = self.leg_pairs()[0]
        response = self.report([(a, b)], kind="closure")
        self.assertEqual(response.json()["proposals"], [])
        Route.objects.filter(pk=self.route.pk).update(status=Route.Status.IN_PROGRESS)
        RouteStop.objects.filter(route=self.route).update(status=RouteStop.Status.DELIVERED)
        legs = self.route.legs
        # Todas entregadas: solo queda pendiente el regreso a la bodega (último tramo)
        return_leg = legs[-1]
        rp = [(x, y) for x, y in zip(return_leg["nodes"], return_leg["nodes"][1:])]
        first_leg_only = [p for p in zip(legs[0]["nodes"], legs[0]["nodes"][1:]) if p not in rp]
        if first_leg_only:
            r = self.report([first_leg_only[0]], kind="closure")
            self.assertEqual(r.json()["proposals"], [])
