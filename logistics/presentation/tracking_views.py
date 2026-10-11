"""Seguimiento público del pedido para el cliente final (A3, RUT-71). Sin sesión y con datos mínimos."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from logistics.application.tracking import build_payload

NOT_FOUND = "No encontramos ese pedido."


def _no_store(response: JsonResponse) -> JsonResponse:
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def api_public_tracking(request: HttpRequest, token: str):
    """GET: estado del pedido por su tracking_token. Respuesta genérica si no existe (sin pistas)."""
    payload = build_payload(token)
    if payload is None:
        return _no_store(JsonResponse({"ok": False, "error": NOT_FOUND}, status=404))
    return _no_store(JsonResponse(payload))
