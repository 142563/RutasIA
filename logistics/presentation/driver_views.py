"""API de la vista móvil del conductor (docs/PLAN.md §7, conductor)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from logistics.application import driver as service
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _parse_json, _require_role


def _fail(exc: PlanningError):
    return _error(str(exc), 404 if isinstance(exc, service.NotFoundError) else 400)


@login_required
@require_GET
def api_driver_today(request: HttpRequest):
    denied = _require_role(request, UserProfile.Role.DRIVER)
    if denied:
        return denied
    try:
        return _ok(service.today_routes(request.user))
    except PlanningError as exc:
        return _fail(exc)


@login_required
@require_POST
def api_driver_route_start(request: HttpRequest, route_id: int):
    denied = _require_role(request, UserProfile.Role.DRIVER)
    if denied:
        return denied
    try:
        return _ok(service.start_route(request.user, route_id))
    except PlanningError as exc:
        return _fail(exc)


@login_required
@require_POST
def api_driver_stop_update(request: HttpRequest, stop_id: int):
    denied = _require_role(request, UserProfile.Role.DRIVER)
    if denied:
        return denied
    try:
        return _ok(service.update_stop(request.user, stop_id, _parse_json(request)))
    except PlanningError as exc:
        return _fail(exc)
