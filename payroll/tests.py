from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User

from . import services
from .models import JobCategory, PayGrade, PayProfile, PayrollRun, RunStatus


class PayrollMaths(TestCase):
    def test_paye_bands(self):
        self.assertEqual(services.paye(Decimal('20000')), 0)                    # below the relief
        self.assertEqual(round(services.paye(Decimal('50000')), 2), Decimal('7383.35'))

    def test_statutory_is_positive_and_less_than_gross(self):
        p, n, s, h = services.statutory(Decimal('100000'))
        self.assertTrue(0 < p + n + s + h < Decimal('100000'))


class PayrollFlow(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('adm', 'adm@x.com', 'pw-12345-xyz', role=Role.ADMIN)
        self.ceo = User.objects.create_user('ceo', 'ceo@x.com', 'pw-12345-xyz', role=Role.CEO)
        self.dev = User.objects.create_user('dev', 'dev@x.com', 'pw-12345-xyz', role=Role.DEVELOPER)
        g = PayGrade.objects.create(name='Senior', rank=4, base_salary=Decimal('130000'))
        c = JobCategory.objects.create(name='Engineering', allowance_percent=Decimal('15'))
        PayProfile.objects.create(user=self.dev, grade=g, category=c, apply_statutory=False)

    def test_rank_and_category_drive_pay(self):
        f = services.compute(self.dev.pay_profile, 2026, 8)
        self.assertEqual(f['base'], Decimal('130000'))
        self.assertEqual(f['category_allowance'], Decimal('19500'))             # 15% of the rank salary

    def test_preparer_cannot_approve_and_ceo_can(self):
        run = services.create_run(None, 2026, 8, self.admin)
        with self.assertRaises(services.PayrollError):
            services.approve(run, self.admin)
        services.approve(run, self.ceo)
        self.assertEqual(run.status, RunStatus.APPROVED)
        services.mark_paid(run, self.admin, 'BATCH-1')
        self.assertEqual(run.status, RunStatus.PAID)

    def test_no_run_for_unfinished_month(self):
        from django.utils import timezone
        t = timezone.localdate()
        with self.assertRaises(services.PayrollError):
            services.create_run(None, t.year, t.month, self.admin)
