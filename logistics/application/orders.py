"""Casos de uso de pedidos y bodegas de la aplicación nueva (docs/PLAN.md §6 y §7).

Cada pedido guarda la ubicación de entrega (lat/lng) y el nodo del grafo más
cercano, que calcula el servidor con el mismo RoadGraph del motor de rutas.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from django.utils import timezone

from logistics.domain.exceptions import PlanningError
from logistics.models import GT_LAT_MAX, GT_LAT_MIN, GT_LON_MAX, GT_LON_MIN, Depot, Node, Order
from logistics.routing.graph import load_graph

MAX_WEIGHT_KG = Decimal("5000")


def nearest_node(lat: float, lng: float) -> Node:
    graph = load_graph()
    if graph.node_count == 0:
        raise PlanningError("El grafo vial está vacío: corre seed_graph_nodes y build_graph.")
    return Node.objects.get(code=graph.codes[graph.nearest_node(lat, lng)])


def parse_location(payload: dict) -> tuple[float, float]:
    try:
        lat, lng = float(payload["latitude"]), float(payload["longitude"])
    except (KeyError, TypeError, ValueError):
        raise PlanningError("Elige la ubicación de entrega (municipio o punto en el mapa).") from None
    if not (GT_LAT_MIN <= lat <= GT_LAT_MAX and GT_LON_MIN <= lng <= GT_LON_MAX):
        raise PlanningError("La ubicación está fuera de Guatemala.")
    return lat, lng


# --- serialización -----------------------------------------------------------

def node_ref(node: Node | None) -> dict | None:
    return {"code": node.code, "name": node.name} if node else None


def order_payload(order: Order) -> dict:
    return {
        "id": order.id,
        "code": order.code,
        "recipient": order.recipient,
        "phone": order.phone,
        "address": order.address,
        "reference": order.reference,
        "latitude": order.latitude,
        "longitude": order.longitude,
        "node": node_ref(order.node),
        "weight_kg": float(order.weight_kg),
        "package_count": order.package_count,
        "priority": order.priority,
        "status": order.status,
        "status_label": order.get_status_display(),
        "is_demo": order.is_demo,
        "created_at": timezone.localtime(order.created_at).isoformat(),
    }


def depot_payload(depot: Depot) -> dict:
    return {
        "id": depot.id,
        "name": depot.name,
        "address": depot.address,
        "latitude": depot.latitude,
        "longitude": depot.longitude,
        "node": node_ref(depot.node),
    }


# --- casos de uso ------------------------------------------------------------

def app_orders():
    """Pedidos de la aplicación nueva: los que tienen ubicación de entrega."""
    return Order.objects.filter(latitude__isnull=False, longitude__isnull=False).select_related("node")


def list_orders(params) -> dict:
    orders = app_orders()
    query = (params.get("q") or "").strip()
    if query:
        orders = orders.filter(
            Q(code__icontains=query) | Q(recipient__icontains=query) | Q(address__icontains=query)
            | Q(node__name__icontains=query)
        )
    counts = {row["status"]: row["total"] for row in orders.values("status").annotate(total=Count("id"))}
    counts["all"] = sum(counts.values())
    status = params.get("status") or "all"
    if status != "all":
        if status not in Order.Status.values:
            raise PlanningError("Estado inválido.")
        orders = orders.filter(status=status)
    ids = params.get("ids")
    if ids:
        try:
            orders = orders.filter(id__in=[int(x) for x in str(ids).split(",") if x])
        except ValueError:
            raise PlanningError("ids debe ser una lista de números separados por coma.") from None
    return {"orders": [order_payload(o) for o in orders], "counts": counts}


def create_order(payload: dict) -> dict:
    recipient = str(payload.get("recipient", "")).strip()
    address = str(payload.get("address", "")).strip()
    if not recipient:
        raise PlanningError("Indica el destinatario.")
    if not address:
        raise PlanningError("Indica la dirección de entrega.")
    lat, lng = parse_location(payload)
    try:
        weight = Decimal(str(payload.get("weight_kg", "")))
    except InvalidOperation:
        raise PlanningError("El peso debe ser un número en kg.") from None
    if not (Decimal("0") < weight <= MAX_WEIGHT_KG):
        raise PlanningError(f"El peso debe ser mayor que 0 y hasta {MAX_WEIGHT_KG} kg.")
    try:
        packages = int(payload.get("package_count", 1))
    except (TypeError, ValueError):
        raise PlanningError("Los bultos deben ser un número entero.") from None
    if packages < 1:
        raise PlanningError("Debe haber al menos 1 bulto.")
    priority = payload.get("priority") or Order.Priority.NORMAL
    if priority not in Order.Priority.values:
        raise PlanningError("Prioridad inválida.")

    order = Order.objects.create(
        recipient=recipient[:120],
        phone=str(payload.get("phone", "")).strip()[:30],
        address=address[:255],
        reference=str(payload.get("reference", "")).strip()[:255],
        place_id=str(payload.get("place_id", "")).strip()[:255],
        latitude=lat,
        longitude=lng,
        node=nearest_node(lat, lng),
        weight_kg=weight,
        package_count=packages,
        priority=priority,
    )
    return {"order": order_payload(order)}


def list_depots() -> dict:
    return {"depots": [depot_payload(d) for d in Depot.objects.filter(is_active=True).select_related("node")]}
