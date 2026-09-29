"""Historia de demostración: al abrir la app por primera vez ya hay algo vivo que ver.

Crea UNA ruta de hoy para el conductor de demostración, cerca de la capital, ya iniciada
y con la primera entrega hecha. Así Hoy, Rutas, el conductor y Reportes muestran datos
desde el primer minuto, y quedan pedidos pendientes para que tú planifiques.
Usa los mismos casos de uso que la app (create_route, update_stop): nada de atajos.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from logistics.application.driver import update_stop
from logistics.application.planning import create_route
from logistics.domain.regions import DEPARTMENT_REGION
from logistics.models import Depot, Driver, Order, Route, Vehicle

# Metropolitana y Central: una ruta corta y creíble (Mixco, Antigua, Chimaltenango, Escuintla)
DEMO_REGIONS = ("I", "V")


@transaction.atomic
def create_demo_story() -> Route | None:
    """Devuelve la ruta creada, o None si ya había rutas o faltan datos de demostración."""
    if Route.objects.exists():
        return None
    conductor = User.objects.filter(username="conductor").first()
    driver = Driver.objects.filter(user=conductor).first() if conductor else None
    depot = Depot.objects.filter(is_active=True).first()
    if driver is None or depot is None:
        return None

    orders = [
        o for o in Order.objects.filter(is_demo=True, status=Order.Status.PENDING).select_related("node")
        if o.node and DEPARTMENT_REGION.get(o.node.department) in DEMO_REGIONS
    ]
    if len(orders) < 2:
        return None
    vehicle = driver.vehicles.filter(is_active=True).first() or Vehicle.objects.filter(is_active=True).first()

    departure = timezone.localtime() - timedelta(minutes=45)
    result = create_route({
        "depot_id": depot.id,
        "order_ids": [o.id for o in orders],
        "departure": departure.isoformat(),
        "driver_id": driver.id,
        "vehicle_id": vehicle.id if vehicle else None,
    }, user=None)
    route = Route.objects.get(pk=result["route"]["id"])

    # El conductor ya salió y entregó la primera parada
    first = route.stops.order_by("sequence").first()
    update_stop(conductor, first.id, {"status": "delivered"})
    route.refresh_from_db()
    return route
