"""Tráfico del momento: compara la llegada estimada de una ruta con Google ahora mismo."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_POST

from logistics.application.live_traffic import LiveCheckError, live_check
from logistics.models import Route, UserProfile
from logistics.presentation.serializers import _error, _get_role, _ok


@login_required
@require_POST
def api_route_live_check(request: HttpRequest, route_id: int):
    role = _get_role(request)
    route = Route.objects.filter(id=route_id).select_related("driver").first()
    # El conductor solo ve sus rutas; las ajenas responden igual que una que no existe.
    if route is None or (
        role == UserProfile.Role.DRIVER and (route.driver is None or route.driver.user_id != request.user.id)
    ):
        return _error("No se encontró la ruta.", 404)
    try:
        return _ok(live_check(route))
    except LiveCheckError as exc:
        return _error(str(exc), exc.status)
