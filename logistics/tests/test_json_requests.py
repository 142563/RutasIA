import json

from django.test import RequestFactory, SimpleTestCase

from logistics.domain.exceptions import PlanningError
from logistics.presentation.serializers import _parse_json


class JsonRequestTests(SimpleTestCase):
    def test_rejects_non_objects_and_malformed_json(self):
        factory = RequestFactory()
        for body in ("[]", "null", "true", "1", '"texto"', "{", b"\xff"):
            with self.subTest(body=body):
                request = factory.post("/api/", data=body, content_type="application/json")
                with self.assertRaisesMessage(PlanningError, "JSON inválido"):
                    _parse_json(request)

    def test_accepts_objects_and_empty_body(self):
        factory = RequestFactory()
        payload = {"username": "prueba", "nested": [1, 2]}
        request = factory.post("/api/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(_parse_json(request), payload)
        self.assertEqual(_parse_json(factory.post("/api/", data="", content_type="application/json")), {})
