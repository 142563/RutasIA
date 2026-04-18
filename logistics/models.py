from __future__ import annotations

import random
import string
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def _random_suffix(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        SUPERVISOR = "supervisor", "Supervisor"
        OPERATOR = "operator", "Operador"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OPERATOR)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.get_role_display()})"


class Department(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=80, unique=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class RouteConnection(TimestampedModel):
    origin = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="connections_from",
    )
    destination = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="connections_to",
    )
    distance_km = models.DecimalField(max_digits=8, decimal_places=2)
    is_bidirectional = models.BooleanField(default=True)

    class Meta:
        ordering = ["origin__name", "destination__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["origin", "destination"],
                name="uniq_route_connection_direction",
            ),
            models.CheckConstraint(
                condition=~models.Q(origin=models.F("destination")),
                name="origin_destination_must_differ",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.origin.name} -> {self.destination.name} ({self.distance_km} km)"


class Driver(TimestampedModel):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=30, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.license_number})"


class Vehicle(TimestampedModel):
    plate = models.CharField(max_length=16, unique=True)
    model = models.CharField(max_length=100)
    capacity_kg = models.DecimalField(max_digits=8, decimal_places=2)
    fuel_efficiency_km_l = models.DecimalField(max_digits=8, decimal_places=2)
    cost_per_km = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    current_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )

    class Meta:
        ordering = ["plate"]

    def __str__(self) -> str:
        return f"{self.plate} - {self.model}"


class Order(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ASSIGNED = "assigned", "Asignado"
        IN_TRANSIT = "in_transit", "En tránsito"
        DELIVERED = "delivered", "Entregado"
        CANCELED = "canceled", "Cancelado"

    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"

    code = models.CharField(max_length=24, unique=True, blank=True)
    origin = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="orders_origin")
    destination = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="orders_destination",
    )
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    package_count = models.PositiveIntegerField(default=1)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_for = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            stamp = timezone.now().strftime("%Y%m%d")
            self.code = f"PED-{stamp}-{_random_suffix()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.origin.code}->{self.destination.code})"


class Trip(TimestampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planificado"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Completado"
        CANCELED = "canceled", "Cancelado"

    code = models.CharField(max_length=24, unique=True, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="trips")
    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trips",
    )
    origin = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="trips_origin")
    destination = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="trips_destination",
    )
    orders = models.ManyToManyField(Order, through="TripOrder", related_name="trips")
    route_nodes = models.JSONField(default=list)
    total_distance_km = models.DecimalField(max_digits=9, decimal_places=2)
    estimated_fuel_liters = models.DecimalField(max_digits=9, decimal_places=2)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            stamp = timezone.now().strftime("%Y%m%d")
            self.code = f"VIA-{stamp}-{_random_suffix()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.origin.code}->{self.destination.code})"


class TripOrder(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="uniq_trip_order"),
        ]

    def __str__(self) -> str:
        return f"{self.trip.code} - {self.order.code}"


class TripEvent(TimestampedModel):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="events")
    note = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.trip.code}: {self.note[:50]}"
