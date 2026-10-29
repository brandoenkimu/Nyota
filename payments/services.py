import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from audit.service import record
from core.notify import notify
from orders.models import Order, PaymentMethod, PaymentStatus, ShopOrderStatus, TrackingEvent

from . import mpesa, stripe_service
from .models import Payment, PaymentState

log = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def start_payment(request, order, method, phone=''):
    """Create a Payment for the order and kick off the chosen method.
    Returns the URL the customer should be sent to."""
    previous = order.payment_method
    order.payment_method = method
    order.save(update_fields=['payment_method'])
    pay_url = reverse('orders:pay', args=[order.number])

    if method == PaymentMethod.COD:
        if previous != PaymentMethod.COD or not order.payments.exists():   # sellers hear about it now: nothing is left to wait for
            for so in order.shop_orders.select_related('shop__owner'):
                notify(so.shop.owner, f'New order {order.number}', 'Pay on delivery', f'/seller/orders/{so.pk}/')
        Payment.objects.create(order=order, method=method, state=PaymentState.PENDING, amount=order.total,
                               currency=settings.CURRENCY)
        order.payment_status = PaymentStatus.UNPAID
        order.save(update_fields=['payment_status'])
        return pay_url

    if method == PaymentMethod.MPESA:
        number = mpesa.normalize_phone(phone or order.ship_phone)
        if not number:
            raise PaymentError('Enter a valid Safaricom number such as 0712 345 678.')
        payment = Payment.objects.create(order=order, method=method, state=PaymentState.INITIATED,
                                         amount=order.total, currency=settings.CURRENCY, phone=number)
        if mpesa.is_configured():
            try:
                data = mpesa.stk_push(number, order.total, order.number, f'Nyota {order.number}')
            except Exception as exc:
                payment.state = PaymentState.FAILED
                payment.failure_reason = str(exc)[:200]
                payment.save()
                raise PaymentError(f'M-Pesa could not start the payment: {exc}')
            payment.merchant_request_id = data.get('MerchantRequestID', '')
            payment.checkout_request_id = data.get('CheckoutRequestID', '')
            payment.state = PaymentState.PENDING
            payment.save()
        elif settings.PAYMENTS_SIMULATE:
            payment.simulated = True
            payment.state = PaymentState.PENDING
            payment.checkout_request_id = f'SIM-{order.number}'
            payment.save()
        else:
            payment.state = PaymentState.FAILED
            payment.failure_reason = 'M-Pesa is not configured'
            payment.save()
            raise PaymentError('M-Pesa is not available right now. Please choose another payment method.')
        order.payment_status = PaymentStatus.PENDING
        order.save(update_fields=['payment_status'])
        return pay_url

    if method == PaymentMethod.STRIPE:
        payment = Payment.objects.create(order=order, method=method, state=PaymentState.INITIATED,
                                         amount=order.total, currency=settings.CURRENCY)
        if stripe_service.is_configured():
            try:
                session = stripe_service.create_checkout_session(
                    order,
                    request.build_absolute_uri(reverse('orders:stripe_return', args=[order.number])),
                    request.build_absolute_uri(pay_url))
            except Exception as exc:
                payment.state = PaymentState.FAILED
                payment.failure_reason = str(exc)[:200]
                payment.save()
                raise PaymentError('Card payment could not be started. Please try again.')
            payment.stripe_session_id = session['id']
            payment.state = PaymentState.PENDING
            payment.save()
            order.payment_status = PaymentStatus.PENDING
            order.save(update_fields=['payment_status'])
            return session['url']
        if settings.PAYMENTS_SIMULATE:
            payment.simulated = True
            payment.state = PaymentState.PENDING
            payment.save()
            order.payment_status = PaymentStatus.PENDING
            order.save(update_fields=['payment_status'])
            return pay_url
        payment.state = PaymentState.FAILED
        payment.failure_reason = 'Stripe is not configured'
        payment.save()
        raise PaymentError('Card payments are not available right now.')
    raise PaymentError('Unknown payment method.')


@transaction.atomic
def mark_paid(payment, receipt='', raw=None, request=None):
    """Idempotent: calling twice (e.g. callback + polling) does nothing the second time."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.state == PaymentState.SUCCEEDED:
        return payment
    payment.state = PaymentState.SUCCEEDED
    if receipt:
        payment.receipt = receipt
    if raw is not None:
        payment.raw = raw
    payment.save()
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == 'cancelled':
        log.warning('Payment %s succeeded for cancelled order %s: refund needed', payment.pk, order.number)
        record('payment.after_cancel', target=order, actor=order.customer, method=payment.method, receipt=payment.receipt)
    order.payment_status = PaymentStatus.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=['payment_status', 'paid_at'])
    for so in order.shop_orders.all():
        TrackingEvent.objects.create(shop_order=so, status=so.status, title='Payment received',
                                     detail=f'{payment.get_method_display()} payment confirmed'
                                            + (f' ({payment.receipt})' if payment.receipt else ''))
        notify(so.shop.owner, f'Order {order.number} is paid', 'You can confirm and pack it now.',
               f'/seller/orders/{so.pk}/')
    notify(order.customer, f'Payment received for {order.number}', 'Thank you!', f'/account/orders/{order.number}/')
    record('payment.succeeded', target=order, request=request, actor=order.customer, method=payment.method,
           receipt=payment.receipt, simulated=payment.simulated)
    return payment


@transaction.atomic
def mark_failed(payment, reason='', raw=None, cancelled=False):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.state == PaymentState.SUCCEEDED:
        return payment
    payment.state = PaymentState.CANCELLED if cancelled else PaymentState.FAILED
    payment.failure_reason = reason[:200]
    if raw is not None:
        payment.raw = raw
    payment.save()
    order = payment.order
    if order.payment_status != PaymentStatus.PAID:
        order.payment_status = PaymentStatus.FAILED
        order.save(update_fields=['payment_status'])
    record('payment.failed', target=order, actor=order.customer, method=payment.method, reason=reason)
    return payment
