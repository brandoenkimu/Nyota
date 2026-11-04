"""Payroll: ranks + job categories + people + monthly runs. The same screens serve two scopes:
Nyota's own staff (administrator prepares, CEO approves) and a shop's team (the owner runs it)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import PLATFORM_ROLES
from audit.service import record
from payroll import services
from payroll.forms import CategoryForm, GradeForm, ProfileForm, RunForm
from payroll.models import JobCategory, PayGrade, PayProfile, PayrollRun, Payslip, RunStatus

from .common import badge, form_page, link, listing, show

User = get_user_model()


def scoped(view):
    """Admin / CEO work on the platform's staff, a seller owner on their own shop's team."""
    @wraps(view)
    def wrapped(request, *a, **kw):
        u = request.user
        if not u.is_authenticated:
            return redirect(f'{reverse("accounts:staff_login")}?next={request.path}')
        if u.role in ('admin', 'ceo'):
            request.pay_shop, request.pay_base = None, '/staff/payroll/'
        elif u.role == 'seller_owner' and u.shop:
            request.pay_shop, request.pay_base = u.shop, '/seller/payroll/'
        else:
            messages.warning(request, 'Payroll is not part of your account.')
            return redirect(u.home_url)
        request.pay_can_prepare = u.role in ('admin', 'seller_owner')
        request.pay_can_approve = u.role in ('ceo', 'seller_owner')
        return view(request, *a, **kw)
    return wrapped


def _people(shop):
    qs = User.objects.filter(is_active=True)
    return qs.filter(shop_membership__shop=shop, shop_membership__active=True) if shop else qs.filter(role__in=PLATFORM_ROLES)


def _mine(request, qs, shop_field='shop'):
    return qs.filter(**{shop_field: request.pay_shop})


@scoped
def home(request):
    shop, base = request.pay_shop, request.pay_base
    runs = PayrollRun.objects.filter(shop=shop)[:24]
    rows = [{'cells': [link(f'{base}run/{r.pk}/', r.label), r.slips.count(), r.total_gross, r.total_net, badge(r.status, r.get_status_display())],
             'url': f'{base}run/{r.pk}/'} for r in runs]
    form = RunForm(request.POST or None) if request.pay_can_prepare else None
    if form is not None and request.method == 'POST' and form.is_valid():
        m = form.cleaned_data['month']
        try:
            run = services.create_run(shop, m.year, m.month, request.user, request)
            messages.success(request, 'Draft payroll created from attendance. Check it, adjust if needed, then approve.')
            return redirect(f'{base}run/{run.pk}/')
        except services.PayrollError as exc:
            messages.error(request, str(exc))
    missing = _people(shop).filter(pay_profile__isnull=True).count()
    return show(request, 'portal/payroll_home.html', {
        'rows': rows, 'form': form, 'base': base, 'missing': missing, 'shop': shop,
        'headers': ['Month', 'People', 'Gross', 'Net pay', 'Status']}, 'Payroll')


@scoped
def run_detail(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk, shop=request.pay_shop)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'recalc' and request.pay_can_prepare:
                services.recalculate(run, request.user, request)
                messages.success(request, 'Recalculated from attendance.')
            elif action == 'approve' and request.pay_can_approve:
                services.approve(run, request.user, request)
                messages.success(request, 'Approved. Staff can now see their payslips.')
            elif action == 'paid' and request.pay_can_prepare:
                services.mark_paid(run, request.user, request.POST.get('reference', ''), request)
                messages.success(request, 'Marked as paid.')
            else:
                messages.error(request, 'You cannot do that with this payroll.')
        except services.PayrollError as exc:
            messages.error(request, str(exc))
        return redirect(f'{request.pay_base}run/{pk}/')
    slips = run.slips.select_related('user')
    return show(request, 'portal/payroll_run.html', {'run': run, 'slips': slips, 'base': request.pay_base,
                                                     'can_prepare': request.pay_can_prepare, 'can_approve': request.pay_can_approve},
                f'Payroll: {run.label}')


@scoped
def slip_detail(request, pk):
    slip = get_object_or_404(Payslip.objects.select_related('run', 'user'), pk=pk, run__shop=request.pay_shop)
    if request.method == 'POST' and request.pay_can_prepare:
        try:
            from decimal import Decimal, InvalidOperation
            services.adjust(slip, Decimal(request.POST.get('adjustment') or '0'), request.POST.get('note', ''), request.user, request)
            messages.success(request, 'Adjustment saved.')
        except (services.PayrollError, InvalidOperation) as exc:
            messages.error(request, str(exc) or 'Enter a valid amount.')
        return redirect(f'{request.pay_base}slip/{pk}/')
    return show(request, 'portal/payslip.html', {'slip': slip, 'editable': request.pay_can_prepare and slip.run.status == RunStatus.DRAFT,
                                                 'base': request.pay_base}, f'Payslip: {slip.user.display_name}')


# ---- ranks, categories, people
@scoped
def grades(request):
    qs = PayGrade.objects.filter(shop=request.pay_shop)
    rows = [{'cells': [g.rank, g.name, g.base_salary, g.profiles.count()], 'url': f'{request.pay_base}grades/{g.pk}/'} for g in qs]
    return listing(request, 'Ranks and base salaries', ['Rank', 'Name', 'Monthly base', 'People'], rows,
                   add=(f'{request.pay_base}grades/new/', 'New rank') if request.pay_can_prepare else None,
                   empty='No ranks yet.', subtitle='A higher rank number means more senior.')


@scoped
def grade_edit(request, pk=None):
    if not request.pay_can_prepare:
        return redirect(f'{request.pay_base}grades/')
    obj = get_object_or_404(PayGrade, pk=pk, shop=request.pay_shop) if pk else None
    form = GradeForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        g = form.save(commit=False); g.shop = request.pay_shop; g.save()
        record('payroll.grade_saved', target=g, request=request, base=str(g.base_salary))
        return redirect(f'{request.pay_base}grades/')
    return form_page(request, 'Rank', form, 'Save', f'{request.pay_base}grades/')


@scoped
def categories(request):
    qs = JobCategory.objects.filter(shop=request.pay_shop)
    rows = [{'cells': [c.name, f'+{c.allowance_percent}%', c.description, c.profiles.count()], 'url': f'{request.pay_base}categories/{c.pk}/'} for c in qs]
    return listing(request, 'Job categories', ['Category', 'Allowance', 'About', 'People'], rows,
                   add=(f'{request.pay_base}categories/new/', 'New category') if request.pay_can_prepare else None,
                   empty='No categories yet.', subtitle='The kind of work someone does adds a percentage on top of their rank salary.')


@scoped
def category_edit(request, pk=None):
    if not request.pay_can_prepare:
        return redirect(f'{request.pay_base}categories/')
    obj = get_object_or_404(JobCategory, pk=pk, shop=request.pay_shop) if pk else None
    form = CategoryForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False); c.shop = request.pay_shop; c.save()
        record('payroll.category_saved', target=c, request=request, pct=str(c.allowance_percent))
        return redirect(f'{request.pay_base}categories/')
    return form_page(request, 'Job category', form, 'Save', f'{request.pay_base}categories/')


@scoped
def people(request):
    rows = []
    for u in _people(request.pay_shop).select_related('pay_profile__grade', 'pay_profile__category'):
        p = getattr(u, 'pay_profile', None)
        rows.append({'cells': [u.display_name, u.get_role_display() if not request.pay_shop else (u.shop_membership.get_role_display()),
                               p.grade.name if p else 'not set', p.category.name if p else '-',
                               p.get_employment_type_display() if p else '-'], 'url': f'{request.pay_base}people/{u.pk}/'})
    return listing(request, 'Pay profiles', ['Person', 'Position', 'Rank', 'Category', 'Type'], rows,
                   empty='No staff yet.', subtitle='Open a person to set their rank, category and how they are paid.')


@scoped
def person_edit(request, user_pk):
    person = get_object_or_404(_people(request.pay_shop), pk=user_pk)
    if not request.pay_can_prepare:
        messages.warning(request, 'Only the person who prepares payroll can change pay profiles.')
        return redirect(f'{request.pay_base}people/')
    obj = getattr(person, 'pay_profile', None)
    form = ProfileForm(request.POST or None, instance=obj, shop=request.pay_shop)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False); p.user = person; p.save()
        record('payroll.profile_saved', target=person, request=request, grade=p.grade.name, category=p.category.name)
        messages.success(request, 'Pay profile saved.')
        return redirect(f'{request.pay_base}people/')
    return form_page(request, f'Pay profile: {person.display_name}', form, 'Save', f'{request.pay_base}people/',
                     note='Create ranks and categories first if the lists are empty.')


# ---- a staff member's own payslips (platform staff and shop staff)
def my_payslips(request):
    u = request.user
    if not u.is_authenticated:
        return redirect(f'{reverse("accounts:staff_login")}?next={request.path}')
    if u.role == 'customer':
        return redirect(u.home_url)
    qs = Payslip.objects.filter(user=u, run__status__in=[RunStatus.APPROVED, RunStatus.PAID]).select_related('run')
    rows = [{'cells': [link(f'/me/payslips/{s.pk}/', s.run.label), s.grade_name, s.gross, s.total_deductions, s.net,
                       badge(s.run.status, s.run.get_status_display())], 'url': f'/me/payslips/{s.pk}/'} for s in qs]
    return listing(request, 'My payslips', ['Month', 'Rank', 'Gross', 'Deductions', 'Net pay', 'Status'], rows,
                   empty='No payslips yet.')


def my_payslip(request, pk):
    u = request.user
    if not u.is_authenticated:
        return redirect(f'{reverse("accounts:staff_login")}?next={request.path}')
    slip = get_object_or_404(Payslip.objects.select_related('run', 'user'), pk=pk, user=u,
                             run__status__in=[RunStatus.APPROVED, RunStatus.PAID])
    return show(request, 'portal/payslip.html', {'slip': slip, 'editable': False, 'base': '/me/payslips/'}, f'Payslip {slip.run.label}')
