"""API de Configuración (admin): bodegas, pilotos, camiones y usuarios."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_http_methods

from logistics.application import fleet
from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _parse_json, _require_role

# El despachador solo puede consultar (lo necesita el planificador).
_DISPATCHER_READS = {"depots", "drivers", "vehicles"}


def _guard(request: HttpRequest, kind: str):
    if kind not in fleet.KINDS:
        return _error("Sección no encontrada.", 404)
    if request.method == "GET" and kind in _DISPATCHER_READS:
        return _require_role(request, UserProfile.Role.ADMIN, UserProfile.Role.DISPATCHER)
    return _require_role(request, UserProfile.Role.ADMIN)


def _body(request: HttpRequest) -> dict:
    body = _parse_json(request)
    if not isinstance(body, dict):
        raise PlanningError("JSON inválido en la solicitud.")
    return body


@login_required
@require_http_methods(["GET", "POST"])
def api_fleet_collection(request: HttpRequest, kind: str):
    if (denied := _guard(request, kind)) is not None:
        return denied
    try:
        if request.method == "GET":
            return _ok(fleet.list_items(kind))
        return _ok(fleet.create_item(kind, _body(request), request.user), 201)
    except PlanningError as exc:
        return _error(str(exc), 400)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_fleet_item(request: HttpRequest, kind: str, item_id: int):
    if (denied := _guard(request, kind)) is not None:
        return denied
    try:
        if request.method == "GET":
            return _ok(fleet.get_item(kind, item_id))
        if request.method == "PATCH":
            return _ok(fleet.update_item(kind, item_id, _body(request), request.user))
        return _ok(fleet.deactivate_item(kind, item_id, request.user))
    except LookupError as exc:
        return _error(str(exc), 404)
    except PlanningError as exc:
        return _error(str(exc), 400)
