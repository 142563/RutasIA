from decimal import Decimal
from unittest import mock

from django.test import TestCase

from logistics.models import Order


class UniqueCodeTests(TestCase):
    def test_order_code_retries_when_suffix_collides(self):
        # Los dos primeros sufijos chocan; el tercero es libre
        with mock.patch("logistics.models._random_suffix", side_effect=["1234", "1234", "5678"]):
            first = Order.objects.create(recipient="A", address="x", weight_kg=Decimal("1"))
            second = Order.objects.create(recipient="B", address="y", weight_kg=Decimal("1"))
        self.assertTrue(first.code.endswith("-1234"))
        self.assertTrue(second.code.endswith("-5678"))
