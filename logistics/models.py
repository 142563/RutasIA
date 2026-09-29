from __future__ import annotations

import random
import string
from decimal import Decimal
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


class FuelPrice(TimestampedModel):
    """Singleton — precio de combustible en GTQ/galón. Usar FuelPrice.current()."""
    regular_gtq_gal = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("29.50"))
    super_gtq_gal = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("32.00"))
    diesel_gtq_gal = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("24.00"))
    source = models.CharField(max_length=120, default="MEM Guatemala")

    class Meta:
        verbose_name = "Precio de combustible"

    def __str__(self) -> str:
        return f"Regular Q{self.regular_gtq_gal}/gal — {self.updated_at:%d/%m/%Y %H:%M}"

    @classmethod
    def current(cls) -> "FuelPrice":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        DISPATCHER = "dispatcher", "Despachador"
        DRIVER = "driver", "Conductor"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DISPATCHER)

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
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="driver",
        help_text="Cuenta con la que el conductor entra a su vista móvil.",
    )
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
        IN_TRANSIT = "in_transit", "En ruta"
        DELIVERED = "delivered", "Entregado"
        FAILED = "failed", "No entregado"
        CANCELED = "canceled", "Cancelado"

    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"

    code = models.CharField(max_length=24, unique=True, blank=True)
    # Interfaz clásica: pedidos entre departamentos. Opcionales en los pedidos nuevos.
    origin = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="orders_origin", null=True, blank=True,
    )
    destination = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="orders_destination",
        null=True,
        blank=True,
    )
    # Pedido con dirección real (docs/PLAN.md §6): se asocia al nodo más cercano del grafo.
    recipient = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=255, blank=True, help_text="Referencias para encontrar la dirección.")
    place_id = models.CharField(max_length=255, blank=True, help_text="Google Places (cuando haya key del navegador).")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    node = models.ForeignKey("Node", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    is_demo = models.BooleanField(default=False)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    package_count = models.PositiveIntegerField(default=1)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_for = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            stamp = timezone.localtime().strftime("%Y%m%d")  # fecha de Guatemala, no UTC
            self.code = f"PED-{stamp}-{_random_suffix()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.origin_id and self.destination_id:
            return f"{self.code} ({self.origin.code}->{self.destination.code})"
        return f"{self.code} ({self.recipient or 'sin destinatario'})"


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
    estimated_fuel_gallons = models.DecimalField(max_digits=9, decimal_places=2)
    fuel_price_gtq_gal = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    estimated_fuel_cost_gtq = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            stamp = timezone.localtime().strftime("%Y%m%d")  # fecha de Guatemala, no UTC
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


# ---------------------------------------------------------------------------
# Red vial nacional (motor de rutas nuevo, docs/PLAN.md §2 y §6)
#
# Conviven con Department / RouteConnection mientras la app vieja siga en uso.
# Coordenadas, km y minutos son float: el motor calcula en float y Decimal se
# reserva para dinero.
# ---------------------------------------------------------------------------

# Recuadro que contiene a Guatemala, con un margen pequeño.
GT_LAT_MIN, GT_LAT_MAX = 13.5, 18.0
GT_LON_MIN, GT_LON_MAX = -92.5, -88.0


class GuatemalaDepartment(models.TextChoices):
    ALTA_VERAPAZ = "AV", "Alta Verapaz"
    BAJA_VERAPAZ = "BV", "Baja Verapaz"
    CHIMALTENANGO = "CM", "Chimaltenango"
    CHIQUIMULA = "CQ", "Chiquimula"
    EL_PROGRESO = "PR", "El Progreso"
    ESCUINTLA = "ES", "Escuintla"
    GUATEMALA = "GU", "Guatemala"
    HUEHUETENANGO = "HU", "Huehuetenango"
    IZABAL = "IZ", "Izabal"
    JALAPA = "JA", "Jalapa"
    JUTIAPA = "JU", "Jutiapa"
    PETEN = "PE", "Petén"
    QUETZALTENANGO = "QZ", "Quetzaltenango"
    QUICHE = "QC", "Quiché"
    RETALHULEU = "RE", "Retalhuleu"
    SACATEPEQUEZ = "SA", "Sacatepéquez"
    SAN_MARCOS = "SM", "San Marcos"
    SANTA_ROSA = "SR", "Santa Rosa"
    SOLOLA = "SO", "Sololá"
    SUCHITEPEQUEZ = "SU", "Suchitepéquez"
    TOTONICAPAN = "TO", "Totonicapán"
    ZACAPA = "ZA", "Zacapa"


class Node(models.Model):
    """Nodo del grafo nacional: cabecera, municipio o cruce de carreteras."""

    class Kind(models.TextChoices):
        CABECERA = "cabecera", "Cabecera departamental"
        MUNICIPIO = "municipio", "Municipio"
        CRUCE = "cruce", "Cruce, salida o frontera"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    department = models.CharField(max_length=2, choices=GuatemalaDepartment.choices)
    latitude = models.FloatField()
    longitude = models.FloatField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(latitude__gte=GT_LAT_MIN, latitude__lte=GT_LAT_MAX)
                & models.Q(longitude__gte=GT_LON_MIN, longitude__lte=GT_LON_MAX),
                name="node_inside_guatemala",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Edge(TimestampedModel):
    """Tramo de carretera DIRIGIDO origin -> destination.

    Cada tramo físico son dos aristas: ida y vuelta pueden tener tráfico distinto.
    El costo con tráfico es duration_free_min × TrafficProfile.multiplier.
    """

    class Source(models.TextChoices):
        GOOGLE = "google", "Google Routes API"
        MANUAL = "manual", "Manual"
        # Solo para desarrollar sin key: km y minutos ESTIMADOS, no aptos para la tesis.
        ESTIMATE = "estimate", "Estimado sin conexión"

    origin = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="edges_out")
    destination = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="edges_in")
    distance_km = models.FloatField()
    duration_free_min = models.FloatField(help_text="t0: minutos sin tráfico (staticDuration de Google).")
    road = models.CharField(max_length=20, blank=True, help_text="Carretera principal, p. ej. CA-1.")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.GOOGLE)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["origin__name", "destination__name"]
        constraints = [
            models.UniqueConstraint(fields=["origin", "destination"], name="uniq_edge_direction"),
            models.CheckConstraint(
                condition=~models.Q(origin=models.F("destination")),
                name="edge_origin_destination_must_differ",
            ),
            models.CheckConstraint(condition=models.Q(distance_km__gt=0), name="edge_distance_positive"),
            models.CheckConstraint(condition=models.Q(duration_free_min__gt=0), name="edge_duration_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.origin.name} -> {self.destination.name} ({self.duration_free_min:.1f} min)"


class TrafficBand(models.TextChoices):
    """Franjas horarias de docs/PLAN.md §2.3."""

    DAWN = "dawn", "Madrugada (05:00–07:00)"
    PEAK_AM = "peak_am", "Pico mañana (07:00–09:00)"
    MID_MORNING = "mid_morning", "Media mañana (09:00–12:00)"
    MIDDAY = "midday", "Mediodía (12:00–14:00)"
    AFTERNOON = "afternoon", "Tarde (14:00–17:00)"
    PEAK_PM = "peak_pm", "Pico tarde (17:00–20:00)"
    NIGHT = "night", "Noche (20:00–05:00)"


class DayType(models.TextChoices):
    WEEKDAY = "weekday", "Laboral"
    WEEKEND = "weekend", "Fin de semana"


class TrafficProfile(models.Model):
    """Multiplicador de tráfico m ≥ 1 de una arista en una franja y tipo de día.

    m ≥ 1 lo garantiza la BD: así el costo nunca baja de t0, los pesos nunca son
    negativos (requisito de Dijkstra) y v_max se deriva de un costo mínimo real.
    """

    edge = models.ForeignKey(Edge, on_delete=models.CASCADE, related_name="traffic_profiles")
    band = models.CharField(max_length=12, choices=TrafficBand.choices)
    day_type = models.CharField(max_length=8, choices=DayType.choices)
    multiplier = models.FloatField()
    calibrated_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=40, default="google_routes")

    class Meta:
        ordering = ["edge", "day_type", "band"]
        constraints = [
            models.UniqueConstraint(fields=["edge", "band", "day_type"], name="uniq_traffic_profile"),
            models.CheckConstraint(condition=models.Q(multiplier__gte=1.0), name="traffic_multiplier_gte_1"),
        ]

    def __str__(self) -> str:
        return f"{self.edge} · {self.get_band_display()} · {self.get_day_type_display()}: ×{self.multiplier:.2f}"


class RouteSample(models.Model):
    """Respuesta de Google Routes API para un par de nodos (caché y bitácora).

    band y day_type vacíos = consulta sin tráfico (t0, build_graph); con valor =
    consulta con tráfico para ese perfil (calibrate_traffic). Se guarda todo lo
    que devolvió Google para poder auditar de dónde sale cada peso del grafo.
    """

    origin = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="samples_out")
    destination = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="samples_in")
    band = models.CharField(max_length=12, choices=TrafficBand.choices, blank=True)
    day_type = models.CharField(max_length=8, choices=DayType.choices, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    routing_preference = models.CharField(max_length=30)
    status = models.CharField(max_length=40, blank=True, help_text="Vacío = OK; si no, el error de Google.")
    duration_s = models.FloatField(null=True, blank=True)
    static_duration_s = models.FloatField(null=True, blank=True)
    distance_m = models.FloatField(null=True, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fetched_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["origin", "destination", "band", "day_type"], name="uniq_route_sample"
            ),
        ]

    @property
    def ok(self) -> bool:
        return not self.status and self.duration_s is not None and self.distance_m is not None

    def __str__(self) -> str:
        profile = f"{self.band}/{self.day_type}" if self.band else "sin tráfico"
        return f"{self.origin.code} -> {self.destination.code} [{profile}]"


class Depot(TimestampedModel):
    """Bodega desde donde salen las rutas."""

    name = models.CharField(max_length=120, unique=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    node = models.ForeignKey(Node, on_delete=models.SET_NULL, null=True, blank=True, related_name="depots")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Route(TimestampedModel):
    """Ruta de reparto planificada con el motor nuevo (docs/PLAN.md §6)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planificada"
        IN_PROGRESS = "in_progress", "En curso"
        COMPLETED = "completed", "Completada"
        CANCELED = "canceled", "Cancelada"

    class Criterion(models.TextChoices):
        TIME = "time", "Más rápida (tráfico)"
        DISTANCE = "distance", "Más corta (km)"

    code = models.CharField(max_length=24, unique=True, blank=True)
    depot = models.ForeignKey(Depot, on_delete=models.PROTECT, related_name="routes")
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    departure_at = models.DateTimeField()
    criterion = models.CharField(max_length=10, choices=Criterion.choices, default=Criterion.TIME)
    algorithm = models.CharField(max_length=16, default="astar")
    return_to_depot = models.BooleanField(default=True)
    service_min = models.FloatField(default=10)
    driving_minutes = models.FloatField(help_text="Minutos de manejo con el tráfico de cada tramo.")
    total_km = models.FloatField()
    shortest_minutes = models.FloatField(
        null=True, blank=True, help_text="Minutos de la ruta más corta con el mismo tráfico (para el ahorro).")
    expanded_nodes = models.PositiveIntegerField(default=0)
    finish_at = models.DateTimeField()
    legs = models.JSONField(default=list, help_text="Tramos: nodos, minutos, km, franja.")
    data_source = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    started_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo el conductor inició la ruta.")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-departure_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.code:
            stamp = timezone.localtime().strftime("%Y%m%d")  # fecha de Guatemala, no UTC
            self.code = f"RUT-{stamp}-{_random_suffix()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.code


class RouteStop(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        DELIVERED = "delivered", "Entregado"
        FAILED = "failed", "No entregado"

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="route_stops")
    sequence = models.PositiveIntegerField()
    eta = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reason = models.CharField(max_length=120, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="uniq_route_stop_sequence"),
            models.UniqueConstraint(fields=["route", "order"], name="uniq_route_stop_order"),
        ]

    def __str__(self) -> str:
        return f"{self.route.code} #{self.sequence} {self.order.code}"


class Incident(TimestampedModel):
    """Incidente en la red vial (docs/PLAN.md §8, flujo C).

    Mientras está vigente, cada arista afectada se PENALIZA (multiplier ≥ 1 sobre
    el costo con tráfico) o se BLOQUEA (costo infinito). Nunca resta minutos: así
    los pesos siguen ≥ 0 y la heurística de A* (con v_max del grafo sin
    incidentes) sigue siendo admisible.
    """

    class Kind(models.TextChoices):
        TRAFFIC = "traffic", "Tránsito pesado"
        ACCIDENT = "accident", "Accidente"
        LANDSLIDE = "landslide", "Derrumbe"
        CLOSURE = "closure", "Carretera cerrada"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    edges = models.ManyToManyField(Edge, related_name="incidents")
    blocked = models.BooleanField(default=False, help_text="True = el tramo no se puede usar (costo infinito).")
    multiplier = models.FloatField(default=1.0, help_text="Penalización extra ≥ 1 si no está bloqueado.")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True, help_text="Vacío = vigente hasta que se resuelva.")
    note = models.CharField(max_length=255, blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    route = models.ForeignKey(
        "Route", on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents",
        help_text="Ruta desde la que lo reportó el conductor, si aplica.",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-starts_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(multiplier__gte=1.0), name="incident_multiplier_gte_1"),
        ]

    def __str__(self) -> str:
        effect = "bloqueo" if self.blocked else f"×{self.multiplier:.2f}"
        return f"{self.get_kind_display()} ({effect})"


class RerouteProposal(TimestampedModel):
    """Ruta alternativa que A* propone a un conductor por un incidente.

    El conductor (o el despachador) la acepta o mantiene la ruta actual.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACCEPTED = "accepted", "Aceptada"
        KEPT = "kept", "Mantuvo la ruta"
        EXPIRED = "expired", "Vencida"

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="reroutes")
    incident = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name="reroutes")
    current_minutes = models.FloatField(help_text="Minutos restantes por la ruta actual, con el incidente.")
    proposed_minutes = models.FloatField(help_text="Minutos restantes por la ruta nueva.")
    proposed_legs = models.JSONField(default=list, help_text="Tramos pendientes recalculados con A*.")
    summary = models.CharField(max_length=200, blank=True, help_text='Ej.: "Nueva ruta por Palín: −18 min".')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def minutes_saved(self) -> float:
        return self.current_minutes - self.proposed_minutes

    def __str__(self) -> str:
        return f"{self.route.code}: {self.summary or self.get_status_display()}"
