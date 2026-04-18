import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Department, Order, RouteConnection, Trip, Vehicle
from .services import PlanningError, RouteOptimizer, TripPlanner


class RouteOptimizerTests(TestCase):
    def setUp(self):
        self.gua = Department.objects.create(code="GUA", name="Guatemala")
        self.esc = Department.objects.create(code="ESC", name="Escuintla")
        self.que = Department.objects.create(code="QUE", name="Quetzaltenango")
        RouteConnection.objects.create(
            origin=self.gua,
            destination=self.esc,
            distance_km=Decimal("64"),
            is_bidirectional=True,
        )
        RouteConnection.objects.create(
            origin=self.esc,
            destination=self.que,
            distance_km=Decimal("160"),
            is_bidirectional=True,
        )

    def test_shortest_path_returns_route_and_distance(self):
        path, distance = RouteOptimizer.shortest_path(self.gua.id, self.que.id)
        self.assertEqual(path, [self.gua.id, self.esc.id, self.que.id])
        self.assertEqual(distance, Decimal("224.00"))


class TripPlanningApiTests(TestCase):
    def setUp(self):
        self.gua = Department.objects.create(code="GUA", name="Guatemala")
        self.esc = Department.objects.create(code="ESC", name="Escuintla")
        self.que = Department.objects.create(code="QUE", name="Quetzaltenango")
        RouteConnection.objects.create(
            origin=self.gua,
            destination=self.esc,
            distance_km=Decimal("64"),
            is_bidirectional=True,
        )
        RouteConnection.objects.create(
            origin=self.esc,
            destination=self.que,
            distance_km=Decimal("160"),
            is_bidirectional=True,
        )
        self.vehicle = Vehicle.objects.create(
            plate="C-111AAA",
            model="Isuzu NPR",
            capacity_kg=Decimal("2500"),
            fuel_efficiency_km_l=Decimal("6.20"),
            cost_per_km=Decimal("4.10"),
            is_active=True,
            current_department=self.gua,
        )
        self.order_1 = Order.objects.create(
            origin=self.gua,
            destination=self.que,
            weight_kg=Decimal("700"),
            package_count=10,
            priority=Order.Priority.NORMAL,
            status=Order.Status.PENDING,
        )
        self.order_2 = Order.objects.create(
            origin=self.gua,
            destination=self.que,
            weight_kg=Decimal("600"),
            package_count=8,
            priority=Order.Priority.HIGH,
            status=Order.Status.PENDING,
        )

    def test_plan_trip_api_creates_trip_and_assigns_orders(self):
        response = self.client.post(
            reverse("api-plan-trip"),
            data=json.dumps(
                {
                    "vehicle_id": self.vehicle.id,
                    "order_ids": [self.order_1.id, self.order_2.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        trip = Trip.objects.get()
        self.assertEqual(trip.status, Trip.Status.PLANNED)
        self.assertEqual(trip.orders.count(), 2)
        self.order_1.refresh_from_db()
        self.order_2.refresh_from_db()
        self.assertEqual(self.order_1.status, Order.Status.ASSIGNED)
        self.assertEqual(self.order_2.status, Order.Status.ASSIGNED)

    def test_trip_planner_validates_capacity(self):
        self.vehicle.capacity_kg = Decimal("900")
        self.vehicle.save(update_fields=["capacity_kg"])
        with self.assertRaisesMessage(PlanningError, "excede la capacidad"):
            TripPlanner.plan_trip(self.vehicle, Order.objects.filter(id__in=[self.order_1.id, self.order_2.id]))

# Create your tests here.
