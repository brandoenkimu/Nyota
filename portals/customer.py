import json

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.forms import AddressForm, ProfileForm
from accounts.models import Address
from catalog.models import Product, Wishlist
from core.models import Notification
from core.utils import paginate
from orders.models import FLOW, Order, OrderItem, ShopOrder, ShopOrderStatus
from orders.services import OrderError, cancel_shop_order
from shops.models import ShopStatus

from .common import dash, form_page, kpi, link, listing, role_required, show, badge, table

CUSTOMER = ('customer',)


def order_context(order, viewer='customer'):
    """Everything the order/tracking page needs: parts, timelines, and map points."""
    parts = []
    points = []
    for so in order.shop_orders.select_related('shop').prefetch_related('events', 'items'):
        steps = []
        reached = {e.status: e for e in so.events.all()}
        for key in FLOW:
            ev = reached.get(key)
            steps.append({'key': key, 'label': dict(ShopOrderStatus.choices)[key], 'done': so.flow_index >= FLOW.index(key)
                          and so.status != ShopOrderStatus.CANCELLED, 'at': ev.occurred_at if ev else None})
        parts.append({'so': so, 'steps': steps, 'pct': round(max(0, so.flow_index) / (len(FLOW) - 1) * 92), 'events': list(so.events.all()), 'items': list(so.items.all())})
        if so.shop.has_location:
            points.append({'lat': float(so.shop.lat), 'lng': float(so.shop.lng), 'label': f'{so.shop.name} (seller)',
                           'kind': 'shop'})
        for ev in so.events.all():
            if ev.lat is not None and ev.lng is not None:
                points.append({'lat': float(ev.lat), 'lng': float(ev.lng),
                               'label': f'{ev.title} - {ev.location_label}'.strip(' -'), 'kind': 'event'})
    if order.has_ship_point:
        points.append({'lat': float(order.ship_lat), 'lng': float(order.ship_lng), 'label': 'Delivery address',
                       'kind': 'dest'})
    return {'order': order, 'parts': parts, 'points_json': json.dumps(points).replace('<', '\\u003c'), 'viewer': viewer,
            'payment': order.payments.first()}


@role_required(*CUSTOMER)
def home(request):
    user = request.user
    orders = Order.objects.filter(customer=user).prefetch_related('shop_orders__shop')
    active = orders.filter(status__in=['placed', 'in_progress']).count()
    spent = sum(o.total for o in orders.filter(payment_status='paid'))
    unread = Notification.objects.filter(user=user, is_read=False).count()
    kpis = [kpi('Orders', orders.count(), icon='box'), kpi('On the way', active, icon='truck'),
            kpi('Total spent', spent, icon='wallet', money=True),
            kpi('Wishlist', Wishlist.objects.filter(user=user).count(), icon='heart')]
    rows = []
    for o in orders[:6]:
        rows.append({'cells': [link(o.get_absolute_url(), o.number), o.placed_at.strftime('%d %b %Y'),
                               o.total, badge(o.status), badge(o.payment_status)], 'url': o.get_absolute_url()})
    bought = (Product.objects.filter(order_items__shop_order__order__customer=user).values_list('category', flat=True))
    recs = (Product.objects.filter(is_active=True, shop__status=ShopStatus.ACTIVE, category__in=list(bought))
            .exclude(order_items__shop_order__order__customer=user).select_related('shop', 'category')
            .order_by('-sold')[:8]) if bought else []
    if not recs:
        recs = (Product.objects.filter(is_active=True, shop__status=ShopStatus.ACTIVE).select_related('shop', 'category')
                .order_by('-sold')[:8])
    resp = show(request, 'portal/customer_home.html', {
        'kpis': kpis, 'recent': rows, 'recs': recs, 'unread': unread,
        'followed': user.followed_shops.filter(status=ShopStatus.ACTIVE)[:6],
    }, f'Hello, {user.first_name or user.display_name}')
    return resp


@role_required(*CUSTOMER)
def orders(request):
    qs = Order.objects.filter(customer=request.user).prefetch_related('shop_orders__shop')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    page = paginate(request, qs, 15)
    rows = [{'cells': [link(o.get_absolute_url(), o.number), o.placed_at.strftime('%d %b %Y %H:%M'),
                       ', '.join(so.shop.name for so in o.shop_orders.all()), o.total, badge(o.status),
                       badge(o.payment_status)], 'url': o.get_absolute_url()} for o in page.object_list]
    filters = [{'name': 'status', 'label': 'Status', 'type': 'select', 'value': status,
                'options': [('', 'All')] + [(k, v) for k, v in Order._meta.get_field('status').choices]}]
    return listing(request, 'My orders', ['Order', 'Placed', 'Shops', 'Total', 'Status', 'Payment'], rows, page,
                   filters, empty='You have not placed any orders yet.')


@role_required(*CUSTOMER)
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related('payments'), number=number, customer=request.user)
    return show(request, 'portal/order_detail.html', order_context(order), f'Order {order.number}')


@role_required(*CUSTOMER)
@require_POST
def order_cancel(request, so_id):
    so = get_object_or_404(ShopOrder, pk=so_id, order__customer=request.user)
    if so.status not in (ShopOrderStatus.PENDING, ShopOrderStatus.CONFIRMED):
        messages.error(request, 'This part of your order is already being packed or shipped, so it cannot be cancelled here. '
                                'Please chat with the seller.')
    else:
        try:
            cancel_shop_order(so, request.user, 'Cancelled by the customer', request)
            messages.success(request, 'Cancelled. Any payment already made will be refunded by the seller.')
        except OrderError as exc:
            messages.error(request, str(exc))
    return redirect(so.order.get_absolute_url())


@role_required(*CUSTOMER)
def wishlist(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product__shop', 'product__category')
    return show(request, 'portal/wishlist.html', {'items': items}, 'My wishlist')


@role_required(*CUSTOMER)
def addresses(request):
    form = AddressForm(request.POST or None, initial={'full_name': request.user.display_name,
                                                      'phone': request.user.phone})
    if request.method == 'POST' and form.is_valid():
        addr = form.save(commit=False)
        addr.user = request.user
        if addr.is_default:
            request.user.addresses.update(is_default=False)
        addr.save()
        messages.success(request, 'Address saved.')
        return redirect('portals:customer_addresses')
    return show(request, 'portal/addresses.html', {'form': form, 'items': request.user.addresses.all()}, 'My addresses')


@role_required(*CUSTOMER)
@require_POST
def address_delete(request, pk):
    get_object_or_404(Address, pk=pk, user=request.user).delete()
    messages.success(request, 'Address removed.')
    return redirect('portals:customer_addresses')


@role_required('customer', 'seller_owner', 'seller_staff', 'admin', 'analyst', 'developer', 'ceo', 'support')
def profile(request):
    from accounts.models import Attendance
    from django.utils import timezone
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated.')
        return redirect('portals:profile')
    today = None
    if request.user.is_platform_staff or request.user.is_seller_side:
        today = Attendance.objects.filter(user=request.user, date=timezone.localdate()).first()
    return show(request, 'portal/profile.html', {'form': form, 'attendance_today': today,
                                                 'staff_profile': getattr(request.user, 'staff_profile', None)},
                'Profile & appearance')
