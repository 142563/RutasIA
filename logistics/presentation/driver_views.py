"""API de la vista móvil del conductor (docs/PLAN.md §7, conductor)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from logistics.presentation.serializers import _error


@login_required
@require_GET
def api_driver_today(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_driver_route_start(request: HttpRequest, route_id: int):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_driver_stop_update(request: HttpRequest, stop_id: int):
    return _error("Pendiente de implementar.", 501)
