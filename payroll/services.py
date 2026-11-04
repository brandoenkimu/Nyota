"""Pay = rank (base salary) + job-category allowance + fixed allowance + overtime +- adjustment,
minus absence, lateness and statutory deductions. All rates come from settings.PAYROLL so they are easy to update."""
import calendar
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Attendance
from audit.service import record

from .models import EmploymentType, PayProfile, PayrollRun, Payslip, RunStatus

D = Decimal


class PayrollError(Exception):
    pass


def cfg():
    return settings.PAYROLL


def money(x):
    return D(x).quantize(D('1'), rounding=ROUND_HALF_UP)


def working_days(year, month, until=None):
    n = 0
    for d in range(1, calendar.monthrange(year, month)[1] + 1):
        day = dt.date(year, month, d)
        if until and day > until:
            break
        if day.weekday() < cfg()['WORK_DAYS_PER_WEEK']:
            n += 1
    return n


def paye(taxable):
    """Progressive monthly income tax from the configured bands, minus personal relief."""
    tax, lower = D('0'), D('0')
    for upper, rate in cfg()['PAYE_BANDS']:
        top = D(str(upper)) if upper is not None else None
        if taxable > lower:
            part = (min(taxable, top) if top is not None else taxable) - lower
            tax += part * D(str(rate))
        if top is None or taxable <= top:
            break
        lower = top
    return max(D('0'), tax - D(str(cfg()['PERSONAL_RELIEF'])))


def statutory(gross):
    c = cfg()
    nssf = min(gross, D(str(c['NSSF_UPPER_LIMIT']))) * D(str(c['NSSF_RATE']))
    shif = max(gross * D(str(c['SHIF_RATE'])), D(str(c['SHIF_MIN'])))
    housing = gross * D(str(c['HOUSING_LEVY_RATE']))
    taxable = gross - nssf - shif - housing
    return money(paye(taxable)), money(nssf), money(shif), money(housing)


def compute(profile, year, month):
    """Return a dict of Payslip fields for this person and month."""
    c = cfg()
    last_day = dt.date(year, month, calendar.monthrange(year, month)[1])
    expected = working_days(year, month)
    rows = list(Attendance.objects.filter(user=profile.user, date__year=year, date__month=month))
    present = len([r for r in rows if r.clock_out or r.clock_in])
    late = len([r for r in rows if r.late])
    hours = sum((D(str(r.hours)) for r in rows if r.clock_out), D('0'))
    ot_hours = sum((max(D('0'), D(str(r.hours)) - D(str(c['DAY_HOURS']))) for r in rows if r.clock_out), D('0'))

    if profile.employment_type == EmploymentType.FULL_TIME:
        base = D(profile.grade.base_salary)
    else:
        base = hours * D(profile.hourly_rate)
    allowance = base * D(profile.category.allowance_percent) / D('100')
    fixed = D(profile.fixed_allowance) if profile.employment_type == EmploymentType.FULL_TIME else D('0')
    overtime = D('0')
    if profile.employment_type == EmploymentType.FULL_TIME and expected:
        hourly = D(profile.grade.base_salary) / (D(expected) * D(str(c['DAY_HOURS'])))
        overtime = ot_hours * hourly * D(str(c['OVERTIME_MULTIPLIER']))
    absence = D('0')
    if profile.employment_type == EmploymentType.FULL_TIME and c['DEDUCT_ABSENCE'] and expected:
        absent = max(0, expected - present)
        absence = (base + allowance) / D(expected) * D(absent)
    late_ded = D(str(c['LATE_PENALTY'])) * D(late)
    gross = base + allowance + fixed + overtime
    p = n = s = h = D('0')
    if profile.apply_statutory:
        p, n, s, h = statutory(max(D('0'), gross - absence - late_ded))
    net = gross - absence - late_ded - p - n - s - h
    return dict(grade_name=profile.grade.name, category_name=profile.category.name,
                employment_type=profile.employment_type, days_expected=expected, days_present=present, days_late=late,
                hours=hours.quantize(D('0.01')), overtime_hours=ot_hours.quantize(D('0.01')), base=money(base),
                category_allowance=money(allowance), fixed_allowance=money(fixed), overtime_pay=money(overtime),
                gross=money(gross), absence_deduction=money(absence), late_deduction=money(late_ded), paye=p, nssf=n,
                shif=s, housing_levy=h, net=money(net), pay_phone=profile.pay_phone)


def refresh_slip(slip):
    """Re-compute one slip but keep the manual adjustment."""
    profile = slip.user.pay_profile
    f = compute(profile, slip.run.year, slip.run.month)
    adj = slip.adjustment
    if adj:
        f['gross'] = f['gross'] + adj
        p = n = s = h = D('0')
        if profile.apply_statutory:
            p, n, s, h = statutory(max(D('0'), f['gross'] - f['absence_deduction'] - f['late_deduction']))
        f.update(paye=p, nssf=n, shif=s, housing_levy=h)
        f['net'] = f['gross'] - f['absence_deduction'] - f['late_deduction'] - p - n - s - h
    for k, v in f.items():
        setattr(slip, k, v)
    slip.save()
    return slip


def profiles_for(shop):
    qs = PayProfile.objects.filter(active=True, user__is_active=True).select_related('user', 'grade', 'category')
    return qs.filter(grade__shop=shop) if shop else qs.filter(grade__shop__isnull=True)


@transaction.atomic
def create_run(shop, year, month, by, request=None):
    today = timezone.localdate()
    if (year, month) >= (today.year, today.month):
        raise PayrollError('Payroll can only be run for a month that has finished.')
    if PayrollRun.objects.filter(shop=shop, year=year, month=month).exists():
        raise PayrollError('There is already a payroll run for that month.')
    profiles = list(profiles_for(shop))
    if not profiles:
        raise PayrollError('Nobody has a pay profile yet. Set up ranks, categories and people first.')
    run = PayrollRun.objects.create(shop=shop, year=year, month=month, created_by=by)
    for p in profiles:
        Payslip.objects.create(run=run, user=p.user, **compute(p, year, month))
    record('payroll.run_created', target=run, request=request, actor=by, people=len(profiles))
    return run


@transaction.atomic
def recalculate(run, by, request=None):
    if run.status != RunStatus.DRAFT:
        raise PayrollError('Only a draft run can be recalculated.')
    for s in run.slips.select_related('user__pay_profile__grade', 'user__pay_profile__category'):
        refresh_slip(s)
    record('payroll.recalculated', target=run, request=request, actor=by)


@transaction.atomic
def adjust(slip, amount, note, by, request=None):
    if slip.run.status != RunStatus.DRAFT:
        raise PayrollError('This run is no longer a draft.')
    slip.adjustment, slip.adjustment_note = D(amount), note[:160]
    refresh_slip(slip)
    record('payroll.adjusted', target=slip.run, request=request, actor=by, user=slip.user.username, amount=str(amount), note=note[:100])


@transaction.atomic
def approve(run, by, request=None):
    if run.status != RunStatus.DRAFT:
        raise PayrollError('This run is not waiting for approval.')
    if run.created_by_id == by.pk and run.shop_id is None:
        raise PayrollError('The person who prepared the payroll cannot also approve it.')
    run.status, run.approved_by, run.approved_at = RunStatus.APPROVED, by, timezone.now()
    run.save()
    from core.notify import notify
    for s in run.slips.select_related('user'):
        notify(s.user, f'Your {run.label} payslip is ready', f'Net pay {s.net}', '/me/payslips/')
    record('payroll.approved', target=run, request=request, actor=by, net=str(run.total_net))


@transaction.atomic
def mark_paid(run, by, reference, request=None):
    if run.status != RunStatus.APPROVED:
        raise PayrollError('Approve the run first.')
    run.status, run.paid_by, run.paid_at, run.payment_reference = RunStatus.PAID, by, timezone.now(), reference[:80]
    run.save()
    record('payroll.paid', target=run, request=request, actor=by, reference=reference[:80], net=str(run.total_net))
