"""Avisos enviados (bitácora NotificationLog) para el detalle de ruta y de pedido (A4, RUT-72)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET

from logistics.presentation.serializers import _error


@login_required
@require_GET
def api_notifications(request: HttpRequest):
    """GET ?route=<id> o ?order=<id>: últimos avisos. Lo implementa A4 (solo admin y despachador)."""
    return _error("Todavía no disponible.", 501)
