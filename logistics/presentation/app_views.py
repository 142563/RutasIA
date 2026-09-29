"""Sesión y arranque de la aplicación React (SPA).

Django sirve la API y el build de React (frontend/dist). La autenticación es la
sesión de Django con su protección CSRF: el cliente pide la cookie en
/api/auth/csrf/ y envía el token en el header X-CSRFToken.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from logistics.domain.exceptions import PlanningError
from logistics.models import UserProfile
from logistics.presentation.serializers import _error, _ok, _parse_json, role_for


def user_payload(user) -> dict:
    role = role_for(user)
    driver = getattr(user, "driver", None)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "role": role,
        "role_label": UserProfile.Role(role).label,
        "driver_id": driver.id if driver else None,
    }


@ensure_csrf_cookie
@require_GET
def api_csrf(request: HttpRequest):
    return _ok({})


@require_POST
def api_login(request: HttpRequest):
    try:
        payload = _parse_json(request)
    except PlanningError as exc:
        return _error(str(exc))
    user = authenticate(
        request, username=str(payload.get("username", "")).strip(), password=str(payload.get("password", ""))
    )
    if user is None:
        return _error("Usuario o contraseña incorrectos.", 400)
    login(request, user)
    return _ok({"user": user_payload(user)})


@require_POST
def api_logout(request: HttpRequest):
    logout(request)
    return _ok({})


@require_GET
def api_session(request: HttpRequest):
    """Usuario actual; 401 si no hay sesión (la SPA lo usa al arrancar)."""
    if not request.user.is_authenticated:
        return _error("Inicia sesión para continuar.", 401)
    return _ok({"user": user_payload(request.user)})


@require_GET
def api_config(request: HttpRequest):
    """Configuración pública del cliente. La key del navegador está restringida por referrer."""
    return _ok({
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "google_maps_map_id": settings.GOOGLE_MAPS_MAP_ID,
    })


BUILD_MISSING_HTML = """<!doctype html><html lang="es"><meta charset="utf-8">
<title>Aplicación sin compilar</title>
<body style="font-family:system-ui;max-width:560px;margin:80px auto;color:#111113">
<h1 style="font-size:20px">La aplicación React no está compilada</h1>
<p>Para desarrollo: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run dev</code> y abre
<a href="http://localhost:5173">localhost:5173</a>.</p>
<p>Para servirla desde Django: <code>cd frontend &amp;&amp; npm run build</code>.</p>
<p>La interfaz anterior sigue en <a href="/clasico/">/clasico/</a>.</p>
</body></html>"""


@ensure_csrf_cookie
@require_GET
def spa(request: HttpRequest, path: str = ""):
    """index.html del build de React para cualquier ruta del cliente (/pedidos, /laboratorio…)."""
    index = settings.FRONTEND_DIST / "app" / "index.html"
    if not index.exists():
        return HttpResponse(BUILD_MISSING_HTML)
    return HttpResponse(index.read_text(encoding="utf-8"))
