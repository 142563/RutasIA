import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings


class SecuritySettingsTests(SimpleTestCase):
    def load_settings(self, debug, secret):
        with patch.dict(os.environ, {"DEBUG": debug, "SECRET_KEY": secret, "DATABASE_URL": ""}):
            return runpy.run_path(str(Path(__file__).resolve().parents[2] / "rutasia" / "settings.py"))

    def test_production_rejects_missing_short_or_public_secret(self):
        for secret in ("", "cambia-esto", "django-insecure-" + "x" * 60):
            with self.subTest(secret_type="vacía" if not secret else "insegura"):
                with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY privada"):
                    self.load_settings("False", secret)

    def test_production_uses_secure_cookies_https_and_short_hsts(self):
        settings = self.load_settings("False", "clave-exclusiva-de-prueba-" * 3)
        self.assertFalse(settings["DEBUG"])
        for name in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"):
            self.assertTrue(settings[name])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 3600)
        self.assertFalse(settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"])
        self.assertFalse(settings["SECURE_HSTS_PRELOAD"])
        self.assertEqual(settings["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")

    def test_development_keeps_http_available(self):
        settings = self.load_settings("True", "solo-desarrollo")
        self.assertFalse(settings["SECURE_SSL_REDIRECT"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 0)
        self.assertFalse(settings["SESSION_COOKIE_SECURE"])

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=3600,
                       SECURE_HSTS_INCLUDE_SUBDOMAINS=False, SECURE_HSTS_PRELOAD=False,
                       SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_https_proxy_does_not_loop_and_adds_hsts(self):
        middleware = SecurityMiddleware(lambda request: HttpResponse("ok"))
        factory = RequestFactory()
        response = middleware(factory.get("/api/auth/csrf/", HTTP_X_FORWARDED_PROTO="https"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Strict-Transport-Security"], "max-age=3600")
        response = middleware(factory.get("/api/auth/csrf/"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://testserver/api/auth/csrf/")
