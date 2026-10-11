"""Límite de inicio de sesión compartido entre procesos mediante la base de datos."""
from __future__ import annotations

import time
import unicodedata
from datetime import timedelta
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from logistics.models import LoginAttempt

WINDOW = timedelta(minutes=15)
ACCOUNT_LIMIT = 5
IP_LIMIT = 20
LIMIT_MESSAGE = "Demasiados intentos. Espera unos minutos."


class LoginRateLimited(Exception):
    pass


def client_ip(request) -> str:
    """Solo atraviesa proxies explícitamente confiables, desde el socket hacia afuera."""
    try:
        peer = ip_address(request.META.get("REMOTE_ADDR", ""))
    except ValueError:
        return "unknown"
    networks = [ip_network(cidr) for cidr in settings.LOGIN_TRUSTED_PROXY_CIDRS]
    if not any(peer in network for network in networks):
        return str(peer)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if len(forwarded) > 2048:
        return str(peer)
    try:
        chain = [ip_address(value.strip()) for value in forwarded.split(",")]
    except ValueError:
        return str(peer)
    for candidate in reversed(chain):
        peer = candidate
        if not any(peer in network for network in networks):
            break
    return str(peer)


def attempt_key(scope: str, value: str) -> str:
    digest = salted_hmac("enruta.login_limits", value, algorithm="sha256").hexdigest()
    return f"{scope}:{digest}"


def _authenticate_once(request, username: str, password: str):
    normalized = unicodedata.normalize("NFKC", username.strip()).casefold()
    account_key = attempt_key("account", normalized)
    ip_key = attempt_key("ip", client_ip(request))
    # Una IP bloqueada no puede crear filas ilimitadas variando el nombre de cuenta.
    if LoginAttempt.objects.filter(key=ip_key, blocked_until__gt=timezone.now()).exists():
        return None, True
    with transaction.atomic():
        # El UPDATE toma el bloqueo de escritura también en SQLite; PostgreSQL bloquea cada fila.
        for key in sorted((account_key, ip_key)):
            LoginAttempt.objects.filter(key=key).update(touched_at=F("touched_at"))
            LoginAttempt.objects.get_or_create(key=key)
        rows = {row.key: row for row in LoginAttempt.objects.select_for_update().filter(
            key__in=(account_key, ip_key)
        ).order_by("key")}
        now = timezone.now()
        if any(row.blocked_until and row.blocked_until > now for row in rows.values()):
            return None, True
        user = authenticate(request, username=username, password=password)
        blocked = False
        for key, limit in ((account_key, ACCOUNT_LIMIT), (ip_key, IP_LIMIT)):
            row = rows[key]
            row.failures = [stamp for stamp in row.failures if stamp > (now - WINDOW).timestamp()]
            row.blocked_until = None
            if user is not None and key == account_key:
                row.failures = []
            elif user is None:
                row.failures.append(now.timestamp())
                if len(row.failures) >= limit:
                    row.blocked_until = now + WINDOW
                    blocked = True
            row.touched_at = now
            row.save(update_fields=("failures", "blocked_until", "touched_at"))
        return user, blocked


def authenticate_with_limits(request, *, username: str, password: str):
    """No evalúa la contraseña durante un bloqueo; un éxito solo limpia su cuenta."""
    for retry in range(4):
        try:
            user, blocked = _authenticate_once(request, username, password)
            break
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            if retry == 3:
                raise LoginRateLimited(LIMIT_MESSAGE) from exc
            time.sleep(0.02 * 2 ** retry)
    if blocked:
        raise LoginRateLimited(LIMIT_MESSAGE)
    return user
