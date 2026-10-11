"""Bienvenida al crear una cuenta (A2, RUT-70): usuario, rol, qué correos recibirá y contraseña temporal.

La contraseña temporal solo viaja en el cuerpo del correo; nunca se guarda en la bitácora ni en logs.
"""
from __future__ import annotations

from django.contrib.auth.models import User

from logistics.domain.notifications import ROLE_SUMMARY, Event
from logistics.models import NotificationLog, UserProfile

from . import recipients
from .core import Message, dispatch, format_moment, render_email, site_url


def notify_account_created(user_id: int, temp_password: str) -> list[str]:
    """Bienvenida con la contraseña temporal. Un reenvío de acceso usa otro vencimiento, así que otra llave."""
    user = User.objects.select_related("profile").filter(pk=user_id).first()
    if user is None or not temp_password:
        return []
    profile = getattr(user, "profile", None)
    if profile is None:
        return []
    messages = []
    for target in recipients.staff_recipients(Event.ACCOUNT_CREATED, user=user):
        expires = profile.temp_password_expires_at
        subject = "Bienvenido a enruta"
        html, text = render_email("account_created", {
            "subject": subject, "name": user.get_full_name() or user.username, "username": user.username,
            "role_label": UserProfile.Role(profile.role).label, "summary": ROLE_SUMMARY.get(profile.role, []),
            "temp_password": temp_password, "expires": format_moment(expires) if expires else "",
            "login_url": site_url("login"),
        })
        stamp = expires.isoformat() if expires else "sin-vencimiento"
        messages.append(Message(
            event=Event.ACCOUNT_CREATED, audience=NotificationLog.Audience.STAFF, to=target.email,
            subject=subject, html=html, text=text, user_id=target.id,
            dedupe_key=f"{Event.ACCOUNT_CREATED}:user:{target.id}:{stamp}",
        ))
    return dispatch(messages)
