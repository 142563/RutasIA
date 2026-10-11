"""Envío con la API HTTP de Resend (https://resend.com/docs/api-reference/emails).

Un correo: POST /emails. Varios: POST /emails/batch (hasta 100 por llamada), así "Ruta iniciada"
con 30 clientes es una sola solicitud y no 30. Aquí no hay lógica de negocio ni base de datos.
"""
from __future__ import annotations

import httpx
from django.conf import settings

RESEND_URL = "https://api.resend.com/emails"
RESEND_BATCH_URL = "https://api.resend.com/emails/batch"
TIMEOUT_SECONDS = 8
BATCH_LIMIT = 100


def _payload(message) -> dict:
    return {"from": settings.NOTIFY_FROM, "to": [message.to], "subject": message.subject,
            "html": message.html, "text": message.text}


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}


def send_one(message) -> str:
    """Envía un correo y devuelve su id en Resend. Lanza httpx.HTTPError si falla."""
    response = httpx.post(RESEND_URL, headers=_headers(), json=_payload(message), timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return str(response.json().get("id", ""))


def send_batch(messages: list) -> list[str]:
    """Envía hasta BATCH_LIMIT correos en una llamada; ids en el mismo orden. Falla completo o nada."""
    response = httpx.post(RESEND_BATCH_URL, headers=_headers(), json=[_payload(m) for m in messages],
                          timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json().get("data") or []
    return [str(item.get("id", "")) for item in data] + [""] * (len(messages) - len(data))
