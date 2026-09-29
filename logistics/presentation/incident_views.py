"""API de incidentes y recálculo en vivo (docs/PLAN.md §8, flujo C)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_http_methods, require_POST

from logistics.application import incidents as service
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _get_role, _ok, _parse_json, _require_role

ALL_ROLES = (UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER, UserProfile.Role.DRIVER)


@login_required
@require_http_methods(["GET", "POST"])
def api_incidents(request: HttpRequest):
    """GET: incidentes vigentes (?all=1 incluye resueltos) y propuestas pendientes.
    POST: reporta un incidente y devuelve las propuestas de recálculo que generó."""
    denied = _require_role(request, *ALL_ROLES)
    if denied:
        return denied
    try:
        if request.method == "GET":
            include_resolved = request.GET.get("all") in ("1", "true")
            return _ok(service.list_incidents(request.user, _get_role(request), include_resolved))
        return _ok(service.create_incident(_parse_json(request), request.user), status=201)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_POST
def api_incident_resolve(request: HttpRequest, incident_id: int):
    denied = _require_role(request, *ALL_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.resolve_incident(incident_id, request.user, _get_role(request)))
    except PlanningError as exc:
        return _error(str(exc), _status(exc))


@login_required
@require_POST
def api_reroute_decision(request: HttpRequest, proposal_id: int):
    denied = _require_role(request, *ALL_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.decide_reroute(proposal_id, _parse_json(request), request.user, _get_role(request)))
    except PlanningError as exc:
        return _error(str(exc), _status(exc))


def _status(exc: PlanningError) -> int:
    """404 si no existe, 403 si no tiene permiso sobre ese recurso, 400 en los demás casos."""
    message = str(exc)
    if "no existe" in message:
        return 404
    return 403 if message.startswith("Solo ") else 400
