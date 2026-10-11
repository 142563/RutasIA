"""Núcleo de los avisos por correo: armar, filtrar repetidos, enviar y dejar bitácora.

Cada evento (account.py, customer.py, staff.py) arma `Message`s y llama `dispatch`.
Los disparos desde la lógica de negocio usan `later(...)`: corre después del commit y nunca
rompe ni deshace la operación (una entrega se registra aunque Resend esté caído).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import httpx
from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string

from logistics.domain.notifications import Event
from logistics.models import NotificationLog

from . import transport

logger = logging.getLogger("logistics.application.notifications")

GT_TZ = ZoneInfo("America/Guatemala")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class Message:
    event: Event
    audience: str  # NotificationLog.Audience
    to: str
    subject: str
    html: str
    text: str
    user_id: int | None = None
    order_id: int | None = None
    route_id: int | None = None
    dedupe_key: str = ""
    keep_subject: bool = True  # False en la bienvenida: no se guarda nada que pueda revelar la contraseña


def format_moment(moment) -> str:
    """'10 de octubre, 14:32' en hora de Guatemala."""
    local = moment.astimezone(GT_TZ)
    return f"{local.day} de {MONTHS[local.month - 1]}, {local:%H:%M}"


def format_day(moment) -> str:
    """'sábado 10 de octubre' en hora de Guatemala."""
    local = moment.astimezone(GT_TZ)
    return f"{WEEKDAYS[local.weekday()]} {local.day} de {MONTHS[local.month - 1]}"


def format_clock(moment) -> str:
    return f"{moment.astimezone(GT_TZ):%H:%M}"


def site_url(path: str = "") -> str:
    return f"{settings.SITE_URL.rstrip('/')}/{path.lstrip('/')}"


def render_email(name: str, context: dict) -> tuple[str, str]:
    """HTML y texto de `emails/<name>.html` y `emails/<name>.txt` (las plantillas escapan solas)."""
    context = {"site_url": settings.SITE_URL.rstrip("/"), **context}
    return (render_to_string(f"emails/{name}.html", context).strip(),
            render_to_string(f"emails/{name}.txt", context).strip())


def _log(message: Message, status: str, provider_id: str = "", error: str = "") -> NotificationLog:
    return NotificationLog(
        event=str(message.event), audience=message.audience, recipient=message.to,
        subject=message.subject[:200] if message.keep_subject else "", user_id=message.user_id,
        order_id=message.order_id, route_id=message.route_id, status=status,
        provider_id=provider_id[:80], error=error[:300], dedupe_key=message.dedupe_key[:160],
    )


def _already_sent(message: Message) -> bool:
    return bool(message.dedupe_key) and NotificationLog.objects.filter(
        dedupe_key=message.dedupe_key[:160], status=NotificationLog.Status.SENT).exists()


def dispatch(messages: list[Message]) -> list[str]:
    """Envía los mensajes (en lote si son varios) y devuelve los destinatarios a los que salió."""
    pending = [m for m in messages if m.to and not _already_sent(m)]
    if not pending:
        return []
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY no está configurada: %d correo(s) sin enviar (%s).",
                    len(pending), ", ".join(sorted({str(m.event) for m in pending})))
        NotificationLog.objects.bulk_create(
            [_log(m, NotificationLog.Status.SKIPPED, error="Falta RESEND_API_KEY") for m in pending])
        return []

    logs, sent = [], []
    for start in range(0, len(pending), transport.BATCH_LIMIT):
        chunk = pending[start:start + transport.BATCH_LIMIT]
        try:
            ids = transport.send_batch(chunk) if len(chunk) > 1 else [transport.send_one(chunk[0])]
            results = [(m, i, "") for m, i in zip(chunk, ids)]
        except httpx.HTTPError as exc:
            if len(chunk) == 1:
                results = [(chunk[0], None, str(exc))]
            else:
                # Un lote falla completo si un correo es inválido: se reintenta uno por uno
                logger.warning("Falló el lote de %d correos (%s); se reintenta uno por uno.", len(chunk), exc)
                results = []
                for m in chunk:
                    try:
                        results.append((m, transport.send_one(m), ""))
                    except httpx.HTTPError as one_exc:
                        results.append((m, None, str(one_exc)))
        for message, provider_id, error in results:
            if provider_id is None:
                logger.warning("No se pudo enviar el correo «%s» a %s: %s", message.subject, message.to, error)
                logs.append(_log(message, NotificationLog.Status.FAILED, error=error))
            else:
                logs.append(_log(message, NotificationLog.Status.SENT, provider_id=provider_id))
                sent.append(message.to)
    NotificationLog.objects.bulk_create(logs)
    return sent


def safely(fn, *args, **kwargs) -> list[str]:
    """Corre un evento sin dejar escapar errores: un correo caído nunca afecta la operación."""
    try:
        return fn(*args, **kwargs) or []
    except Exception as exc:  # noqa: BLE001 - cualquier falla (red, datos, plantilla) solo se registra
        logger.warning("No se pudo procesar el aviso %s: %s", getattr(fn, "__name__", fn), exc)
        return []


def later(fn, *args, **kwargs) -> None:
    """Programa el evento para después del commit de la transacción actual (o ya, si no hay)."""
    transaction.on_commit(lambda: safely(fn, *args, **kwargs))
