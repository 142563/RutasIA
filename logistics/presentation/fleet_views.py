"""API de Configuración (admin): bodegas, pilotos, camiones y usuarios."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_http_methods

from logistics.presentation.serializers import _error


@login_required
@require_http_methods(["GET", "POST"])
def api_fleet_collection(request: HttpRequest, kind: str):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_fleet_item(request: HttpRequest, kind: str, item_id: int):
    return _error("Pendiente de implementar.", 501)
