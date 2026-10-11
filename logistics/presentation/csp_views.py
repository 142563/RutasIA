"""Recibe telemetría anónima de CSP sin guardar datos personales ni URLs."""
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)
MAX_REPORT_BYTES = 16 * 1024
MAX_REPORTS = 16
DIRECTIVES = frozenset({
    "default-src", "script-src", "script-src-elem", "script-src-attr", "style-src", "style-src-elem",
    "style-src-attr", "img-src", "font-src", "connect-src", "frame-src", "frame-ancestors", "worker-src",
    "object-src", "base-uri", "form-action", "media-src", "manifest-src", "child-src",
})


def _error(message, status):
    return JsonResponse({"ok": False, "error": message}, status=status)


@csrf_exempt
@require_POST
def api_csp_report(request):
    # Los navegadores no pueden adjuntar el token CSRF a sus reportes automáticos.
    if request.content_type not in {"application/csp-report", "application/reports+json", "application/json"}:
        return _error("Tipo de reporte no compatible.", 415)
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return _error("Tamaño de reporte inválido.", 400)
    if length < 0:
        return _error("Tamaño de reporte inválido.", 400)
    if length > MAX_REPORT_BYTES:
        return _error("El reporte es demasiado grande.", 413)
    # No usa request.body: lee como máximo el límite más un byte, incluso sin longitud fiable.
    raw = request.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        return _error("El reporte es demasiado grande.", 413)
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            reports = [payload.get("csp-report")]
        elif isinstance(payload, list) and 0 < len(payload) <= MAX_REPORTS:
            if any(not isinstance(item, dict) or item.get("type") != "csp-violation" for item in payload):
                raise ValueError
            reports = [item.get("body") for item in payload]
        else:
            raise ValueError
        directives = []
        for report in reports:
            if not isinstance(report, dict):
                raise ValueError
            value = report.get("effective-directive", report.get("effectiveDirective", report.get("violated-directive")))
            if not isinstance(value, str) or not value.strip():
                raise ValueError
            directive = value.split()[0]
            directives.append(directive if directive in DIRECTIVES else "unknown")
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _error("Reporte CSP inválido.", 400)
    # El cuerpo puede contener claves, direcciones, tokens y texto de scripts: nunca se registra.
    logger.warning("CSP report directives=%s count=%d", ",".join(sorted(set(directives))), len(reports))
    return HttpResponse(status=204)
