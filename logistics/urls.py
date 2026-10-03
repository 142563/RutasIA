from django.urls import path
from logistics.presentation import (
    app_views, assignment_views, dispatch_views, driver_views, fleet_views, incident_views, live_views, orders_views, routing_views, views,
)

urlpatterns = [
    # Interfaz anterior (JS sin framework), mientras se retira
    path("clasico/", views.index, name="index"),
    # Sesión y configuración de la aplicación React
    path("api/auth/csrf/", app_views.api_csrf, name="api-auth-csrf"),
    path("api/auth/login/", app_views.api_login, name="api-auth-login"),
    path("api/auth/logout/", app_views.api_logout, name="api-auth-logout"),
    path("api/auth/session/", app_views.api_session, name="api-auth-session"),
    path("api/auth/demo/", app_views.api_demo_login, name="api-auth-demo"),
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
    # Aplicación nueva: pedidos y bodegas
    path("api/v2/orders/", orders_views.api_v2_orders, name="api-v2-orders"),
    path("api/v2/depots/", orders_views.api_v2_depots, name="api-v2-depots"),
    path("api/v2/routes/plan/", orders_views.api_v2_routes_plan, name="api-v2-routes-plan"),
    path("api/v2/routes/", orders_views.api_v2_routes, name="api-v2-routes"),
    # Pantallas del despachador: Rutas, Monitoreo, Inicio y Reportes
    path("api/v2/routes/<int:route_id>/", dispatch_views.api_v2_route_detail, name="api-v2-route-detail"),
    # Asignar, reasignar y cancelar rutas
    path("api/v2/assignment/options/", assignment_views.api_assignment_options, name="api-v2-assignment-options"),
    path("api/v2/routes/<int:route_id>/assign/", assignment_views.api_route_assign, name="api-v2-route-assign"),
    path("api/v2/routes/<int:route_id>/cancel/", assignment_views.api_route_cancel, name="api-v2-route-cancel"),
    path("api/v2/routes/<int:route_id>/live-check/", live_views.api_route_live_check, name="api-v2-route-live-check"),
    # Configuración (admin): kind = depots | drivers | vehicles | users
    path("api/v2/fleet/<str:kind>/", fleet_views.api_fleet_collection, name="api-v2-fleet"),
    path("api/v2/fleet/<str:kind>/<int:item_id>/", fleet_views.api_fleet_item, name="api-v2-fleet-item"),
    path("api/v2/dashboard/", dispatch_views.api_v2_dashboard, name="api-v2-dashboard"),
    path("api/v2/monitoring/", dispatch_views.api_v2_monitoring, name="api-v2-monitoring"),
    path("api/v2/reports/", dispatch_views.api_v2_reports, name="api-v2-reports"),
    # Vista del conductor (solo sus rutas)
    path("api/driver/today/", driver_views.api_driver_today, name="api-driver-today"),
    path("api/driver/routes/<int:route_id>/start/", driver_views.api_driver_route_start, name="api-driver-route-start"),
    path("api/driver/stops/<int:stop_id>/", driver_views.api_driver_stop_update, name="api-driver-stop-update"),
    # Motor de rutas nuevo (grafo nacional con tráfico)
    path("api/routing/nodes/", routing_views.api_routing_nodes, name="api-routing-nodes"),
    path("api/routing/route/", routing_views.api_routing_route, name="api-routing-route"),
    path("api/routing/compare/", routing_views.api_routing_compare, name="api-routing-compare"),
    path("api/routing/explore/", routing_views.api_routing_explore, name="api-routing-explore"),
    path("api/routing/best-departure/", routing_views.api_routing_best_departure, name="api-routing-best-departure"),
    path("api/routes/optimize/", routing_views.api_routes_optimize, name="api-routes-optimize"),
    path("api/traffic/profile/", routing_views.api_traffic_profile, name="api-traffic-profile"),
    # Incidentes y recálculo en vivo
    path("api/traffic/incidents/", incident_views.api_incidents, name="api-traffic-incidents"),
    path("api/traffic/incidents/<int:incident_id>/resolve/", incident_views.api_incident_resolve,
         name="api-traffic-incident-resolve"),
    path("api/reroutes/<int:proposal_id>/decision/", incident_views.api_reroute_decision,
         name="api-reroute-decision"),
]
