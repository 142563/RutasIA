from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse

from logistics.models import UserProfile
from logistics.domain.exceptions import PlanningError


def _parse_json(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise PlanningError("JSON inválido en la solicitud.")


def _ok(payload: dict, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": True, **payload}, status=status)


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def _get_role(request: HttpRequest) -> str:
    return role_for(request.user)


def role_for(user) -> str:
    """Rol del usuario. Sin perfil: admin si es superusuario; si no, el rol con menos permisos."""
    try:
        return user.profile.role
    except Exception:
        return UserProfile.Role.ADMIN if user.is_superuser else UserProfile.Role.DRIVER


def _require_role(request: HttpRequest, *allowed_roles: str) -> JsonResponse | None:
    if _get_role(request) not in allowed_roles:
        return _error("No tienes permisos para esta acción.", 403)
    return None
