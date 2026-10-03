"""API para asignar, reasignar y cancelar rutas ya planificadas."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from logistics.presentation.serializers import _error


@login_required
@require_GET
def api_assignment_options(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_route_assign(request: HttpRequest, route_id: int):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_route_cancel(request: HttpRequest, route_id: int):
    return _error("Pendiente de implementar.", 501)
