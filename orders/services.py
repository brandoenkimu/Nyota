from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from audit.service import record
from catalog.models import Product
from core.notify import notify

from .models import (Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus, ShopOrder, ShopOrderStatus,
                     TrackingEvent, split_commission)


class OrderError(Exception):
    pass


@transaction.atomic
def create_order(user, summary, address, method, notes='', coupon=None, request=None):
    """Turn a cart summary (Cart.groups()) into an order. Stock is locked and decremented here."""
    if not summary['groups']:
        raise OrderError('Your cart is empty.')
    ids = [line['product'].pk for g in summary['groups'] for line in g['lines']]
    locked = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=ids)}
    for g in summary['groups']:
        for line in g['lines']:
            p = locked.get(line['product'].pk)
            if p is None or not p.is_active:
                raise OrderError(f'"{line["product"].name}" is no longer available.')
            if p.stock < line['wanted']:
                raise OrderError(f'Only {p.stock} of "{p.name}" left in stock.')

    order = Order.objects.create(
        customer=user, payment_method=method, subtotal=summary['subtotal'], shipping_total=summary['shipping'],
        discount_total=summary['discount'], total=summary['total'], coupon=coupon if summary['discount'] else None,
        ship_name=address['full_name'], ship_phone=address['phone'], ship_line1=address['line1'],
        ship_city=address['city'], ship_county=address.get('county', ''), ship_lat=address.get('lat'),
        ship_lng=address.get('lng'), notes=notes,
        payment_status=PaymentStatus.UNPAID)

    for g in summary['groups']:
        shop = g['shop']
        net = g['subtotal'] - g['discount']
        commission, after = split_commission(net, shop.commission_percent)
        so = ShopOrder.objects.create(
            order=order, shop=shop, subtotal=g['subtotal'], shipping_fee=g['shipping'], discount=g['discount'],
            commission_percent=shop.commission_percent, commission_amount=commission,
            seller_earnings=after + g['shipping'])
        for line in g['lines']:
            p = locked[line['product'].pk]
            OrderItem.objects.create(shop_order=so, product=p, name=p.name, sku=p.sku, unit_price=p.price,
                                     unit_cost=p.cost_price, quantity=line['wanted'])
            Product.objects.filter(pk=p.pk).update(stock=F('stock') - line['wanted'], sold=F('sold') + line['wanted'])
        TrackingEvent.objects.create(shop_order=so, status=ShopOrderStatus.PENDING, title='Order received',
                                     detail=f'Order {order.number} was placed.', created_by=user)
        # the seller is notified when the order becomes payable: pay-on-delivery chosen, or online payment confirmed
    if coupon and summary['discount']:
        type(coupon).objects.filter(pk=coupon.pk).update(used=F('used') + 1)
    notify(user, f'Order {order.number} placed', 'We will keep you posted as it moves.', f'/account/orders/{order.number}/')
    record('order.placed', target=order, request=request, actor=user, total=str(order.total), method=method)
    return order


@transaction.atomic
def cancel_shop_order(shop_order, actor, reason='', request=None):
    """Cancel one shop's part of an order and put its stock back."""
    shop_order = ShopOrder.objects.select_for_update().get(pk=shop_order.pk)
    if shop_order.status in (ShopOrderStatus.DELIVERED, ShopOrderStatus.CANCELLED):
        raise OrderError('This part of the order can no longer be cancelled.')
    for item in shop_order.items.select_related('product'):
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity,
                                                              sold=F('sold') - item.quantity)
    shop_order.status = ShopOrderStatus.CANCELLED
    shop_order.save(update_fields=['status'])
    TrackingEvent.objects.create(shop_order=shop_order, status=ShopOrderStatus.CANCELLED, title='Cancelled',
                                 detail=reason[:300], created_by=actor)
    shop_order.order.refresh_status()
    notify(shop_order.order.customer, f'Part of order {shop_order.order.number} was cancelled',
           reason[:200], f'/account/orders/{shop_order.order.number}/')
    record('order.cancelled', target=shop_order, request=request, actor=actor, reason=reason)
    return shop_order


@transaction.atomic
def advance_shop_order(shop_order, actor, status, title='', detail='', location='', lat=None, lng=None,
                       courier='', tracking_number='', expected=None, occurred_at=None, request=None):
    """Move a shop's part of an order to a new status and record a tracking event."""
    shop_order = ShopOrder.objects.select_for_update().select_related('order').get(pk=shop_order.pk)
    if shop_order.status in (ShopOrderStatus.DELIVERED, ShopOrderStatus.CANCELLED):
        raise OrderError('This order is already closed.')
    labels = dict(ShopOrderStatus.choices)
    if status not in labels:
        raise OrderError('Unknown status.')
    now = occurred_at or timezone.now()
    shop_order.status = status
    if courier:
        shop_order.courier = courier
    if tracking_number:
        shop_order.tracking_number = tracking_number
    if expected:
        shop_order.expected_delivery = expected
    if status == ShopOrderStatus.SHIPPED and not shop_order.shipped_at:
        shop_order.shipped_at = now
    if status == ShopOrderStatus.DELIVERED:
        shop_order.delivered_at = now
    shop_order.save()
    TrackingEvent.objects.create(shop_order=shop_order, status=status, title=title or labels[status], detail=detail,
                                 location_label=location, lat=lat, lng=lng, occurred_at=now, created_by=actor)
    order = shop_order.order
    if status == ShopOrderStatus.DELIVERED and order.payment_method == PaymentMethod.COD:
        # cash collected on delivery: this shop's part is settled
        if not order.shop_orders.exclude(pk=shop_order.pk).exclude(status=ShopOrderStatus.DELIVERED).exists():
            order.payment_status = PaymentStatus.PAID
            order.paid_at = now
            order.save(update_fields=['payment_status', 'paid_at'])
    order.refresh_status()
    notify(order.customer, f'Order {order.number}: {labels[status]}', detail[:200] or shop_order.shop.name,
           f'/account/orders/{order.number}/')
    record('order.status', target=shop_order, request=request, actor=actor, status=status)
    return shop_order


PAYABLE_AFTER_MINUTES = 60


@transaction.atomic
def cancel_unpaid_order(order, actor=None, reason='Payment was not completed', request=None):
    """Cancel every open part of an order that was never paid, putting the stock back."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.payment_status == PaymentStatus.PAID or order.payment_method == PaymentMethod.COD:
        raise OrderError('Only unpaid online orders can be cancelled this way.')
    for so in order.shop_orders.all():
        if so.status not in (ShopOrderStatus.DELIVERED, ShopOrderStatus.CANCELLED):
            cancel_shop_order(so, actor, reason, request)
    for p in order.payments.filter(state__in=['initiated', 'pending', 'failed']):
        p.state = 'cancelled'
        p.save(update_fields=['state'])
    return order


def expire_unpaid_orders(minutes=PAYABLE_AFTER_MINUTES):
    """Cancel online orders still unpaid after `minutes`, releasing their stock. Returns how many."""
    from datetime import timedelta
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(minutes=minutes)
    qs = (Order.objects.filter(placed_at__lt=cutoff, payment_status__in=[PaymentStatus.UNPAID, PaymentStatus.PENDING,
                                                                       PaymentStatus.FAILED])
          .exclude(payment_method=PaymentMethod.COD))
    n = 0
    for order in qs:
        try:
            cancel_unpaid_order(order, None, f'Payment was not completed within {minutes} minutes')
            n += 1
        except OrderError:
            pass
    return n
