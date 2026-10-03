"""Tráfico del momento: compara la llegada estimada de una ruta con Google ahora mismo."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_POST

from logistics.presentation.serializers import _error


@login_required
@require_POST
def api_route_live_check(request: HttpRequest, route_id: int):
    return _error("Pendiente de implementar.", 501)
