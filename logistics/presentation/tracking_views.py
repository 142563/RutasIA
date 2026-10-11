"""Seguimiento público del pedido para el cliente final (A3, RUT-71). Sin sesión y con datos mínimos."""
from __future__ import annotations

from django.http import HttpRequest
from django.views.decorators.http import require_GET

from logistics.presentation.serializers import _error


@require_GET
def api_public_tracking(request: HttpRequest, token: str):
    """GET: estado del pedido por su tracking_token. Lo implementa A3."""
    return _error("Todavía no disponible.", 501)
