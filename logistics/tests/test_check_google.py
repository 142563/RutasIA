"""check_google: verifica las keys con una consulta mínima y explica los errores."""
from io import StringIO
from unittest import mock

import httpx
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from logistics.routing.google import RoutesClient


def fake_client(response: httpx.Response):
    transport = httpx.MockTransport(lambda request: response)
    return lambda: RoutesClient(api_key="clave-de-prueba", http=httpx.Client(transport=transport))


class CheckGoogleTests(SimpleTestCase):
    def run_command(self, response):
        out = StringIO()
        with mock.patch("logistics.management.commands.check_google.RoutesClient", fake_client(response)):
            call_command("check_google", stdout=out)
        return out.getvalue()

    @override_settings(GOOGLE_MAPS_API_KEY="")
    def test_ok_reports_distance_and_single_element(self):
        output = self.run_command(httpx.Response(200, json=[
            {"distanceMeters": 45200, "duration": "3300s", "staticDuration": "3000s", "condition": "ROUTE_EXISTS"}]))
        self.assertIn("45.2 km", output)
        self.assertIn("50 min", output)
        self.assertIn("1 elemento", output)
        self.assertIn("No configurada", output)

    def test_forbidden_explains_how_to_fix(self):
        out = StringIO()
        response = httpx.Response(403, text="PERMISSION_DENIED: Routes API has not been used in project")
        with mock.patch("logistics.management.commands.check_google.RoutesClient", fake_client(response)):
            with self.assertRaisesMessage(CommandError, "no funciona"):
                call_command("check_google", stdout=out)
        self.assertIn("activa \"Routes API\"", out.getvalue())

    @override_settings(GOOGLE_ROUTES_API_KEY="")
    def test_missing_key(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_google", stdout=out)
        self.assertIn("GOOGLE_ROUTES_API_KEY", out.getvalue())


class SwappedKeysHintTests(SimpleTestCase):
    def test_browser_key_in_server_slot_is_explained(self):
        out = StringIO()
        response = httpx.Response(403, text='{"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}')
        with mock.patch("logistics.management.commands.check_google.RoutesClient", fake_client(response)):
            with self.assertRaises(CommandError):
                call_command("check_google", stdout=out)
        self.assertIn("key del NAVEGADOR", out.getvalue())
