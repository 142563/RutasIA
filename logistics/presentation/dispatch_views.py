"""API de las pantallas del despachador: Rutas, Monitoreo, Inicio y Reportes."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET

from logistics.application import dispatch as service
from logistics.domain.exceptions import PlanningError
from logistics.presentation.orders_views import DISPATCH_ROLES
from logistics.presentation.serializers import _error, _ok, _require_role


@login_required
@require_GET
def api_v2_route_detail(request: HttpRequest, route_id: int):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.route_detail(route_id))
    except service.RouteNotFound as exc:
        return _error(str(exc), 404)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_GET
def api_v2_dashboard(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    return _ok(service.dashboard())


@login_required
@require_GET
def api_v2_monitoring(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    return _ok(service.monitoring())


@login_required
@require_GET
def api_v2_reports(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    return _ok(service.reports())
