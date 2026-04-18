from django.contrib import admin
from .models import Department, Order, RouteConnection, Trip, TripEvent, TripOrder, Vehicle


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

# Register your models here.
