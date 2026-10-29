import datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image

from accounts import emails
from accounts.forms import StaffCreateForm
from accounts.models import Attendance
from analytics import etl, queries
from audit.service import record
from catalog.models import Product, ProductImage, Review
from core.utils import paginate
from orders.forms import TrackingUpdateForm
from orders.models import Payout, ShopOrder, ShopOrderStatus
from orders.services import OrderError, advance_shop_order, cancel_shop_order
from shops.models import ShopMember

from .common import (badge, chart, csv_response, dash, form_page, kpi, link, listing, role_required, show, table)
from .forms import PayoutRequestForm, ProductForm, ReplyForm, ShopProfileForm

SELLER = ('seller_owner', 'seller_staff')


def _shop(request):
    return request.user.shop


def _payable(qs):
    """Sellers only see (and fulfil) orders that are paid or pay-on-delivery. An order whose online
    payment is pending, failed or abandoned stays hidden from them until the customer pays."""
    return qs.filter(Q(order__payment_method='cod') | Q(order__payment_status__in=['paid', 'refunded']))


# ----------------------------------------------------------------- overview
@role_required(*SELLER)
def home(request):
    shop = _shop(request)
    if shop is None:
        messages.warning(request, 'Your shop is not available.')
        return redirect('core:home')
    since = timezone.now() - dt.timedelta(days=30)
    live = _payable(ShopOrder.objects.filter(shop=shop, created_at__gte=since)).exclude(status=ShopOrderStatus.CANCELLED)
    agg = live.aggregate(rev=Sum('subtotal'), disc=Sum('discount'), earn=Sum('seller_earnings'), n=Count('id'))
    revenue = (agg['rev'] or 0) - (agg['disc'] or 0)
    pending = _payable(ShopOrder.objects.filter(shop=shop)).filter(status__in=[ShopOrderStatus.PENDING, ShopOrderStatus.CONFIRMED,
                                                              ShopOrderStatus.PACKED]).count()
    low = Product.objects.filter(shop=shop, is_active=True, stock__lte=5).count()
    series = (live.annotate(d=TruncDate('created_at')).values('d').annotate(v=Sum('subtotal')).order_by('d'))
    kpis = [kpi('Revenue (30 days)', revenue, icon='wallet', money=True), kpi('Orders (30 days)', agg['n'] or 0, icon='box'),
            kpi('To fulfil', pending, hint='pending, confirmed or packed', icon='truck'),
            kpi('Low stock', low, hint='5 or fewer left', icon='alert')]
    charts = [chart('rev', 'line', 'Daily sales, last 30 days', [r['d'].strftime('%d %b') for r in series],
                    [{'label': 'Sales', 'data': [float(r['v']) for r in series]}], wide=True, money=True)]
    recent = _payable(ShopOrder.objects.filter(shop=shop)).select_related('order__customer').order_by('-created_at')[:8]
    rows = [{'cells': [link(f'/seller/orders/{so.pk}/', so.order.number), so.order.customer.display_name,
                       so.total, badge(so.status), badge(so.order.payment_status)],
             'url': f'/seller/orders/{so.pk}/'} for so in recent]
    notes = []
    if shop.status != 'active':
        notes.append(('warn', 'Your shop is awaiting approval, so customers cannot see it yet. Set it up while you wait.'))
    if not shop.has_location:
        notes.append(('info', 'Add your shop location so customers can find you on the map (Shop profile).'))
    return dash(request, f'{shop.name}', kpis, charts,
                [table('Latest orders', ['Order', 'Customer', 'Total', 'Status', 'Payment'], rows,
                       'No orders yet. Share your shop link to get started.', '/seller/orders/', 'All orders')],
                actions=[('View my public shop', shop.get_absolute_url())], notes=notes,
                subtitle='Your shop at a glance')


# ------------------------------------------------------------------- orders
@role_required(*SELLER, shop_perm='orders')
def orders(request):
    shop = _shop(request)
    qs = _payable(ShopOrder.objects.filter(shop=shop)).select_related('order__customer')
    status, q = request.GET.get('status', ''), request.GET.get('q', '').strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(order__number__icontains=q) | Q(order__customer__first_name__icontains=q)
                       | Q(order__customer__last_name__icontains=q))
    page = paginate(request, qs, 20)
    rows = [{'cells': [link(f'/seller/orders/{so.pk}/', so.order.number), so.created_at.strftime('%d %b %H:%M'),
                       so.order.customer.display_name, so.total, badge(so.status), badge(so.order.payment_status)],
             'url': f'/seller/orders/{so.pk}/'} for so in page.object_list]
    filters = [{'name': 'q', 'label': 'Search', 'type': 'text', 'value': q},
               {'name': 'status', 'label': 'Status', 'type': 'select', 'value': status,
                'options': [('', 'All')] + list(ShopOrderStatus.choices)}]
    return listing(request, 'Orders', ['Order', 'Placed', 'Customer', 'Total', 'Status', 'Payment'], rows, page, filters,
                   empty='No orders yet.')


@role_required(*SELLER, shop_perm='orders')
def order_detail(request, pk):
    so = get_object_or_404(_payable(ShopOrder.objects.select_related('order__customer', 'shop')), pk=pk, shop=_shop(request))
    return handle_shop_order(request, so, 'seller')


def handle_shop_order(request, so, viewer):
    """Shared by the seller and administrator order pages: show it, and apply tracking updates."""
    from .customer import order_context
    initial = {'status': so.next_status() or so.status, 'courier': so.courier, 'tracking_number': so.tracking_number,
               'expected_delivery': so.expected_delivery}
    form = TrackingUpdateForm(request.POST or None, initial=initial)
    if request.method == 'POST' and not so.is_closed and form.is_valid():
        d = form.cleaned_data
        try:
            advance_shop_order(so, request.user, d['status'], d['title'], d['detail'], d['location_label'],
                               d['lat'], d['lng'], d['courier'], d['tracking_number'], d['expected_delivery'],
                               d['occurred_at'], request)
            messages.success(request, 'Tracking updated. The customer has been notified.')
        except OrderError as exc:
            messages.error(request, str(exc))
        return redirect(request.path)
    ctx = order_context(so.order, viewer)
    ctx.update(so=so, form=form, parts=[p for p in ctx['parts'] if p['so'].pk == so.pk], viewer=viewer,
               customer=so.order.customer)
    return show(request, 'portal/shop_order.html', ctx, f'Order {so.order.number} - {so.shop.name}')


@role_required(*SELLER, shop_perm='orders')
@require_POST
def order_cancel(request, pk):
    so = get_object_or_404(ShopOrder, pk=pk, shop=_shop(request))
    try:
        cancel_shop_order(so, request.user, request.POST.get('reason', 'Cancelled by the seller')[:200], request)
        messages.success(request, 'Order cancelled and stock restored.')
    except OrderError as exc:
        messages.error(request, str(exc))
    return redirect('portals:seller_order_detail', pk=pk)


# ----------------------------------------------------------------- products
@role_required(*SELLER, shop_perm='products')
def products(request):
    shop = _shop(request)
    qs = Product.objects.filter(shop=shop).select_related('category')
    q, flt = request.GET.get('q', '').strip(), request.GET.get('show', '')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(brand__icontains=q))
    if flt == 'low':
        qs = qs.filter(stock__lte=5, is_active=True)
    elif flt == 'inactive':
        qs = qs.filter(is_active=False)
    page = paginate(request, qs, 20)
    rows = [{'cells': [link(f'/seller/products/{p.pk}/edit/', p.name), p.category.name, p.price,
                       (badge('failed', 'Out of stock') if p.stock == 0 else
                        badge('pending', f'{p.stock} left') if p.low_stock else p.stock),
                       p.sold, badge('active' if p.is_active else 'suspended', 'Live' if p.is_active else 'Hidden')],
             'url': f'/seller/products/{p.pk}/edit/'} for p in page.object_list]
    filters = [{'name': 'q', 'label': 'Search', 'type': 'text', 'value': q},
               {'name': 'show', 'label': 'Show', 'type': 'select', 'value': flt,
                'options': [('', 'All'), ('low', 'Low stock'), ('inactive', 'Hidden')]}]
    return listing(request, 'Products', ['Product', 'Category', 'Price', 'Stock', 'Sold', 'Visibility'], rows, page,
                   filters, add=('/seller/products/new/', 'Add product'), empty='No products yet. Add your first one!')


def _save_gallery(request, product):
    count = product.gallery.count()
    for f in request.FILES.getlist('gallery')[:6]:
        if count >= 8 or f.size > 5 * 1024 * 1024:
            continue
        try:
            Image.open(f).verify()
            f.seek(0)
        except Exception:
            messages.warning(request, f'"{f.name}" is not a valid image and was skipped.')
            continue
        ProductImage.objects.create(product=product, image=f, alt=product.name, sort=count)
        count += 1


@role_required(*SELLER, shop_perm='products')
def product_new(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.shop = _shop(request)
        p.save()
        _save_gallery(request, p)
        record('product.created', target=p, request=request)
        messages.success(request, 'Product added.')
        return redirect('portals:seller_products')
    return show(request, 'portal/product_form.html', {'form': form, 'product': None}, 'New product')


@role_required(*SELLER, shop_perm='products')
def product_edit(request, pk):
    p = get_object_or_404(Product, pk=pk, shop=_shop(request))
    form = ProductForm(request.POST or None, request.FILES or None, instance=p)
    if request.method == 'POST' and form.is_valid():
        form.save()
        _save_gallery(request, p)
        record('product.updated', target=p, request=request)
        messages.success(request, 'Product updated.')
        return redirect('portals:seller_products')
    return show(request, 'portal/product_form.html', {'form': form, 'product': p, 'gallery': p.gallery.all()},
                f'Edit {p.name}')


@role_required(*SELLER, shop_perm='products')
@require_POST
def product_toggle(request, pk):
    p = get_object_or_404(Product, pk=pk, shop=_shop(request))
    p.is_active = not p.is_active
    p.save(update_fields=['is_active'])
    record('product.visibility', target=p, request=request, active=p.is_active)
    return redirect(request.META.get('HTTP_REFERER') or 'portals:seller_products')


@role_required(*SELLER, shop_perm='products')
@require_POST
def product_delete_image(request, pk):
    img = get_object_or_404(ProductImage, pk=pk, product__shop=_shop(request))
    product_id = img.product_id
    img.delete()
    return redirect('portals:seller_product_edit', pk=product_id)


# ------------------------------------------------------------------ reviews
@role_required(*SELLER, shop_perm='reviews')
def reviews(request):
    shop = _shop(request)
    qs = Review.objects.filter(product__shop=shop).select_related('user', 'product')
    page = paginate(request, qs, 15)
    return show(request, 'portal/seller_reviews.html', {'page': page, 'reply_form': ReplyForm()}, 'Customer reviews')


@role_required(*SELLER, shop_perm='reviews')
@require_POST
def review_reply(request, pk):
    review = get_object_or_404(Review, pk=pk, product__shop=_shop(request))
    form = ReplyForm(request.POST)
    if form.is_valid():
        review.seller_reply = form.cleaned_data['reply']
        review.replied_at = timezone.now()
        review.save(update_fields=['seller_reply', 'replied_at'])
        messages.success(request, 'Reply posted.')
    return redirect('portals:seller_reviews')


# ---------------------------------------------------------------- analytics
@role_required(*SELLER, shop_perm='analytics')
def analytics_view(request):
    shop = _shop(request)
    k = queries.kpis(shop.pk, 30)
    series = queries.daily_series(shop.pk, 60)
    if not series:
        return show(request, 'portal/empty_analytics.html', {'can_refresh': True}, 'Analytics')
    fc = etl.latest('forecast', shop.pk)
    abc = etl.latest('abc', shop.pk).get('rows', [])
    basket = etl.latest('basket', shop.pk).get('rules', [])
    sent = etl.latest('sentiment', shop.pk)
    kpis = [kpi('Revenue (30 days)', k['revenue'], k['revenue_growth'], 'vs previous 30 days', 'wallet', True),
            kpi('Orders', k['orders'], k['orders_growth'], 'vs previous 30 days', 'box'),
            kpi('Average order', k['aov'], icon='chart', money=True), kpi('Customers', k['customers'], icon='users')]
    if k['gross_profit'] is not None:
        kpis.append(kpi('Gross profit', k['gross_profit'], hint='sales minus your product costs', icon='wallet', money=True))
    charts = [
        chart('daily', 'line', 'Daily revenue', [s['date'][5:] for s in series],
              [{'label': 'Revenue', 'data': [s['revenue'] for s in series]}], wide=True, money=True),
        chart('cats', 'doughnut', 'Revenue by category', [c['cat'] for c in queries.by_category(shop.pk)],
              [{'label': 'Revenue', 'data': [float(c['rev']) for c in queries.by_category(shop.pk)]}], money=True),
        chart('wd', 'bar', 'Best days of the week', [d['day'] for d in queries.weekday_pattern(shop.pk)],
              [{'label': 'Revenue', 'data': [d['revenue'] for d in queries.weekday_pattern(shop.pk)]}], money=True),
    ]
    if fc.get('forecast'):
        labels = fc['dates'][-30:] + fc['forecast_dates']
        actual = fc['values'][-30:] + [None] * len(fc['forecast'])
        pred = [None] * (len(fc['values'][-30:]) - 1) + [fc['values'][-1]] + fc['forecast']
        charts.append(chart('fc', 'line', 'Forecast: next 14 days', [d[5:] for d in labels],
                            [{'label': 'Actual', 'data': actual}, {'label': 'Forecast', 'data': pred}], wide=True,
                            money=True))
    tables = [
        table('Top products', ['Product', 'Revenue', 'Units'],
              [{'cells': [t['name'], t['rev'], t['units']]} for t in queries.top_products(shop.pk)]),
        table('Product classes (ABC)', ['Product', 'Revenue', 'Share', 'Class'],
              [{'cells': [r['name'], r['revenue'], f"{r['share'] * 100:.1f}%", r['abc']]} for r in abc[:12]]),
        table('Bought together', ['If a customer buys', 'They also buy', 'Confidence', 'Lift'],
              [{'cells': [b['a_name'], b['b_name'], f"{b['confidence'] * 100:.0f}%", f"{b['lift']:.1f}x"]}
               for b in basket[:8]], 'Not enough multi-item orders yet.'),
    ]
    notes = []
    if sent:
        notes.append(('info', f"Review sentiment: {sent['label']} (average {sent['average']:+.2f} from {sent['reviews']} reviews)."))
    if fc.get('anomalies'):
        a = fc['anomalies'][-1]
        notes.append(('warn', f"Unusual sales day spotted: {a['date']} (KES {a['value']:,.0f})."))
    return dash(request, 'Shop analytics', kpis, charts, tables, notes=notes,
                actions=[('Refresh numbers', '/seller/analytics/refresh/', 'post')],
                subtitle='Built from the Nyota data warehouse')


@role_required(*SELLER, shop_perm='analytics')
@require_POST
def analytics_refresh(request):
    if cache.add('etl:lock', 1, 120):
        try:
            etl.run_etl()
            messages.success(request, 'Analytics refreshed.')
        except Exception:
            messages.error(request, 'Could not refresh analytics right now.')
    else:
        messages.info(request, 'Analytics were refreshed a moment ago. Please wait a minute.')
    return redirect('portals:seller_analytics')


# ------------------------------------------------------------------ payouts
def available_balance(shop):
    earned = (ShopOrder.objects.filter(shop=shop, status=ShopOrderStatus.DELIVERED, order__payment_status='paid')
              .aggregate(s=Sum('seller_earnings'))['s'] or Decimal('0'))
    taken = (Payout.objects.filter(shop=shop).exclude(status='rejected').aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    return earned - taken, earned


@role_required(*SELLER, shop_perm='payouts')
def payouts(request):
    shop = _shop(request)
    available, earned = available_balance(shop)
    form = PayoutRequestForm(request.POST or None, available=available,
                             initial={'destination': shop.phone, 'method': 'M-Pesa'})
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.shop = shop
        p.save()
        record('payout.requested', target=p, request=request, amount=str(p.amount))
        messages.success(request, 'Payout requested. The Nyota team will process it shortly.')
        return redirect('portals:seller_payouts')
    return show(request, 'portal/seller_payouts.html', {
        'available': available, 'earned': earned, 'form': form, 'history': Payout.objects.filter(shop=shop)[:20],
        'commission': shop.commission_percent}, 'Payouts')


# --------------------------------------------------------------------- team
@role_required(*SELLER, shop_perm='staff')
def staff(request):
    shop = _shop(request)
    rows = []
    for m in ShopMember.objects.filter(shop=shop).select_related('user__staff_profile'):
        u = m.user
        rows.append({'cells': [u.display_name, u.username, u.email, m.get_role_display(),
                               badge('active' if m.active else 'suspended', 'Active' if m.active else 'Disabled'),
                               u.last_seen.strftime('%d %b %H:%M') if u.last_seen else 'Never'],
                     'url': None})
    return listing(request, 'Team', ['Name', 'Username', 'Company e-mail', 'Position', 'Access', 'Last seen'], rows,
                   add=('/seller/team/new/', 'Add team member'),
                   empty='You have no team members yet. Add cashiers, inventory clerks and more.',
                   subtitle='Staff sign in at the seller door with the username or company e-mail below.',
                   extra_actions=[])


@role_required(*SELLER, shop_perm='staff')
def staff_new(request):
    shop = _shop(request)
    form = StaffCreateForm(request.POST or None, shop=shop)
    if request.method == 'POST' and form.is_valid():
        user, password = form.save(request.user)
        record('staff.created', target=user, request=request, shop=shop.slug)
        emails.send_staff_welcome(request, user, password, shop)
        return show(request, 'portal/credentials.html', {
            'new_user': user, 'password': password, 'login_url': '/seller/login/', 'back': '/seller/team/',
            'emailed_to': user.notification_email}, 'Team member created')
    return show(request, 'portal/form.html', {
        'form': form, 'submit': 'Create account', 'cancel': '/seller/team/',
        'note': f'Their username and company e-mail are generated from their name and position, '
                f'for example  jane.doe.cashier@{form.preview_domain()}', 'subtitle': ''}, 'Add team member')


@role_required(*SELLER, shop_perm='staff')
@require_POST
def staff_toggle(request, pk):
    m = get_object_or_404(ShopMember, pk=pk, shop=_shop(request))
    m.active = not m.active
    m.save(update_fields=['active'])
    m.user.is_active = m.active
    m.user.save(update_fields=['is_active'])
    record('staff.access_changed', target=m.user, request=request, active=m.active)
    return redirect('portals:seller_staff')


# --------------------------------------------------------------- attendance
@role_required(*SELLER, shop_perm='attendance')
def attendance(request):
    shop = _shop(request)
    day = request.GET.get('date')
    try:
        day = dt.date.fromisoformat(day) if day else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    people = [shop.owner] + [m.user for m in shop.members.select_related('user').filter(active=True)]
    records = {a.user_id: a for a in Attendance.objects.filter(date=day, user__in=people)}
    rows = []
    for u in people:
        a = records.get(u.pk)
        rows.append({'cells': [u.display_name, 'Owner' if u == shop.owner else u.staff_profile.job_title
                               if hasattr(u, 'staff_profile') else '',
                               timezone.localtime(a.clock_in).strftime('%H:%M') if a else '-',
                               timezone.localtime(a.clock_out).strftime('%H:%M') if a and a.clock_out else '-',
                               f'{a.hours} h' if a else '-',
                               badge('late') if a and a.late else badge('present', 'On time') if a else badge('failed', 'Absent')]})
    month_start = day.replace(day=1)
    summary = (Attendance.objects.filter(user__in=people, date__gte=month_start, date__lte=day)
               .values('user__first_name', 'user__last_name').annotate(days=Count('id'), late=Count('id', filter=Q(late=True))))
    srows = [{'cells': [f"{s['user__first_name']} {s['user__last_name']}", s['days'], s['late']]} for s in summary]
    resp = listing(request, f'Attendance on {day:%d %b %Y}', ['Person', 'Position', 'In', 'Out', 'Hours', 'Status'], rows,
                   filters=[{'name': 'date', 'label': 'Date', 'type': 'date', 'value': day.isoformat()}],
                   subtitle='Staff clock in from the button in their own header.')
    return resp


# ------------------------------------------------------------------ profile
@role_required(*SELLER, shop_perm='profile')
def shop_profile(request):
    shop = _shop(request)
    form = ShopProfileForm(request.POST or None, request.FILES or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        record('shop.profile_updated', target=shop, request=request)
        messages.success(request, 'Your shop page was updated.')
        return redirect('portals:seller_profile')
    return show(request, 'portal/shop_profile.html', {'form': form, 'shop': shop}, 'Shop profile')
