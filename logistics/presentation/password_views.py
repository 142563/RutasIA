"""Cambio de contraseña (A2, RUT-70): obligatorio tras entrar con la contraseña temporal."""
from __future__ import annotations

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.views.decorators.http import require_POST

from logistics.application.fleet import MIN_PASSWORD
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _parse_json


@login_required
@require_POST
def api_password_change(request: HttpRequest):
    """POST {current_password, new_password}. Limpia la marca de contraseña temporal y mantiene la sesión."""
    try:
        payload = _parse_json(request)
    except PlanningError as exc:
        return _error(str(exc))
    current = payload.get("current_password")
    new = payload.get("new_password")
    user = request.user
    if not isinstance(current, str) or not user.check_password(current):
        return _error("La contraseña actual no es correcta.", 400)
    if not isinstance(new, str) or len(new) < MIN_PASSWORD:
        return _error(f"La nueva contraseña debe tener al menos {MIN_PASSWORD} caracteres.", 400)
    if new == current:
        return _error("La nueva contraseña debe ser distinta de la actual.", 400)
    try:
        validate_password(new, user)
    except ValidationError as exc:
        return _error(" ".join(exc.messages), 400)
    user.set_password(new)
    user.save(update_fields=["password"])
    UserProfile.objects.filter(user=user).update(must_change_password=False, temp_password_expires_at=None)
    update_session_auth_hash(request, user)  # no cierra la sesión actual
    return _ok({})
