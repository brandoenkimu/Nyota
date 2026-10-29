from decimal import Decimal

from django.test import SimpleTestCase

from .models import FLOW, split_commission


class CommissionTests(SimpleTestCase):
    def test_split(self):
        c, e = split_commission(Decimal('1000'), Decimal('8'))
        self.assertEqual((c, e), (Decimal('80.00'), Decimal('920.00')))

    def test_rounding_keeps_total(self):
        c, e = split_commission(Decimal('333.33'), Decimal('7.5'))
        self.assertEqual(c + e, Decimal('333.33'))

    def test_flow_order(self):
        self.assertEqual(FLOW[0], 'pending')
        self.assertEqual(FLOW[-1], 'delivered')
