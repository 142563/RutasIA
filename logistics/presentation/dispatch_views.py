"""API de las pantallas del despachador: Rutas, Monitoreo, Inicio y Reportes."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET

from logistics.presentation.serializers import _error


@login_required
@require_GET
def api_v2_route_detail(request: HttpRequest, route_id: int):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_GET
def api_v2_dashboard(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_GET
def api_v2_monitoring(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_GET
def api_v2_reports(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)
