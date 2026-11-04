from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class JobCategory(models.Model):
    """The kind of work: pays a percentage allowance on top of the rank's base salary."""
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.CASCADE, related_name='job_categories')
    name = models.CharField(max_length=60)
    allowance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'),
                                            help_text='Extra pay for this kind of work, as % of base salary.')
    description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'job categories'

    def __str__(self):
        return f'{self.name} (+{self.allowance_percent}%)'


class PayGrade(models.Model):
    """The rank: sets the monthly base salary."""
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.CASCADE, related_name='pay_grades')
    name = models.CharField(max_length=60)
    rank = models.PositiveSmallIntegerField(default=1, help_text='Higher number = more senior.')
    base_salary = models.DecimalField('Monthly base salary', max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['rank']

    def __str__(self):
        return f'{self.name} (rank {self.rank})'


class EmploymentType(models.TextChoices):
    FULL_TIME = 'full_time', 'Full time (monthly salary)'
    PART_TIME = 'part_time', 'Part time (paid per hour)'
    CONTRACT = 'contract', 'Contract (paid per hour)'


class PayProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pay_profile')
    grade = models.ForeignKey(PayGrade, on_delete=models.PROTECT, related_name='profiles')
    category = models.ForeignKey(JobCategory, on_delete=models.PROTECT, related_name='profiles')
    employment_type = models.CharField(max_length=10, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'),
                                      help_text='Only for part time and contract staff.')
    fixed_allowance = models.DecimalField('Fixed monthly allowance (transport, airtime...)', max_digits=10,
                                          decimal_places=2, default=Decimal('0'))
    apply_statutory = models.BooleanField('Deduct PAYE, NSSF, SHIF and housing levy', default=True)
    pay_phone = models.CharField('M-Pesa number to pay', max_length=20, blank=True)
    bank_details = models.CharField(max_length=160, blank=True)
    kra_pin = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.user} - {self.grade.name} / {self.category.name}'

    @property
    def shop(self):
        return self.grade.shop


class RunStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft (being prepared)'
    APPROVED = 'approved', 'Approved'
    PAID = 'paid', 'Paid'


class PayrollRun(models.Model):
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.CASCADE, related_name='payroll_runs')
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=RunStatus.choices, default=RunStatus.DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-year', '-month', '-id']

    def __str__(self):
        return f'Payroll {self.year}-{self.month:02d}' + (f' ({self.shop})' if self.shop_id else '')

    @property
    def label(self):
        import calendar
        return f'{calendar.month_name[self.month]} {self.year}'

    @property
    def total_net(self):
        return sum((s.net for s in self.slips.all()), Decimal('0'))

    @property
    def total_gross(self):
        return sum((s.gross for s in self.slips.all()), Decimal('0'))


class Payslip(models.Model):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='slips')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payslips')
    # snapshot of how the pay was worked out, so later grade changes never rewrite history
    grade_name = models.CharField(max_length=60)
    category_name = models.CharField(max_length=60)
    employment_type = models.CharField(max_length=10, choices=EmploymentType.choices)
    days_expected = models.PositiveSmallIntegerField(default=0)
    days_present = models.PositiveSmallIntegerField(default=0)
    days_late = models.PositiveSmallIntegerField(default=0)
    hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    overtime_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    base = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    category_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    fixed_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    adjustment = models.DecimalField('Manual adjustment (+ bonus / - deduction)', max_digits=12, decimal_places=2, default=Decimal('0'))
    adjustment_note = models.CharField(max_length=160, blank=True)
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    absence_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    late_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    paye = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    nssf = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    shif = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    housing_levy = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    pay_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = [('run', 'user')]
        ordering = ['user__first_name', 'user__last_name']

    @property
    def total_deductions(self):
        return self.absence_deduction + self.late_deduction + self.paye + self.nssf + self.shif + self.housing_levy
