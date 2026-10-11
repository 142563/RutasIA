import base64
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from logistics.presentation.csp_views import MAX_REPORT_BYTES, api_csp_report
from rutasia.csp import ContentSecurityPolicyMiddleware


class CspHeaderTests(SimpleTestCase):
    def test_headers_on_spa_api_auth_failure_and_missing_endpoint(self):
        for path in ("/", "/pedidos", "/api/config/", "/api/auth/session/", "/api/no-existe/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                policy = response["Content-Security-Policy-Report-Only"]
                self.assertIn("report-uri /api/csp-report/", policy)
                self.assertIn("object-src 'none'", policy)
                self.assertNotIn("Content-Security-Policy", response)
                script = re.search(r"script-src (.*?);", policy).group(1)
                self.assertNotIn("'unsafe-inline'", script)
                self.assertIn("https://*.googleapis.com", script)

    def test_theme_hash_matches_script_in_actual_served_html_and_changes_with_build(self):
        with TemporaryDirectory() as directory:
            dist = Path(directory)
            (dist / "app").mkdir()
            index = dist / "app" / "index.html"
            with override_settings(FRONTEND_DIST=dist):
                for comment in ("primero", "contenido diferente"):
                    script = "\r\n// " + comment + "\r\nlocalStorage.getItem('enruta-theme');\r\n"
                    index.write_bytes(("<script>" + script + "</script><script src='/asset.js'></script><script>alert('otro');</script>").encode())
                    response = Client().get("/")
                    served = re.search(rb"<script>(.*?)</script>", response.content, re.S).group(1)
                    expected = base64.b64encode(hashlib.sha256(served).digest()).decode()
                    policy = response["Content-Security-Policy-Report-Only"]
                    self.assertIn("'sha256-" + expected + "'", policy)
                    other = base64.b64encode(hashlib.sha256(b"alert('otro');").digest()).decode()
                    self.assertNotIn(other, policy)
                    self.assertNotIn(b"\r", served)

    def test_header_without_build_and_on_server_error(self):
        with TemporaryDirectory() as directory, override_settings(FRONTEND_DIST=Path(directory)):
            response = ContentSecurityPolicyMiddleware(lambda request: HttpResponse(status=500))(RequestFactory().get("/api/falla/"))
            self.assertEqual(response.status_code, 500)
            self.assertIn("Content-Security-Policy-Report-Only", response)
            self.assertNotIn("sha256-", response["Content-Security-Policy-Report-Only"])


class CspReportTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def post(self, payload, content_type="application/csp-report"):
        return self.client.post("/api/csp-report/", json.dumps(payload), content_type=content_type)

    def test_anonymous_report_without_csrf_and_logs_only_directive_and_count(self):
        report = {"effective-directive": "script-src-elem", "document-uri": "https://enruta.world/seguimiento/private-token",
                  "blocked-uri": "https://maps.googleapis.com/maps/api/js?key=secret", "script-sample": "private address"}
        with patch("logistics.presentation.csp_views.logger.warning") as log:
            response = self.post({"csp-report": report})
        self.assertEqual(response.status_code, 204)
        log.assert_called_once_with("CSP report directives=%s count=%d", "script-src-elem", 1)
        self.assertNotIn("sessionid", response.cookies)

    def test_modern_reports_and_untrusted_directive_do_not_leak_text(self):
        with patch("logistics.presentation.csp_views.logger.warning") as log:
            response = self.post([
                {"type": "csp-violation", "body": {"effectiveDirective": "img-src"}},
                {"type": "csp-violation", "body": {"effectiveDirective": "SECRET\nforged log"}},
            ], "application/reports+json")
        self.assertEqual(response.status_code, 204)
        log.assert_called_once_with("CSP report directives=%s count=%d", "img-src,unknown", 2)

    def test_rejects_large_body_before_reading_and_checks_stream_limit(self):
        factory = RequestFactory()
        request = factory.post("/api/csp-report/", b"x" * (MAX_REPORT_BYTES + 1), content_type="application/csp-report")
        with patch.object(request, "read", wraps=request.read) as read:
            self.assertEqual(api_csp_report(request).status_code, 413)
            read.assert_not_called()
        request.META["CONTENT_LENGTH"] = "1"
        with patch.object(request, "read", wraps=request.read) as read:
            self.assertEqual(api_csp_report(request).status_code, 413)
            read.assert_called_once_with(MAX_REPORT_BYTES + 1)
        self.assertFalse(hasattr(request, "_body"))

    def test_accepts_exact_limit_and_rejects_malformed_without_logging(self):
        valid = json.dumps({"csp-report": {"effective-directive": "connect-src"}}).encode()
        with patch("logistics.presentation.csp_views.logger.warning"):
            response = self.client.post("/api/csp-report/", valid + b" " * (MAX_REPORT_BYTES - len(valid)), content_type="application/json")
        self.assertEqual(response.status_code, 204)
        invalid = [b"{", b"\xff", b"null", b"[]", b"{}", b'{"csp-report":[]}',
                   b'{"csp-report":{"effective-directive":4}}', b"[" * 2000 + b"]" * 2000]
        with patch("logistics.presentation.csp_views.logger.warning") as log:
            for body in invalid:
                with self.subTest(body=body[:40]):
                    self.assertEqual(self.client.post("/api/csp-report/", body, content_type="application/csp-report").status_code, 400)
            self.assertEqual(self.post([{"type": "csp-violation", "body": {"effectiveDirective": "img-src"}}] * 17).status_code, 400)
        log.assert_not_called()

    def test_method_content_type_and_invalid_length(self):
        self.assertEqual(self.client.get("/api/csp-report/").status_code, 405)
        self.assertEqual(self.client.post("/api/csp-report/", "anything", content_type="text/plain").status_code, 415)
        request = RequestFactory().post("/api/csp-report/", "{}", content_type="application/json")
        for length in ("bad", "-1"):
            request.META["CONTENT_LENGTH"] = length
            self.assertEqual(api_csp_report(request).status_code, 400)
