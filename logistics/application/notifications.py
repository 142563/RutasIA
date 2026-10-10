"""Correos de entrega con Resend (https://resend.com/docs/api-reference/emails/send-email).

Se envía un correo al cliente (si el pedido tiene correo) y otro al despachador que creó la
ruta (si su usuario tiene correo). Sin RESEND_API_KEY no se sale a internet: solo se registra.
Nada de aquí puede romper ni retrasar la entrega: update_stop lo llama con on_commit y
notify_delivery_safe atrapa cualquier error.
"""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

import httpx
from django.conf import settings
from django.utils.html import escape

from logistics.models import RouteStop

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 8
GT_TZ = ZoneInfo("America/Guatemala")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def format_moment(moment) -> str:
    """'10 de octubre, 14:32' en hora de Guatemala."""
    local = moment.astimezone(GT_TZ)
    return f"{local.day} de {MONTHS[local.month - 1]}, {local:%H:%M}"


def _html(title: str, lines: list[str], link: tuple[str, str] | None = None) -> str:
    """Tabla de una columna con estilos en línea (los clientes de correo ignoran el CSS externo)."""
    paragraphs = "".join(
        f'<p style="margin:0 0 12px;font-size:15px;line-height:1.5;color:#111113">{escape(line)}</p>' for line in lines
    )
    button = ""
    if link:
        url, label = link
        button = (f'<p style="margin:16px 0 0"><a href="{escape(url)}" style="color:#2563eb;'
                  f'font-size:15px;text-decoration:underline">{escape(label)}</a></p>')
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f6f7">'
        '<tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:520px;background:#ffffff;border:1px solid #e4e4e7;border-radius:8px">'
        '<tr><td style="padding:24px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">'
        f'<h1 style="margin:0 0 16px;font-size:18px;font-weight:600;color:#111113">{escape(title)}</h1>'
        f"{paragraphs}{button}"
        '<p style="margin:24px 0 0;font-size:13px;color:#6b6b73">enruta</p>'
        "</td></tr></table></td></tr></table>"
    )


def _build_messages(stop: RouteStop) -> list[dict]:
    order, route = stop.order, stop.route
    driver_name = route.driver.name if route.driver else "el conductor"
    when = format_moment(stop.delivered_at)
    recipient = order.recipient or "cliente"
    messages = []

    if order.recipient_email:
        subject = f"Tu pedido {order.code} fue entregado"
        lines = [
            f"Hola {recipient},",
            f"Tu pedido {order.code} fue entregado el {when} en {order.address}.",
            f"Lo entregó {driver_name}.",
        ]
        messages.append({
            "to": order.recipient_email, "subject": subject,
            "html": _html(subject, lines), "text": "\n\n".join(lines + ["enruta"]),
        })

    dispatcher_email = route.created_by.email if route.created_by else ""
    if dispatcher_email:
        total = route.stops.count()
        done = route.stops.filter(status=RouteStop.Status.DELIVERED).count()
        url = f"{settings.SITE_URL.rstrip('/')}/rutas/{route.id}"
        subject = f"Entregado: {order.code} · {recipient}"
        lines = [
            f"El pedido {order.code} fue entregado a {recipient} el {when}.",
            f"Conductor: {driver_name}.",
            f"Ruta {route.code}: {done} de {total} paradas.",
        ]
        messages.append({
            "to": dispatcher_email, "subject": subject,
            "html": _html(subject, lines, (url, "Ver la ruta")),
            "text": "\n\n".join(lines + [f"Ver la ruta: {url}", "enruta"]),
        })
    return messages


def notify_delivery(stop_id: int) -> list[str]:
    """Envía los correos de una entrega y devuelve los destinatarios a los que se envió."""
    stop = (
        RouteStop.objects.select_related("order", "route__driver", "route__created_by").filter(pk=stop_id).first()
    )
    if stop is None or stop.status != RouteStop.Status.DELIVERED or stop.delivered_at is None:
        return []
    messages = _build_messages(stop)
    if not messages:
        return []
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY no está configurada: no se envían %d correo(s) de la entrega %s.",
                    len(messages), stop.order.code)
        return []

    sent = []
    for message in messages:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.NOTIFY_FROM, "to": [message["to"]], "subject": message["subject"],
                  "html": message["html"], "text": message["text"]},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        sent.append(message["to"])
    return sent


def notify_delivery_safe(stop_id: int) -> list[str]:
    """Igual que notify_delivery pero nunca lanza: un correo caído no debe afectar la entrega."""
    try:
        return notify_delivery(stop_id)
    except Exception as exc:  # noqa: BLE001 - cualquier falla (red, 4xx/5xx, datos) solo se registra
        logger.warning("No se pudo enviar el correo de la entrega (parada %s): %s", stop_id, exc)
        return []
