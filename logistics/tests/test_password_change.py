"""A2 (RUT-70): usuarios con correo, contraseña temporal por correo y cambio obligatorio."""
import json
import logging
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from logistics.application.fleet import generate_temp_password
from logistics.domain.notifications import ROLE_SUMMARY
from logistics.models import NotificationLog, UserProfile

POST = "logistics.application.notifications.transport.httpx.post"
PASSWORD = "clave-segura-123"


def ok_response(*args, **kwargs):
    return mock.Mock(raise_for_status=mock.Mock(), json=lambda: {"id": "re_1"})


def make_user(username, role, email=""):
    user = User.objects.create_user(username=username, password=PASSWORD, email=email)
    UserProfile.objects.create(user=user, role=role)
    return user


class TempPasswordTests(TestCase):
    def test_generated_password_is_readable_and_mixed(self):
        for _ in range(200):
            value = generate_temp_password()
            self.assertEqual(len(value), 12)
            self.assertRegex(value, r"[A-Z]")
            self.assertRegex(value, r"[a-z]")
            self.assertRegex(value, r"[0-9]")
            self.assertIsNone(re.search(r"[0O1lI]", value))


@override_settings(RESEND_API_KEY="test", NOTIFY_FROM="enruta <entregas@enruta.world>", SITE_URL="https://enruta.test")
class AccountCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin1", UserProfile.Role.ADMIN, "admin@example.com")

    def setUp(self):
        self.client.force_login(self.admin)

    def create(self, **extra):
        payload = {"username": "nora", "full_name": "Nora Pérez", "role": "dispatcher",
                   "email": "nora@example.com", **extra}
        with mock.patch(POST, side_effect=ok_response) as post, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("api-v2-fleet", args=["users"]), json.dumps(payload),
                                        content_type="application/json")
        return response, post

    def test_create_without_password_generates_temporary_and_emails_it(self):
        response, post = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["user"]["must_change_password"])
        user = User.objects.get(username="nora")
        profile = user.profile
        self.assertTrue(profile.must_change_password)
        remaining = profile.temp_password_expires_at - timezone.now()
        self.assertTrue(timedelta(hours=71, minutes=55) < remaining <= timedelta(hours=72))
        self.assertEqual(post.call_count, 1)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["to"], ["nora@example.com"])
        self.assertEqual(body["subject"], "Bienvenido a enruta")
        # La temporal llega en el cuerpo y es la que quedó guardada
        match = re.search(r"contraseña temporal es: (\S+)", body["text"])
        self.assertTrue(match)
        self.assertTrue(user.check_password(match.group(1)))
        self.assertIn(match.group(1), body["html"])
        self.assertIn("nora", body["text"])
        self.assertIn("Despachador", body["text"])
        for item in ROLE_SUMMARY["dispatcher"]:
            self.assertIn(item, body["text"])
        self.assertIn("https://enruta.test/login", body["html"])

    def test_create_with_password_is_also_temporary_and_emailed(self):
        response, post = self.create(password="contraseña-larga")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="nora")
        self.assertTrue(user.check_password("contraseña-larga"))
        self.assertTrue(user.profile.must_change_password)
        self.assertIn("contraseña-larga", post.call_args.kwargs["json"]["text"])

    def test_temporary_password_never_reaches_log_or_logs(self):
        with self.assertLogs("logistics", level=logging.DEBUG) as captured:
            logging.getLogger("logistics").info("arranque")
            response, post = self.create(password="Secreta-Temporal-77")
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("Secreta-Temporal-77", "\n".join(captured.output))
        entry = NotificationLog.objects.get(event="account_created")
        self.assertEqual(entry.status, NotificationLog.Status.SENT)
        for value in (entry.subject, entry.error, entry.dedupe_key, entry.recipient):
            self.assertNotIn("Secreta-Temporal-77", value)

    def test_without_api_key_nothing_is_sent_but_user_is_created(self):
        with override_settings(RESEND_API_KEY=""):
            response, post = self.create()
        self.assertEqual(response.status_code, 201)
        post.assert_not_called()
        self.assertEqual(NotificationLog.objects.get(event="account_created").status, NotificationLog.Status.SKIPPED)

    def test_resend_access_issues_new_password_and_new_email(self):
        self.create()
        user = User.objects.get(username="nora")
        old_hash = user.password
        UserProfile.objects.filter(user=user).update(must_change_password=False, temp_password_expires_at=None)
        with mock.patch(POST, side_effect=ok_response) as post, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("api-v2-fleet-resend-access", args=[user.id]))
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertNotEqual(user.password, old_hash)
        self.assertTrue(user.profile.must_change_password)
        self.assertIsNotNone(user.profile.temp_password_expires_at)
        self.assertEqual(post.call_count, 1)
        match = re.search(r"contraseña temporal es: (\S+)", post.call_args.kwargs["json"]["text"])
        self.assertTrue(user.check_password(match.group(1)))
        self.assertEqual(NotificationLog.objects.filter(event="account_created").count(), 2)

    def test_resend_access_needs_admin_and_email(self):
        self.create()
        user = User.objects.get(username="nora")
        self.client.force_login(user)
        self.assertEqual(self.client.post(reverse("api-v2-fleet-resend-access", args=[user.id])).status_code, 403)
        self.client.force_login(self.admin)
        User.objects.filter(pk=user.pk).update(email="")
        response = self.client.post(reverse("api-v2-fleet-resend-access", args=[user.id]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(reverse("api-v2-fleet-resend-access", args=[9999])).status_code, 404)


class LoginAndChangeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = make_user("nora", UserProfile.Role.DISPATCHER, "nora@example.com")

    def csrf(self):
        self.client.get(reverse("api-auth-csrf"))
        return self.client.cookies["csrftoken"].value

    def post(self, name, payload):
        return self.client.post(reverse(name), json.dumps(payload), content_type="application/json",
                                HTTP_X_CSRFTOKEN=self.csrf())

    def set_temporary(self, expires):
        UserProfile.objects.filter(user=self.user).update(must_change_password=True, temp_password_expires_at=expires)

    def test_login_with_expired_temporary_password_is_refused(self):
        self.set_temporary(timezone.now() - timedelta(minutes=1))
        response = self.post("api-auth-login", {"username": "nora", "password": PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"],
                         "Tu contraseña temporal venció. Pide al administrador que te reenvíe el acceso.")
        self.assertEqual(self.client.get(reverse("api-auth-session")).status_code, 401)

    def test_login_with_valid_temporary_flags_must_change(self):
        self.set_temporary(timezone.now() + timedelta(hours=10))
        response = self.post("api-auth-login", {"username": "nora", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["must_change_password"])
        self.assertTrue(self.client.get(reverse("api-auth-session")).json()["user"]["must_change_password"])

    def test_normal_login_does_not_flag(self):
        response = self.post("api-auth-login", {"username": "nora", "password": PASSWORD})
        self.assertFalse(response.json()["user"]["must_change_password"])

    def test_password_change_requires_login_and_csrf(self):
        self.assertIn(self.client.post(reverse("api-auth-password"), "{}", content_type="application/json").status_code,
                      (302, 401, 403))
        self.client.login(username="nora", password=PASSWORD)
        response = self.client.post(reverse("api-auth-password"), "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_password_change_rejects_bad_input(self):
        self.set_temporary(timezone.now() + timedelta(hours=10))
        self.client.login(username="nora", password=PASSWORD)
        cases = [
            ({"current_password": "mala", "new_password": "Nueva-clave-2026x"}, "actual"),
            ({"current_password": PASSWORD, "new_password": "corta1A"}, "10"),
            ({"current_password": PASSWORD, "new_password": PASSWORD}, "distinta"),
            ({"current_password": PASSWORD, "new_password": "1234567890"}, ""),
            ({"current_password": PASSWORD, "new_password": "password123"}, ""),
        ]
        for payload, fragment in cases:
            with self.subTest(payload=payload):
                response = self.post("api-auth-password", payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(fragment, response.json()["error"])
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.must_change_password)

    def test_password_change_clears_flags_and_keeps_session(self):
        self.set_temporary(timezone.now() + timedelta(hours=10))
        self.post("api-auth-login", {"username": "nora", "password": PASSWORD})
        response = self.post("api-auth-password", {"current_password": PASSWORD, "new_password": "Nueva-clave-2026x"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nueva-clave-2026x"))
        profile = self.user.profile
        self.assertFalse(profile.must_change_password)
        self.assertIsNone(profile.temp_password_expires_at)
        session = self.client.get(reverse("api-auth-session"))
        self.assertEqual(session.status_code, 200)
        self.assertFalse(session.json()["user"]["must_change_password"])
