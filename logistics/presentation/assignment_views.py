"""API para asignar, reasignar y cancelar rutas ya planificadas."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from logistics.application import assignment as service
from logistics.domain.exceptions import PlanningError
from logistics.presentation.orders_views import DISPATCH_ROLES
from logistics.presentation.serializers import _error, _ok, _parse_json, _require_role


@login_required
@require_GET
def api_assignment_options(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.options(request.GET.get("route_id"), request.GET.get("departure")))
    except service.RouteNotFound as exc:
        return _error(str(exc), 404)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_POST
def api_route_assign(request: HttpRequest, route_id: int):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.assign(route_id, _parse_json(request)))
    except service.RouteNotFound as exc:
        return _error(str(exc), 404)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_POST
def api_route_cancel(request: HttpRequest, route_id: int):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.cancel(route_id, str(_parse_json(request).get("reason") or "")))
    except service.RouteNotFound as exc:
        return _error(str(exc), 404)
    except PlanningError as exc:
        return _error(str(exc))
