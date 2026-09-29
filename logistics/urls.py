from django.urls import path
from logistics.presentation import routing_views, views

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
    path("api/fuel-price/", views.api_fuel_price, name="api-fuel-price"),
    # Motor de rutas nuevo (grafo nacional con tráfico)
    path("api/routing/nodes/", routing_views.api_routing_nodes, name="api-routing-nodes"),
    path("api/routing/route/", routing_views.api_routing_route, name="api-routing-route"),
    path("api/routing/compare/", routing_views.api_routing_compare, name="api-routing-compare"),
    path("api/routing/explore/", routing_views.api_routing_explore, name="api-routing-explore"),
    path("api/routing/best-departure/", routing_views.api_routing_best_departure, name="api-routing-best-departure"),
    path("api/routes/optimize/", routing_views.api_routes_optimize, name="api-routes-optimize"),
    path("api/traffic/profile/", routing_views.api_traffic_profile, name="api-traffic-profile"),
]
