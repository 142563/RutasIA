"""Avisos enviados (bitácora NotificationLog) para el detalle de ruta y de pedido (A4, RUT-72)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET

from logistics.application.notification_log import recent_for_order, recent_for_route
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _require_role


@login_required
@require_GET
def api_notifications(request: HttpRequest):
    """GET ?route=<id> o ?order=<id>: últimos 50 avisos (solo admin y despachador; nunca el cuerpo)."""
    denied = _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER)
    if denied:
        return denied
    route, order = request.GET.get("route"), request.GET.get("order")
    try:
        if route:
            return _ok({"notifications": recent_for_route(int(route))})
        if order:
            return _ok({"notifications": recent_for_order(int(order))})
    except ValueError:
        return _error("El identificador no es válido.")
    return _error("Indica ?route=<id> o ?order=<id>.")
