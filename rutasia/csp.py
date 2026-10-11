"""CSP de observación: no bloquea recursos ni sustituye la protección contra XSS."""
import base64
import hashlib
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings


class _InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.collecting = False
        self.parts = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.collecting = not any(name == "src" for name, _ in attrs)
            self.parts = []

    def handle_data(self, data):
        if self.collecting:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.collecting:
            self.scripts.append("".join(self.parts))
            self.collecting = False


@lru_cache(maxsize=4)
def _theme_hashes(path, modified, size):
    # Igual que spa: read_text normaliza los saltos de línea antes de servir HTML.
    parser = _InlineScripts()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    return tuple(
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii") + "'"
        for script in parser.scripts if "enruta-theme" in script
    )


def report_only_policy():
    index = settings.FRONTEND_DIST / "app" / "index.html"
    try:
        stat = index.stat()
        hashes = _theme_hashes(str(index), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        hashes = ()
    # Lista de Google basada en su guía CSP. Inline solo en estilos (React/Maps).
    return "; ".join([
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self' " + " ".join(hashes) + " 'unsafe-eval' https://*.googleapis.com https://*.gstatic.com https://*.google.com https://*.ggpht.com https://*.googleusercontent.com blob:",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "img-src 'self' https://*.googleapis.com https://*.gstatic.com https://*.google.com https://*.googleusercontent.com data: blob:",
        "font-src 'self' https://fonts.gstatic.com data:",
        "connect-src 'self' https://*.googleapis.com https://*.gstatic.com https://*.google.com data: blob:",
        "frame-src https://*.google.com",
        "worker-src 'self' blob:",
        "report-uri /api/csp-report/",
    ])


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy-Report-Only"] = report_only_policy()
        return response
