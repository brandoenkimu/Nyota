import datetime as dt

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts import emails
from accounts.forms import StaffCreateForm
from accounts.models import PLATFORM_ROLES, Attendance, Role
from accounts.staffnames import temp_password
from audit.models import AuditLog
from audit.service import record
from catalog.models import Category
from core.models import HeroSlide
from core.notify import notify
from core.utils import paginate
from orders.models import Coupon, Order, Payout, ShopOrder
from payments.models import Payment
from shops.models import Shop, ShopStatus

from .common import badge, chart, csv_response, dash, form_page, kpi, link, listing, role_required, show, table
from .forms import (CategoryForm, CouponForm, ShopAdminForm, SlideForm, UserAdminForm)
from .seller import handle_shop_order

User = get_user_model()
ADMIN = ('admin',)


# ----------------------------------------------------------------- overview
@role_required(*ADMIN)
def home(request):
    since = timezone.now() - dt.timedelta(days=30)
    live = Order.objects.filter(placed_at__gte=since).exclude(status='cancelled')
    agg = live.aggregate(gmv=Sum('total'), n=Count('id'))
    series = live.annotate(d=TruncDate('placed_at')).values('d').annotate(v=Sum('total'), n=Count('id')).order_by('d')
    roles = User.objects.values('role').annotate(n=Count('id')).order_by('-n')
    statuses = Order.objects.values('status').annotate(n=Count('id'))
    pending_shops = Shop.objects.filter(status=ShopStatus.PENDING)
    kpis = [
        kpi('GMV (30 days)', agg['gmv'] or 0, icon='wallet', money=True), kpi('Orders (30 days)', agg['n'] or 0, icon='box'),
        kpi('Active shops', Shop.objects.filter(status=ShopStatus.ACTIVE).count(), icon='store'),
        kpi('Customers', User.objects.filter(role=Role.CUSTOMER).count(), icon='users'),
        kpi('Shops to approve', pending_shops.count(), icon='alert'),
        kpi('Payout requests', Payout.objects.filter(status='requested').count(), icon='wallet'),
        kpi('Failed payments (7d)', Payment.objects.filter(state='failed', created_at__gte=timezone.now() - dt.timedelta(days=7)).count(), icon='card'),
    ]
    charts = [
        chart('gmv', 'line', 'Daily sales value', [r['d'].strftime('%d %b') for r in series],
              [{'label': 'Sales', 'data': [float(r['v']) for r in series]}], wide=True, money=True),
        chart('roles', 'doughnut', 'Accounts by role', [r['role'].replace('_', ' ') for r in roles],
              [{'label': 'Accounts', 'data': [r['n'] for r in roles]}]),
        chart('st', 'bar', 'Orders by status', [s['status'].replace('_', ' ') for s in statuses],
              [{'label': 'Orders', 'data': [s['n'] for s in statuses]}]),
    ]
    latest = Order.objects.select_related('customer')[:8]
    rows = [{'cells': [link(f'/staff/admin/orders/{o.number}/', o.number), o.customer.display_name, o.total,
                       badge(o.status), badge(o.payment_status)], 'url': f'/staff/admin/orders/{o.number}/'} for o in latest]
    srows = [{'cells': [link(f'/staff/admin/shops/{s.pk}/', s.name), s.owner.display_name, s.city,
                        s.created_at.strftime('%d %b')]} for s in pending_shops[:6]]
    tables = [table('Latest orders', ['Order', 'Customer', 'Total', 'Status', 'Payment'], rows, link_url='/staff/admin/orders/',
                    link_label='All orders'),
              table('Shops waiting for approval', ['Shop', 'Owner', 'City', 'Applied'], srows, 'Nothing waiting.',
                    '/staff/admin/shops/?status=pending', 'Review')]
    return dash(request, 'Administration', kpis, charts, tables, subtitle='Everything happening across Nyota')


# ------------------------------------------------------------ orders/tracking
@role_required(*ADMIN)
def orders(request):
    qs = Order.objects.select_related('customer').prefetch_related('shop_orders__shop')
    q, status, pay = (request.GET.get(k, '').strip() for k in ('q', 'status', 'payment'))
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__email__icontains=q) | Q(customer__last_name__icontains=q)
                       | Q(ship_phone__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if pay:
        qs = qs.filter(payment_status=pay)
    page = paginate(request, qs, 25)
    rows = [{'cells': [link(f'/staff/admin/orders/{o.number}/', o.number), o.placed_at.strftime('%d %b %H:%M'),
                       o.customer.display_name, ', '.join(so.shop.name for so in o.shop_orders.all()), o.total,
                       badge(o.status), badge(o.payment_status)], 'url': f'/staff/admin/orders/{o.number}/'}
            for o in page.object_list]
    filters = [{'name': 'q', 'label': 'Search order, customer, phone', 'type': 'text', 'value': q},
               {'name': 'status', 'label': 'Status', 'type': 'select', 'value': status,
                'options': [('', 'All')] + list(Order._meta.get_field('status').choices)},
               {'name': 'payment', 'label': 'Payment', 'type': 'select', 'value': pay,
                'options': [('', 'All')] + list(Order._meta.get_field('payment_status').choices)}]
    return listing(request, 'Orders and tracking', ['Order', 'Placed', 'Customer', 'Shops', 'Total', 'Status', 'Payment'],
                   rows, page, filters, subtitle='Open an order to follow it from payment to delivery and add tracking updates.')


@role_required(*ADMIN)
def order_detail(request, number):
    from .customer import order_context
    order = get_object_or_404(Order.objects.prefetch_related('payments'), number=number)
    ctx = order_context(order, 'admin')
    ctx['customer'] = order.customer
    return show(request, 'portal/order_detail.html', ctx, f'Order {order.number}')


@role_required(*ADMIN)
def shop_order(request, pk):
    so = get_object_or_404(ShopOrder.objects.select_related('order__customer', 'shop'), pk=pk)
    return handle_shop_order(request, so, 'admin')


# -------------------------------------------------------------------- shops
@role_required(*ADMIN)
def shops(request):
    qs = Shop.objects.select_related('owner').annotate(n=Count('products', distinct=True))
    q, status = request.GET.get('q', '').strip(), request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(owner__email__icontains=q) | Q(city__icontains=q))
    if status:
        qs = qs.filter(status=status)
    page = paginate(request, qs, 25)
    rows = [{'cells': [link(f'/staff/admin/shops/{s.pk}/', s.name), s.owner.display_name, s.city, s.n,
                       f'{s.commission_percent}%', badge(s.status), 'Verified' if s.is_verified else '-'],
             'url': f'/staff/admin/shops/{s.pk}/'} for s in page.object_list]
    filters = [{'name': 'q', 'label': 'Search', 'type': 'text', 'value': q},
               {'name': 'status', 'label': 'Status', 'type': 'select', 'value': status,
                'options': [('', 'All')] + list(ShopStatus.choices)}]
    return listing(request, 'Shops', ['Shop', 'Owner', 'City', 'Products', 'Commission', 'Status', 'Verified'], rows, page,
                   filters)


@role_required(*ADMIN)
def shop_edit(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    form = ShopAdminForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        old = Shop.objects.get(pk=pk).status
        form.save()
        record('shop.admin_updated', target=shop, request=request, status=shop.status, verified=shop.is_verified,
               commission=str(shop.commission_override))
        if old != shop.status and shop.status == ShopStatus.ACTIVE:
            notify(shop.owner, 'Your shop is live!', 'An administrator approved your shop.', '/seller/')
        messages.success(request, 'Shop updated.')
        return redirect('portals:admin_shops')
    return form_page(request, f'Manage {shop.name}', form, 'Save', '/staff/admin/shops/',
                     note=f'Owner: {shop.owner.display_name} ({shop.owner.email}). Leave commission empty for the '
                          f'platform default. Public page: {shop.get_absolute_url()}')


# -------------------------------------------------------------------- users
@role_required(*ADMIN)
def users(request):
    qs = User.objects.all()
    q, role = request.GET.get('q', '').strip(), request.GET.get('role', '')
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(username__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q))
    if role:
        qs = qs.filter(role=role)
    page = paginate(request, qs, 25)
    rows = [{'cells': [link(f'/staff/admin/users/{u.pk}/', u.display_name), u.username, u.email, u.get_role_display(),
                       badge('active' if u.is_active else 'suspended', 'Active' if u.is_active else 'Disabled'),
                       u.date_joined.strftime('%d %b %Y')], 'url': f'/staff/admin/users/{u.pk}/'}
            for u in page.object_list]
    filters = [{'name': 'q', 'label': 'Search', 'type': 'text', 'value': q},
               {'name': 'role', 'label': 'Role', 'type': 'select', 'value': role,
                'options': [('', 'All')] + list(Role.choices)}]
    return listing(request, 'Users', ['Name', 'Username', 'Email', 'Role', 'Access', 'Joined'], rows, page, filters)


@role_required(*ADMIN)
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = UserAdminForm(request.POST or None, instance=target)
    if request.method == 'POST' and form.is_valid():
        if target == request.user and not form.cleaned_data['is_active']:
            messages.error(request, 'You cannot disable your own account.')
        else:
            form.save()
            record('user.admin_updated', target=target, request=request, active=target.is_active)
            messages.success(request, 'User updated.')
            return redirect('portals:admin_users')
    return show(request, 'portal/user_edit.html', {'form': form, 'target': target}, f'{target.display_name}')


@role_required(*ADMIN)
@require_POST
def user_reset(request, pk):
    target = get_object_or_404(User, pk=pk)
    password = temp_password()
    target.set_password(password)
    target.must_change_password = True
    target.save(update_fields=['password', 'must_change_password'])
    record('user.password_reset_by_admin', target=target, request=request)
    return show(request, 'portal/credentials.html', {
        'new_user': target, 'password': password, 'login_url': '/staff/login/', 'back': f'/staff/admin/users/{pk}/',
        'emailed_to': '', 'reset': True}, 'Temporary password')


@role_required(*ADMIN)
def staff(request):
    qs = User.objects.filter(role__in=PLATFORM_ROLES).select_related('staff_profile')
    rows = [{'cells': [u.display_name, u.username, u.email, getattr(getattr(u, 'staff_profile', None), 'job_title', ''),
                       getattr(getattr(u, 'staff_profile', None), 'employee_no', ''),
                       badge('active' if u.is_active else 'suspended', 'Active' if u.is_active else 'Disabled'),
                       u.last_seen.strftime('%d %b %H:%M') if u.last_seen else 'Never'],
             'url': f'/staff/admin/users/{u.pk}/'} for u in qs]
    return listing(request, 'Nyota staff', ['Name', 'Username', 'Company e-mail', 'Position', 'Employee no.', 'Access',
                                            'Last seen'], rows, add=('/staff/admin/staff/new/', 'Add staff member'),
                   subtitle='Identities follow the pattern  first.last.position@' + settings.COMPANY_DOMAIN)


@role_required(*ADMIN)
def staff_new(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user, password = form.save(request.user)
        record('staff.created', target=user, request=request, role=user.role)
        emails.send_staff_welcome(request, user, password)
        return show(request, 'portal/credentials.html', {
            'new_user': user, 'password': password, 'login_url': '/staff/login/', 'back': '/staff/admin/staff/',
            'emailed_to': user.notification_email}, 'Staff member created')
    return form_page(request, 'Add a staff member', form, 'Create account', '/staff/admin/staff/',
                     note='The username and company e-mail are generated from the name and position. '
                          'A temporary password is created and must be changed at first sign-in.')


# --------------------------------------------------------------- simple CRUD
def _crud(request, form_class, instance, title, back, label):
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        record(f'{label}.saved', target=obj, request=request)
        messages.success(request, 'Saved.')
        return redirect(back)
    return form_page(request, title, form, 'Save', back)


@role_required(*ADMIN)
def categories(request):
    rows = [{'cells': [c.name, c.slug, c.parent or '-', c.sort, c.products.count()],
             'url': f'/staff/admin/categories/{c.pk}/'} for c in Category.objects.select_related('parent')]
    return listing(request, 'Categories', ['Name', 'Slug', 'Parent', 'Order', 'Products'], rows,
                   add=('/staff/admin/categories/new/', 'Add category'),
                   subtitle='The slug also selects the generated artwork (for example phones, footwear, kitchen).')


@role_required(*ADMIN)
def category_edit(request, pk=None):
    return _crud(request, CategoryForm, get_object_or_404(Category, pk=pk) if pk else None,
                 'Edit category' if pk else 'New category', '/staff/admin/categories/', 'category')


@role_required(*ADMIN)
def coupons(request):
    rows = [{'cells': [c.code, f'{c.percent}%', c.min_total, c.valid_until or 'No expiry', f'{c.used}/{c.usage_limit or "inf"}',
                       badge('active' if c.active else 'suspended', 'Active' if c.active else 'Off')],
             'url': f'/staff/admin/coupons/{c.pk}/'} for c in Coupon.objects.all()]
    return listing(request, 'Coupons', ['Code', 'Discount', 'Minimum basket', 'Valid until', 'Used', 'State'], rows,
                   add=('/staff/admin/coupons/new/', 'Add coupon'))


@role_required(*ADMIN)
def coupon_edit(request, pk=None):
    return _crud(request, CouponForm, get_object_or_404(Coupon, pk=pk) if pk else None,
                 'Edit coupon' if pk else 'New coupon', '/staff/admin/coupons/', 'coupon')


@role_required(*ADMIN)
def slides(request):
    rows = [{'cells': [s.title, s.kicker, s.cta_url, s.sort, badge('active' if s.active else 'suspended',
                                                                    'Shown' if s.active else 'Hidden')],
             'url': f'/staff/admin/slides/{s.pk}/'} for s in HeroSlide.objects.all()]
    return listing(request, 'Home page slides', ['Title', 'Kicker', 'Link', 'Order', 'State'], rows,
                   add=('/staff/admin/slides/new/', 'Add slide'),
                   subtitle='With no slides defined, Nyota shows four built-in ones.')


@role_required(*ADMIN)
def slide_edit(request, pk=None):
    return _crud(request, SlideForm, get_object_or_404(HeroSlide, pk=pk) if pk else None,
                 'Edit slide' if pk else 'New slide', '/staff/admin/slides/', 'slide')


# ------------------------------------------------------- payouts & payments
@role_required(*ADMIN)
def payouts(request):
    page = paginate(request, Payout.objects.select_related('shop'), 25)
    return show(request, 'portal/admin_payouts.html', {'page': page}, 'Payout requests')


@role_required(*ADMIN)
@require_POST
def payout_action(request, pk):
    p = get_object_or_404(Payout, pk=pk)
    action, ref = request.POST.get('action'), request.POST.get('reference', '').strip()[:60]
    mapping = {'approve': 'approved', 'pay': 'paid', 'reject': 'rejected'}
    if action not in mapping or p.status in ('paid', 'rejected'):
        messages.error(request, 'That payout cannot be changed.')
    else:
        p.status = mapping[action]
        p.processed_at, p.processed_by = timezone.now(), request.user
        if ref:
            p.reference = ref
        p.save()
        record('payout.' + p.status, target=p, request=request, amount=str(p.amount))
        notify(p.shop.owner, f'Payout {p.status}', f'KES {p.amount:,.0f} - {p.reference}', '/seller/payouts/')
        messages.success(request, f'Payout marked {p.status}.')
    return redirect('portals:admin_payouts')


@role_required(*ADMIN)
def payments(request):
    qs = Payment.objects.select_related('order')
    state = request.GET.get('state', '')
    if state:
        qs = qs.filter(state=state)
    page = paginate(request, qs, 30)
    rows = [{'cells': [link(f'/staff/admin/orders/{p.order.number}/', p.order.number), p.method,
                       p.amount, badge(p.state), p.receipt or '-', 'demo' if p.simulated else 'live',
                       p.created_at.strftime('%d %b %H:%M')]} for p in page.object_list]
    filters = [{'name': 'state', 'label': 'State', 'type': 'select', 'value': state,
                'options': [('', 'All')] + list(Payment._meta.get_field('state').choices)}]
    return listing(request, 'Payments', ['Order', 'Method', 'Amount', 'State', 'Receipt', 'Mode', 'When'], rows, page, filters)


# --------------------------------------------------------- attendance, audit
@role_required(*ADMIN)
def attendance(request):
    try:
        day = dt.date.fromisoformat(request.GET.get('date', '')) if request.GET.get('date') else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    people = User.objects.filter(Q(role__in=PLATFORM_ROLES) | Q(role='seller_staff'), is_active=True).select_related(
        'staff_profile')
    records = {a.user_id: a for a in Attendance.objects.filter(date=day)}
    rows = []
    for u in people:
        a = records.get(u.pk)
        rows.append({'cells': [u.display_name, u.get_role_display(),
                               timezone.localtime(a.clock_in).strftime('%H:%M') if a else '-',
                               timezone.localtime(a.clock_out).strftime('%H:%M') if a and a.clock_out else '-',
                               f'{a.hours} h' if a else '-',
                               badge('late') if a and a.late else badge('present', 'On time') if a else badge('failed', 'Absent')]})
    return listing(request, f'Attendance on {day:%d %b %Y}', ['Person', 'Role', 'In', 'Out', 'Hours', 'Status'], rows,
                   filters=[{'name': 'date', 'label': 'Date', 'type': 'date', 'value': day.isoformat()}])


@role_required(*ADMIN)
def audit(request):
    qs = AuditLog.objects.all()
    q, action = request.GET.get('q', '').strip(), request.GET.get('action', '').strip()
    if q:
        qs = qs.filter(Q(actor_label__icontains=q) | Q(target_repr__icontains=q) | Q(ip__icontains=q))
    if action:
        qs = qs.filter(action__startswith=action)
    if request.GET.get('export'):
        return csv_response('audit-log.csv', ['time', 'actor', 'role', 'action', 'target', 'ip', 'detail'],
                            [[a.created_at.isoformat(), a.actor_label, a.role, a.action, a.target_repr, a.ip, a.detail]
                             for a in qs[:5000]])
    page = paginate(request, qs, 40)
    rows = [{'cells': [timezone.localtime(a.created_at).strftime('%d %b %H:%M:%S'), a.actor_label or '-', a.role or '-',
                       a.action, a.target_repr or '-', a.ip or '-', ', '.join(f'{k}={v}' for k, v in a.detail.items())[:80]]}
            for a in page.object_list]
    filters = [{'name': 'q', 'label': 'Search person, target or IP', 'type': 'text', 'value': q},
               {'name': 'action', 'label': 'Action starts with', 'type': 'text', 'value': action}]
    return listing(request, 'Audit log', ['Time', 'Who', 'Role', 'Action', 'Target', 'IP', 'Details'], rows, page, filters,
                   subtitle='Append-only and tamper-evident. Developers can verify the hash chain.',
                   extra_actions=[('Export CSV', '?export=1&' + request.GET.urlencode())])
