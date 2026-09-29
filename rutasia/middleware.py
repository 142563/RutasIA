from django.conf import settings
from django.http import JsonResponse


class ApiLoginRequiredMiddleware:
    """En /api/, cambia la redirección al login (302) por un 401 en JSON.

    login_required redirige a la página de login, lo que sirve para HTML pero no
    para la aplicación React, que necesita saber que la sesión expiró.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.path.startswith("/api/")
            and response.status_code == 302
            and response.get("Location", "").startswith(settings.LOGIN_URL)
        ):
            return JsonResponse({"ok": False, "error": "Inicia sesión para continuar."}, status=401)
        return response
