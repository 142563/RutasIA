"""Cambio de contraseña (A2, RUT-70): obligatorio tras entrar con la contraseña temporal."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_POST

from logistics.presentation.serializers import _error


@login_required
@require_POST
def api_password_change(request: HttpRequest):
    """POST {current_password, new_password}. Lo implementa A2."""
    return _error("Todavía no disponible.", 501)
