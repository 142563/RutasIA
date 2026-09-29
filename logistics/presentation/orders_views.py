"""API de pedidos y bodegas de la aplicación nueva (/api/v2/)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_http_methods

from logistics.application import orders as service
from logistics.application import planning
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _parse_json, _require_role

DISPATCH_ROLES = (UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER)


@login_required
@require_http_methods(["GET", "POST"])
def api_v2_orders(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        if request.method == "GET":
            return _ok(service.list_orders(request.GET))
        return _ok(service.create_order(_parse_json(request)), status=201)
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_GET
def api_v2_depots(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    return _ok(service.list_depots())


@login_required
@require_http_methods(["POST"])
def api_v2_routes_plan(request: HttpRequest):
    """Calcula (sin guardar) la más rápida y la más corta, y las horas de salida alternativas."""
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(planning.plan_route(_parse_json(request)))
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_http_methods(["GET", "POST"])
def api_v2_routes(request: HttpRequest):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    if request.method == "GET":
        return _ok(planning.list_routes())
    try:
        return _ok(planning.create_route(_parse_json(request), request.user), status=201)
    except PlanningError as exc:
        return _error(str(exc))
