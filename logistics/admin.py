from django.contrib import admin
from .models import Department, Depot, Edge, Incident, RerouteProposal, Route, RouteStop, Node, Order, RouteConnection, TrafficProfile, Trip, TripEvent, TripOrder, Vehicle


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(RouteConnection)
class RouteConnectionAdmin(admin.ModelAdmin):
    list_display = ("origin", "destination", "distance_km", "is_bidirectional")
    list_filter = ("is_bidirectional",)
    search_fields = ("origin__name", "destination__name")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "model", "capacity_kg", "fuel_efficiency_km_l", "cost_per_km", "is_active")
    list_filter = ("is_active",)
    search_fields = ("plate", "model")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("code", "origin", "destination", "weight_kg", "package_count", "priority", "status")
    list_filter = ("status", "priority")
    search_fields = ("code",)


class TripOrderInline(admin.TabularInline):
    model = TripOrder
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "vehicle",
        "origin",
        "destination",
        "total_distance_km",
        "estimated_cost",
        "status",
    )
    list_filter = ("status",)
    search_fields = ("code", "vehicle__plate")
    inlines = [TripOrderInline]


@admin.register(TripEvent)
class TripEventAdmin(admin.ModelAdmin):
    list_display = ("trip", "note", "created_at")
    search_fields = ("trip__code", "note")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "department", "latitude", "longitude", "is_active")
    list_filter = ("kind", "department", "is_active")
    search_fields = ("code", "name")


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("origin", "destination", "road", "distance_km", "duration_free_min", "source", "is_active")
    list_filter = ("road", "source", "is_active")
    search_fields = ("origin__name", "destination__name", "road")


@admin.register(TrafficProfile)
class TrafficProfileAdmin(admin.ModelAdmin):
    list_display = ("edge", "band", "day_type", "multiplier", "calibrated_at")
    list_filter = ("band", "day_type")
    search_fields = ("edge__origin__name", "edge__destination__name")


@admin.register(Depot)
class DepotAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "node", "is_active")
    list_filter = ("is_active",)


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 0


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("code", "depot", "driver", "departure_at", "criterion", "driving_minutes", "total_km", "status")
    list_filter = ("status", "criterion")
    inlines = [RouteStopInline]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("kind", "blocked", "multiplier", "starts_at", "ends_at", "resolved_at")
    list_filter = ("kind", "blocked")
    filter_horizontal = ("edges",)


@admin.register(RerouteProposal)
class RerouteProposalAdmin(admin.ModelAdmin):
    list_display = ("route", "summary", "current_minutes", "proposed_minutes", "status", "created_at")
    list_filter = ("status",)
