"""API de incidentes y recálculo en vivo (docs/PLAN.md §8, flujo C)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_http_methods, require_POST

from logistics.presentation.serializers import _error


@login_required
@require_http_methods(["GET", "POST"])
def api_incidents(request: HttpRequest):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_incident_resolve(request: HttpRequest, incident_id: int):
    return _error("Pendiente de implementar.", 501)


@login_required
@require_POST
def api_reroute_decision(request: HttpRequest, proposal_id: int):
    return _error("Pendiente de implementar.", 501)
