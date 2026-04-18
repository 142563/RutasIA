from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/me/", views.api_me, name="api-me"),
    path("api/users/", views.api_users, name="api-users"),
    path("api/dashboard/", views.api_dashboard, name="api-dashboard"),
    path("api/departments/", views.api_departments, name="api-departments"),
    path("api/connections/", views.api_connections, name="api-connections"),
    path("api/drivers/", views.api_drivers, name="api-drivers"),
    path("api/vehicles/", views.api_vehicles, name="api-vehicles"),
    path("api/orders/", views.api_orders, name="api-orders"),
    path("api/trips/", views.api_trips, name="api-trips"),
    path("api/trips/plan/", views.api_plan_trip, name="api-plan-trip"),
    path("api/trips/<int:trip_id>/action/", views.api_trip_action, name="api-trip-action"),
    path("api/trips/<int:trip_id>/events/", views.api_trip_event, name="api-trip-event"),
]
