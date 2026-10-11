"""Avisos al personal según su rol (A4, RUT-72): excepciones, resumen de ruta y avisos al conductor.

El despachador no recibe un correo por cada entrega: solo excepciones y un resumen al terminar su ruta.
Cada función devuelve los correos a los que se envió. Destinatarios: recipients.staff_recipients.
"""
from __future__ import annotations

from django.utils import timezone

from logistics.domain.notifications import Event
from logistics.models import Driver, Incident, NotificationLog, RerouteProposal, Route, RouteStop

from .core import Message, dispatch, format_clock, format_day, format_moment, render_email, site_url
from .recipients import staff_recipients


def _messages(event: Event, users, subject: str, template: str, context: dict, key_object: str,
              route: Route | None = None, order_id: int | None = None) -> list[Message]:
    """Un Message por usuario (la plantilla es la misma; la llave de no repetir incluye al usuario)."""
    html, text = render_email(template, {"subject": subject, **context})
    return [
        Message(
            event=event, audience=NotificationLog.Audience.STAFF, to=user.email, subject=subject, html=html,
            text=text, user_id=user.id, order_id=order_id, route_id=route.id if route else None,
            dedupe_key=f"{event}:{key_object}:user:{user.id}",
        )
        for user in users
    ]


def _route_url(route: Route) -> str:
    return site_url(f"rutas/{route.id}")


def _person(user) -> str:
    return (user.get_full_name() or user.username) if user else "alguien del equipo"


def notify_route_assigned(route_id: int) -> list[str]:
    """Ruta asignada → al conductor, para que sepa cuándo y de dónde sale."""
    route = Route.objects.select_related("depot", "driver__user", "created_by").filter(pk=route_id).first()
    if route is None or route.driver_id is None:
        return []
    if route.status not in (Route.Status.PLANNED, Route.Status.IN_PROGRESS):
        return []
    users = staff_recipients(Event.ROUTE_ASSIGNED, route=route)
    stops = route.stops.count()
    subject = f"Nueva ruta asignada: {route.code}"
    return dispatch(_messages(Event.ROUTE_ASSIGNED, users, subject, "staff_route_assigned", {
        "code": route.code, "day": format_day(route.departure_at), "clock": format_clock(route.departure_at),
        "depot": route.depot.name, "stops": stops, "km": round(route.total_km, 1),
        "minutes": round(route.driving_minutes + route.service_min * stops),
        "url": site_url("conductor"), "status_label": "Nueva ruta",
        "details": [("Ruta", route.code), ("Salida", f"{format_day(route.departure_at)}, {format_clock(route.departure_at)}"),
                    ("Desde", route.depot.name), ("Paradas", f"{stops} parada{'' if stops == 1 else 's'}"), ("Distancia", f"{round(route.total_km, 1)} km".replace(".", ",")),
                    ("Tiempo estimado", f"{round(route.driving_minutes + route.service_min * stops)} min")],
    }, f"route:{route.id}", route=route))


def notify_route_canceled(route_id: int, driver_id: int | None) -> list[str]:
    """Ruta cancelada → al conductor que la tenía (`driver_id` viene aparte: la ruta pudo perderlo)."""
    route = Route.objects.select_related("depot", "driver__user", "created_by").filter(pk=route_id).first()
    if route is None:
        return []
    if route.driver_id is None and driver_id:
        route.driver = Driver.objects.select_related("user").filter(pk=driver_id).first()  # solo en memoria
    users = staff_recipients(Event.ROUTE_CANCELED, route=route)
    subject = f"Ruta cancelada: {route.code}"
    return dispatch(_messages(Event.ROUTE_CANCELED, users, subject, "staff_route_canceled", {
        "code": route.code, "day": format_day(route.departure_at), "clock": format_clock(route.departure_at),
        "depot": route.depot.name, "url": site_url("conductor"), "status_label": "Cancelada",
        "details": [("Ruta", route.code), ("Salía", f"{format_day(route.departure_at)}, {format_clock(route.departure_at)}"),
                    ("Desde", route.depot.name)],
    }, f"route:{route.id}", route=route))


def notify_delivery_failed(stop_id: int) -> list[str]:
    """Entrega fallida → a los administradores y al despachador que creó la ruta."""
    stop = RouteStop.objects.select_related(
        "order", "route__driver", "route__created_by__profile").filter(pk=stop_id).first()
    if stop is None or stop.status != RouteStop.Status.FAILED:
        return []
    route, order = stop.route, stop.order
    users = staff_recipients(Event.DELIVERY_FAILED, route=route)
    subject = f"No entregado: {order.code} · {order.recipient}"
    return dispatch(_messages(Event.DELIVERY_FAILED, users, subject, "staff_delivery_failed", {
        "order_code": order.code, "recipient": order.recipient, "address": order.address,
        "reason": stop.reason or "Sin motivo indicado", "route_code": route.code,
        "driver_name": route.driver.name if route.driver else "sin conductor",
        "when": format_moment(timezone.now()), "url": _route_url(route), "status_label": "No entregado",
        "details": [("Pedido", order.code), ("Cliente", order.recipient), ("Dirección", order.address),
                    ("Motivo", stop.reason or "Sin motivo indicado"), ("Ruta", route.code),
                    ("Conductor", route.driver.name if route.driver else "sin conductor"),
                    ("Hora", format_moment(timezone.now()))],
    }, f"stop:{stop.id}", route=route, order_id=order.id))


def notify_route_completed(route_id: int) -> list[str]:
    """Ruta terminada → resumen al despachador que la creó."""
    route = Route.objects.select_related("driver", "created_by__profile").filter(pk=route_id).first()
    if route is None or route.status != Route.Status.COMPLETED:
        return []
    users = staff_recipients(Event.ROUTE_COMPLETED, route=route)
    if not users:
        return []
    stops = list(route.stops.select_related("order"))
    delivered = [s for s in stops if s.status == RouteStop.Status.DELIVERED]
    failed = [s for s in stops if s.status == RouteStop.Status.FAILED]
    real = None
    if route.started_at and route.completed_at:
        real = max(round((route.completed_at - route.started_at).total_seconds() / 60), 0)
    estimated = round(route.driving_minutes + route.service_min * len(stops))
    subject = f"Ruta {route.code} terminada"
    return dispatch(_messages(Event.ROUTE_COMPLETED, users, subject, "staff_route_completed", {
        "code": route.code, "driver_name": route.driver.name if route.driver else "sin conductor",
        "delivered": len(delivered), "total": len(stops), "failed_count": len(failed),
        "failed": [{"code": s.order.code, "recipient": s.order.recipient, "reason": s.reason or "Sin motivo indicado"}
                   for s in failed],
        "real_minutes": real, "estimated_minutes": estimated, "url": _route_url(route), "status_label": "Terminada",
        "details": [("Ruta", route.code), ("Conductor", route.driver.name if route.driver else "sin conductor"),
                    ("Entregados", f"{len(delivered)} de {len(stops)}"), ("No entregados", str(len(failed))),
                    ("Tiempo", f"{real} min reales contra {estimated} min estimados" if real is not None
                     else f"{estimated} min estimados")],
    }, f"route:{route.id}", route=route))


def notify_incident_reported(incident_id: int) -> list[str]:
    """Incidente reportado → administradores y despachadores activos."""
    incident = Incident.objects.select_related("reported_by", "route").filter(pk=incident_id).first()
    if incident is None:
        return []
    users = staff_recipients(Event.INCIDENT_REPORTED, route=incident.route)
    kind = incident.get_kind_display()
    affected = incident.reroutes.values("route_id").distinct().count()
    subject = f"Incidente reportado: {kind}"
    return dispatch(_messages(Event.INCIDENT_REPORTED, users, subject, "staff_incident_reported", {
        "kind": kind, "blocked": incident.blocked, "note": incident.note,
        "reporter": _person(incident.reported_by),
        "route_code": incident.route.code if incident.route else "",
        "affected_routes": affected,
        "when": format_moment(incident.starts_at), "url": site_url(""), "status_label": "Acción requerida",
        "details": [("Incidente", kind), ("Tramo", "Tramo bloqueado" if incident.blocked else "Sin bloqueo"),
                    ("Reportó", _person(incident.reported_by)), ("Hora", format_moment(incident.starts_at))]
                   + ([("Ruta", incident.route.code)] if incident.route else [])
                   + ([("Rutas afectadas", str(affected))] if affected else []),
    }, f"incident:{incident.id}", route=incident.route))


def notify_reroute_pending(proposal_id: int) -> list[str]:
    """Recálculo por aprobar → al despachador que creó la ruta."""
    proposal = RerouteProposal.objects.select_related("route__created_by__profile", "route__driver").filter(
        pk=proposal_id).first()
    if proposal is None or proposal.status != RerouteProposal.Status.PENDING:
        return []
    route = proposal.route
    users = staff_recipients(Event.REROUTE_PENDING, route=route)
    subject = f"Recálculo por aprobar en {route.code}"
    return dispatch(_messages(Event.REROUTE_PENDING, users, subject, "staff_reroute_pending", {
        "code": route.code, "summary": proposal.summary or "Hay una ruta alternativa",
        "saved": round(proposal.minutes_saved), "driver_name": route.driver.name if route.driver else "sin conductor",
        "url": _route_url(route), "status_label": "Acción requerida",
        "details": [("Ruta", route.code), ("Conductor", route.driver.name if route.driver else "sin conductor"),
                    ("Propuesta", proposal.summary or "Hay una ruta alternativa"),
                    ("Ahorro estimado", f"{round(proposal.minutes_saved)} min")],
    }, f"proposal:{proposal.id}", route=route))


def notify_reroute_approved(proposal_id: int) -> list[str]:
    """Cambio de ruta aprobado → al conductor, para que revise su ruta."""
    proposal = RerouteProposal.objects.select_related("route__driver__user").filter(pk=proposal_id).first()
    if proposal is None or proposal.status != RerouteProposal.Status.ACCEPTED:
        return []
    route = proposal.route
    users = staff_recipients(Event.REROUTE_APPROVED, route=route)
    subject = "Tu ruta cambió"
    return dispatch(_messages(Event.REROUTE_APPROVED, users, subject, "staff_reroute_approved", {
        "code": route.code, "summary": proposal.summary or "Se aplicó una ruta alternativa",
        "url": site_url("conductor"), "status_label": "Ruta actualizada",
        "details": [("Ruta", route.code), ("Cambio", proposal.summary or "Se aplicó una ruta alternativa")],
    }, f"proposal:{proposal.id}", route=route))
