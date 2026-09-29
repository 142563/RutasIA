from django.urls import path
from logistics.presentation import app_views, routing_views, views

urlpatterns = [
    # Interfaz anterior (JS sin framework), mientras se retira
    path("clasico/", views.index, name="index"),
    # Sesión y configuración de la aplicación React
    path("api/auth/csrf/", app_views.api_csrf, name="api-auth-csrf"),
    path("api/auth/login/", app_views.api_login, name="api-auth-login"),
    path("api/auth/logout/", app_views.api_logout, name="api-auth-logout"),
    path("api/auth/session/", app_views.api_session, name="api-auth-session"),
    path("api/config/", app_views.api_config, name="api-config"),
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
