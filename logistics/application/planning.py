"""Planificador con tráfico (docs/PLAN.md §8, flujo A).

1. Bodega + hora de salida + pedidos → dos variantes con el MISMO tráfico:
   la más rápida (minutos con tráfico) y la más corta (km).
2. "¿A qué hora conviene salir?": la misma ruta saliendo en cada franja del día.
3. Confirmar: el servidor recalcula la variante elegida (nunca confía en el
   cliente), guarda la ruta con sus paradas y marca los pedidos como asignados.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from time import perf_counter

from django.db import transaction
from django.utils import timezone

from logistics.application import assignment
from logistics.application.notifications import later, on_route_created
from logistics.application.orders import app_orders, node_ref
from logistics.application.routing import (avoid_unpaved, get_graph, optimizer_params, optimizer_payload,
                                           parse_departure, roads_along)
from logistics.domain.exceptions import PlanningError
from logistics.models import Depot, Driver, Order, Route, RouteStop, TrafficBand, Vehicle
from logistics.routing.graph import TIME, RoadGraph
from logistics.routing.multistop import (DEFAULT_SERVICE_MIN, FIXED, GENETIC, NN2OPT, MultiStopPlan, UnreachableStopError,
                                         plan_multistop)
from logistics.routing.traffic import GT_TZ, REPRESENTATIVE_TIME, profile_for

MAX_STOPS = 50
CRITERIA = (Route.Criterion.TIME, Route.Criterion.DISTANCE)


def _parse_request(payload: dict):
    graph = get_graph()
    try:
        depot = Depot.objects.select_related("node").get(pk=payload.get("depot_id"), is_active=True)
    except (Depot.DoesNotExist, ValueError, TypeError):
        raise PlanningError("Elige una bodega válida.") from None

    ids = payload.get("order_ids")
    if not isinstance(ids, list) or not ids:
        raise PlanningError("Selecciona al menos un pedido.")
    if len(ids) > MAX_STOPS:
        raise PlanningError(f"Máximo {MAX_STOPS} pedidos por ruta.")
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        raise PlanningError("order_ids debe ser una lista de números.") from None
    by_id = {o.id: o for o in app_orders().filter(id__in=ids)}
    if len(by_id) != len(set(ids)):
        raise PlanningError("Uno o más pedidos no existen.")
    orders = [by_id[i] for i in dict.fromkeys(ids)]  # sin duplicados, en el orden de captura
    not_pending = [o.code for o in orders if o.status != Order.Status.PENDING]
    if not_pending:
        raise PlanningError(f"Estos pedidos ya no están pendientes: {', '.join(not_pending)}.")

    try:
        service_min = float(payload.get("service_min", DEFAULT_SERVICE_MIN))
    except (TypeError, ValueError):
        raise PlanningError("El tiempo de servicio debe ser un número de minutos.") from None
    if not 0 <= service_min <= 120:
        raise PlanningError("El tiempo de servicio debe estar entre 0 y 120 minutos.")

    return {
        "graph": graph,
        "depot": depot,
        "orders": orders,
        "departure": parse_departure(payload.get("departure")),
        "service_min": service_min,
        "return_to_depot": bool(payload.get("return_to_depot", True)),
        "avoid_unpaved": avoid_unpaved(payload),
        "ga_params": optimizer_params(),
    }


def _node_of(graph: RoadGraph, code: str | None, lat: float, lng: float) -> int:
    if code and code in graph.index:
        return graph.index[code]
    return graph.nearest_node(lat, lng)


def _plan(req: dict, criterion: str, departure: datetime | None = None, fixed_order=None,
          optimizer: str = GENETIC) -> MultiStopPlan:
    graph, depot = req["graph"], req["depot"]
    depot_node = _node_of(graph, depot.node.code if depot.node else None, depot.latitude, depot.longitude)
    stops = [_node_of(graph, o.node.code if o.node else None, o.latitude, o.longitude) for o in req["orders"]]
    try:
        return plan_multistop(graph, depot_node, stops, departure or req["departure"], req["service_min"],
                              req["return_to_depot"], criterion, fixed_order, req["avoid_unpaved"],
                              optimizer=optimizer, ga_params=req["ga_params"])
    except UnreachableStopError as exc:
        raise PlanningError(f"No hay ruta hacia {graph.names[exc.node]}.") from None


def _shortest(req: dict, departure: datetime | None = None, optimizer: str = GENETIC) -> MultiStopPlan:
    return _plan(req, Route.Criterion.DISTANCE, departure, optimizer=optimizer)


def _fastest(req: dict, departure: datetime | None = None,
             shortest: MultiStopPlan | None = None, optimizer: str = GENETIC) -> MultiStopPlan:
    """La ruta con MENOS minutos entre varios candidatos, medidos con el mismo tráfico.

    El orden de las paradas sale del algoritmo genético (sembrado con vecino más
    cercano + 2-opt) y
    se optimiza con el tráfico de la hora de salida, mientras que cada tramo se
    recorre en su propia franja. Por eso el orden pensado para km puede resultar
    más rápido. Se evalúan:
      1. orden optimizado por tiempo, tramos por tiempo;
      2. orden optimizado por km, tramos por tiempo;
      3. la más corta tal cual.
    Así, por construcción, la más rápida nunca tarda más que la más corta.
    """
    shortest = shortest or _shortest(req, departure, optimizer)
    candidates = [
        _plan(req, Route.Criterion.TIME, departure, optimizer=optimizer),
        _plan(req, Route.Criterion.TIME, departure, fixed_order=shortest.order),
        shortest,
    ]
    best = min(candidates, key=lambda plan: plan.driving_minutes)
    if best.optimizer == FIXED:
        # El orden de km lo calculó el optimizador de la más corta: se le atribuye a él
        best.optimizer, best.ga_generations, best.optimize_ms = (
            shortest.optimizer, shortest.ga_generations, shortest.optimize_ms)
    return best


def _variant_payload(req: dict, plan: MultiStopPlan) -> dict:
    graph, orders = req["graph"], req["orders"]
    stops = []
    for sequence, (index, eta) in enumerate(zip(plan.order, plan.etas), start=1):
        o = orders[index]
        stops.append({
            "sequence": sequence, "order_id": o.id, "code": o.code, "recipient": o.recipient,
            "address": o.address, "node": node_ref(o.node), "lat": o.latitude, "lng": o.longitude,
            "weight_kg": float(o.weight_kg), "eta": eta.isoformat(),
        })
    legs = [
        {
            "nodes": [graph.codes[i] for i in leg.search.path],
            "roads": roads_along(graph, leg.search.edges),
            "minutes": round(leg.minutes, 2),
            "free_minutes": round(leg.search.total(graph.t0), 2),
            "km": round(leg.km, 2),
            "unpaved_km": round(graph.unpaved_km(leg.search.edges), 2),
            "band": leg.band,
            "depart_at": leg.depart_at.isoformat(),
            "arrive_at": leg.arrive_at.isoformat(),
            "expanded": leg.search.expanded,
        }
        for leg in plan.legs
    ]
    return {
        # El criterio con el que se trazaron los tramos (la más rápida puede resultar ser la de km)
        "criterion": plan.criterion,
        "driving_minutes": round(plan.driving_minutes, 2),
        "traffic_minutes": round(sum(leg.minutes - leg.search.total(graph.t0) for leg in plan.legs), 2),
        "total_km": round(plan.total_km, 2),
        "finish_at": plan.finish_at.isoformat(),
        "expanded": plan.expanded,
        "stops": stops,
        "legs": legs,
        **optimizer_payload(plan),
    }


def _departure_options(req: dict) -> list[dict]:
    """La ruta más rápida saliendo a la hora representativa de cada franja del mismo día.

    Es una estimación para comparar horas (7 franjas × 2 variantes): el orden se
    calcula con vecino más cercano + 2-opt para no correr 14 genéticos por solicitud
    y mantener la respuesta por debajo de 30 s con 50 paradas. La ruta que se guarda
    siempre la ordena el genético.
    """
    day = req["departure"].date()
    options = []
    for band in TrafficBand.values:
        departure = datetime.combine(day, REPRESENTATIVE_TIME[band], tzinfo=GT_TZ)
        plan = _fastest(req, departure, optimizer=NN2OPT)
        options.append({
            "band": band,
            "band_label": TrafficBand(band).label.split(" (")[0],
            "departure": departure.isoformat(),
            "driving_minutes": round(plan.driving_minutes, 2),
        })
    return options


def plan_route(payload: dict) -> dict:
    started = perf_counter()
    req = _parse_request(payload)
    shortest = _shortest(req)
    fastest = _fastest(req, shortest=shortest)
    band, day_type = profile_for(req["departure"])
    depot = req["depot"]
    return {
        "depot": {"id": depot.id, "name": depot.name, "lat": depot.latitude, "lng": depot.longitude,
                  "node": node_ref(depot.node)},
        "departure": req["departure"].isoformat(),
        "band": band,
        "band_label": TrafficBand(band).label,
        "day_type": day_type,
        "service_min": req["service_min"],
        "return_to_depot": req["return_to_depot"],
        "avoid_unpaved": req["avoid_unpaved"],
        "total_weight_kg": float(sum(o.weight_kg for o in req["orders"])),
        "fastest": _variant_payload(req, fastest),
        "shortest": _variant_payload(req, shortest),
        "minutes_saved": round(shortest.driving_minutes - fastest.driving_minutes, 2),
        "departure_options": _departure_options(req),
        "data_source": req["graph"].sources,
        # Tiempo real de respuesta del servidor para esta solicitud (tesis: meta < 30 s)
        "response_seconds": round(perf_counter() - started, 3),
    }


@transaction.atomic
def create_route(payload: dict, user) -> dict:
    criterion = payload.get("criterion") or Route.Criterion.TIME
    if criterion not in CRITERIA:
        raise PlanningError("Criterio inválido. Usa 'time' o 'distance'.")
    # Bloquea los pedidos mientras se asignan (evita asignarlos dos veces)
    list(Order.objects.select_for_update().filter(id__in=payload.get("order_ids") or []))
    req = _parse_request(payload)

    # Activo y capacidad aquí; la disponibilidad por horario, tras calcular la hora de fin
    driver, vehicle = assignment.validate_for_new_route(payload, sum(o.weight_kg for o in req["orders"]))

    shortest = _shortest(req)
    plan = shortest if criterion == Route.Criterion.DISTANCE else _fastest(req, shortest=shortest)
    assignment.ensure_available(driver, vehicle, req["departure"], plan.finish_at)
    variant = _variant_payload(req, plan)
    route = Route.objects.create(
        depot=req["depot"], driver=driver, vehicle=vehicle, created_by=user,
        departure_at=req["departure"], criterion=criterion, optimizer=plan.optimizer,
        return_to_depot=req["return_to_depot"],
        service_min=req["service_min"], driving_minutes=plan.driving_minutes, total_km=plan.total_km,
        shortest_minutes=shortest.driving_minutes, expanded_nodes=plan.expanded, finish_at=plan.finish_at,
        legs=variant["legs"], data_source=";".join(f"{k}={v}" for k, v in sorted(req["graph"].sources.items())),
    )
    RouteStop.objects.bulk_create([
        RouteStop(route=route, order_id=stop["order_id"], sequence=stop["sequence"],
                  eta=datetime.fromisoformat(stop["eta"]))
        for stop in variant["stops"]
    ])
    Order.objects.filter(id__in=[o.id for o in req["orders"]]).update(
        status=Order.Status.ASSIGNED, updated_at=timezone.now())
    later(on_route_created, route.id)
    return {"route": route_payload(route)}


def route_payload(route: Route) -> dict:
    stops = list(route.stops.select_related("order", "order__node"))
    return {
        "id": route.id,
        "code": route.code,
        "status": route.status,
        "status_label": route.get_status_display(),
        "criterion": route.criterion,
        "optimizer": route.optimizer,
        "depot": route.depot.name,
        # Coordenadas reales de la bodega: el mapa dibuja el primer tramo hasta su nodo
        "depot_lat": route.depot.latitude, "depot_lng": route.depot.longitude,
        "driver": route.driver.name if route.driver else None,
        "driver_id": route.driver_id,
        "vehicle": route.vehicle.plate if route.vehicle else None,
        "departure_at": timezone.localtime(route.departure_at).isoformat(),
        "finish_at": timezone.localtime(route.finish_at).isoformat(),
        "started_at": _local_iso(route.started_at),
        "completed_at": _local_iso(route.completed_at),
        "driving_minutes": round(route.driving_minutes, 2),
        "traffic_minutes": stored_traffic_minutes(route.legs),
        "total_km": round(route.total_km, 2),
        "minutes_saved": round(route.shortest_minutes - route.driving_minutes, 2) if route.shortest_minutes else None,
        "data_source": route.data_source,
        "stops": [
            {"id": s.id, "sequence": s.sequence, "order_code": s.order.code, "recipient": s.order.recipient,
             "phone": s.order.phone, "address": s.order.address, "reference": s.order.reference,
             "lat": s.order.latitude, "lng": s.order.longitude,
             "node": node_ref(s.order.node), "eta": timezone.localtime(s.eta).isoformat(),
             "status": s.status, "status_label": s.get_status_display(), "reason": s.reason,
             "delivered_at": _local_iso(s.delivered_at)}
            for s in stops
        ],
    }


def stored_traffic_minutes(legs: list[dict]) -> float | None:
    # Las rutas anteriores no guardaban t0: no reconstruir su historia con el grafo actual.
    if not legs or any("free_minutes" not in leg for leg in legs):
        return None
    return round(sum(max(0, leg["minutes"] - leg["free_minutes"]) for leg in legs), 2)


def _local_iso(moment) -> str | None:
    return timezone.localtime(moment).isoformat() if moment else None


def list_routes() -> dict:
    routes = Route.objects.select_related("depot", "driver", "vehicle")[:50]
    return {"routes": [route_payload(r) for r in routes]}
