"""Límites compartidos de login, confianza del proxy y limpieza de contadores."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from logistics.application.login_limits import (
    LIMIT_MESSAGE, LoginRateLimited, attempt_key, authenticate_with_limits, client_ip,
)
from logistics.models import LoginAttempt


@override_settings(LOGIN_TRUSTED_PROXY_CIDRS=[], PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LoginLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user("despachador", password="clave-segura-123")

    def api(self, username="despachador", password="incorrecta", **headers):
        return self.client.post(reverse("api-auth-login"), json.dumps({
            "username": username, "password": password,
        }), content_type="application/json", REMOTE_ADDR="203.0.113.5", **headers)

    def test_account_limit_is_generic_and_blocks_correct_password(self):
        for username in ("despachador", "no-existe"):
            with self.subTest(username=username):
                LoginAttempt.objects.all().delete()
                for _ in range(4):
                    self.assertEqual(self.api(username).status_code, 400)
                self.assertEqual(self.api(username).json(), {"ok": False, "error": LIMIT_MESSAGE})
                response = self.api(username, "clave-segura-123")
                self.assertEqual(response.status_code, 429)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_clears_account_but_not_ip(self):
        for _ in range(3):
            self.api()
        self.assertEqual(self.api(password="clave-segura-123").status_code, 200)
        self.assertEqual(LoginAttempt.objects.get(key=attempt_key("account", "despachador")).failures, [])
        self.assertEqual(len(LoginAttempt.objects.get(key=attempt_key("ip", "203.0.113.5")).failures), 3)
        for _ in range(4):
            self.assertEqual(self.api().status_code, 400)

    def test_block_expires_without_extending_on_rejected_requests(self):
        start = timezone.now()
        with patch("logistics.application.login_limits.timezone.now", return_value=start):
            for _ in range(5):
                self.api()
        with patch("logistics.application.login_limits.timezone.now", return_value=start + timedelta(minutes=14)):
            self.assertEqual(self.api(password="clave-segura-123").status_code, 429)
        with patch("logistics.application.login_limits.timezone.now", return_value=start + timedelta(minutes=15)):
            self.assertEqual(self.api(password="clave-segura-123").status_code, 200)

    def test_old_failures_leave_the_rolling_window(self):
        start = timezone.now()
        with patch("logistics.application.login_limits.timezone.now", return_value=start):
            for _ in range(4):
                self.api()
        with patch("logistics.application.login_limits.timezone.now", return_value=start + timedelta(minutes=15)):
            self.assertEqual(self.api().status_code, 400)
            row = LoginAttempt.objects.get(key=attempt_key("account", "despachador"))
            self.assertEqual(len(row.failures), 1)

    def test_ip_limit_combines_accounts_and_ignores_spoofed_headers(self):
        for number in range(19):
            self.assertEqual(self.api(f"inexistente-{number}", HTTP_X_FORWARDED_FOR=f"198.51.100.{number}").status_code, 400)
        self.assertEqual(self.api("otra-cuenta").status_code, 429)
        self.assertEqual(self.api(password="clave-segura-123").status_code, 429)

    def test_normalized_account_combines_case_and_whitespace(self):
        for name in ("despachador", " DESPACHADOR ", "Despachador", "despachador"):
            self.assertEqual(self.api(name).status_code, 400)
        self.assertEqual(self.api("DESPACHADOR").status_code, 429)
        self.assertEqual(LoginAttempt.objects.filter(key__startswith="account:").count(), 1)
        self.assertNotIn("despachador", LoginAttempt.objects.first().key)

    def test_blocked_ip_cannot_create_more_account_rows(self):
        LoginAttempt.objects.create(key=attempt_key("ip", "203.0.113.5"),
                                    blocked_until=timezone.now() + timedelta(minutes=15))
        for number in range(10):
            self.assertEqual(self.api(f"otra-{number}").status_code, 429)
        self.assertEqual(LoginAttempt.objects.count(), 1)

    def test_html_and_api_share_counters_and_html_returns_429(self):
        for _ in range(4):
            self.api()
        response = self.client.post(reverse("login"), {"username": "despachador", "password": "incorrecta"},
                                    REMOTE_ADDR="203.0.113.5")
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, LIMIT_MESSAGE, status_code=429)
        self.assertEqual(self.api(password="clave-segura-123").status_code, 429)

    def test_html_success_keeps_redirect_and_clears_account(self):
        self.api()
        response = self.client.post(reverse("login"), {"username": "despachador", "password": "clave-segura-123"},
                                    REMOTE_ADDR="203.0.113.5")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.assertEqual(LoginAttempt.objects.get(key=attempt_key("account", "despachador")).failures, [])

    def test_csrf_rejection_does_not_write_a_counter(self):
        client = Client(enforce_csrf_checks=True)
        for path, data, content_type in (
            (reverse("api-auth-login"), '{"username":"despachador","password":"incorrecta"}', "application/json"),
            (reverse("login"), "username=despachador&password=incorrecta", "application/x-www-form-urlencoded"),
        ):
            self.assertEqual(client.post(path, data, content_type=content_type).status_code, 403)
        self.assertFalse(LoginAttempt.objects.exists())

    def test_cleanup_only_deletes_old_inactive_rows(self):
        now = timezone.now()
        LoginAttempt.objects.create(key="old", touched_at=now - timedelta(days=2))
        LoginAttempt.objects.create(key="recent", touched_at=now)
        LoginAttempt.objects.create(key="blocked", touched_at=now - timedelta(days=2), blocked_until=now + timedelta(minutes=1))
        output = StringIO()
        call_command("clean_login_attempts", stdout=output)
        self.assertEqual(set(LoginAttempt.objects.values_list("key", flat=True)), {"recent", "blocked"})
        self.assertIn("1", output.getvalue())


class ClientIpTests(TestCase):
    def request(self, peer, forwarded):
        return RequestFactory().post("/", REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=forwarded)

    @override_settings(LOGIN_TRUSTED_PROXY_CIDRS=["10.20.0.0/16", "192.0.2.0/24"])
    def test_first_untrusted_from_socket_ignores_attacker_prefix(self):
        request = self.request("10.20.0.5", "198.51.100.99, 203.0.113.7, 192.0.2.4")
        self.assertEqual(client_ip(request), "203.0.113.7")

    @override_settings(LOGIN_TRUSTED_PROXY_CIDRS=["10.20.0.0/16"])
    def test_direct_peer_does_not_trust_forwarded_ip(self):
        self.assertEqual(client_ip(self.request("203.0.113.7", "198.51.100.99")), "203.0.113.7")
        self.assertEqual(client_ip(self.request("10.20.0.5", "invalid")), "10.20.0.5")

    @override_settings(LOGIN_TRUSTED_PROXY_CIDRS=["2001:db8:1::/64"])
    def test_ipv6_and_absent_peer(self):
        self.assertEqual(client_ip(self.request("2001:db8:1::2", "2001:db8:2::3")), "2001:db8:2::3")
        self.assertEqual(client_ip(self.request("", "203.0.113.5")), "unknown")


@override_settings(LOGIN_TRUSTED_PROXY_CIDRS=[])
class ConcurrentLoginTests(TransactionTestCase):
    def test_two_connections_do_not_lose_failures_and_share_the_block(self):
        barrier = threading.Barrier(2)

        def fail():
            close_old_connections()
            try:
                request = RequestFactory().post("/", REMOTE_ADDR="203.0.113.7")
                barrier.wait(timeout=5)
                return authenticate_with_limits(request, username="missing", password="incorrecta")
            finally:
                close_old_connections()

        with patch("logistics.application.login_limits.authenticate", return_value=None):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: fail(), range(2)))
            self.assertEqual(results, [None, None])
            row = LoginAttempt.objects.get(key=attempt_key("account", "missing"))
            self.assertEqual(len(row.failures), 2)
            request = RequestFactory().post("/", REMOTE_ADDR="203.0.113.7")
            for _ in range(2):
                authenticate_with_limits(request, username="missing", password="incorrecta")
            with self.assertRaises(LoginRateLimited):
                authenticate_with_limits(request, username="missing", password="incorrecta")
            with self.assertRaises(LoginRateLimited):
                authenticate_with_limits(request, username="missing", password="correcta")
