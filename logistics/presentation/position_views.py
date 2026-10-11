from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from logistics.application import positions as service
from logistics.application.driver import NotFoundError
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.orders_views import DISPATCH_ROLES
from logistics.presentation.serializers import _error, _ok, _parse_json, _require_role


def _fail(exc):
    return _error(str(exc), 429 if isinstance(exc, service.PositionRateError) else 404 if isinstance(exc, NotFoundError) else 400)


@login_required
@require_POST
def api_driver_position(request):
    denied = _require_role(request, UserProfile.Role.DRIVER)
    if denied:
        return denied
    try:
        return _ok(service.record_position(request.user, _parse_json(request)), 201)
    except PlanningError as exc:
        return _fail(exc)


@login_required
@require_GET
def api_route_positions(request, route_id):
    denied = _require_role(request, *DISPATCH_ROLES)
    if denied:
        return denied
    try:
        return _ok(service.route_positions(route_id, request.GET))
    except PlanningError as exc:
        return _fail(exc)
