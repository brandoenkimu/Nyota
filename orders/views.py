from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Address, Role
from catalog.models import Product
from payments import stripe_service
from payments.models import Payment, PaymentState
from payments.services import PaymentError, mark_failed, mark_paid, start_payment

from .cart import Cart
from .forms import CheckoutForm
from .models import Coupon, Order, PaymentMethod, PaymentStatus
from .services import OrderError, cancel_unpaid_order, create_order


def _coupon(request):
    code = request.session.get('coupon')
    return Coupon.objects.filter(code__iexact=code, active=True).first() if code else None


def cart_view(request):
    cart = Cart(request)
    summary = cart.groups(_coupon(request))
    return render(request, 'orders/cart.html', {'summary': summary, 'coupon': _coupon(request)})


def _back(request, fallback='orders:cart'):
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or fallback)


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    try:
        qty = max(1, int(request.POST.get('qty', 1)))
    except ValueError:
        qty = 1
    cart = Cart(request)
    if product.stock <= 0:
        msg = f'"{product.name}" is out of stock.'
        ok = False
    else:
        cart.add(product.pk, qty)
        msg = f'Added "{product.name}" to your cart.'
        ok = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': ok, 'message': msg, 'count': len(cart)}, status=200 if ok else 409)
    (messages.success if ok else messages.error)(request, msg)
    if request.POST.get('buy_now') and ok:
        return redirect('orders:checkout')
    return _back(request, 'core:products')


@require_POST
def cart_update(request, pk):
    try:
        Cart(request).set(pk, int(request.POST.get('qty', 1)))
    except ValueError:
        pass
    return redirect('orders:cart')


@require_POST
def cart_remove(request, pk):
    Cart(request).remove(pk)
    return redirect('orders:cart')


@require_POST
def cart_coupon(request):
    code = request.POST.get('code', '').strip()
    if not code:
        request.session.pop('coupon', None)
        return redirect('orders:cart')
    cp = Coupon.objects.filter(code__iexact=code, active=True).first()
    subtotal = Cart(request).groups()['subtotal']
    if cp and cp.is_valid_for(subtotal):
        request.session['coupon'] = cp.code
        messages.success(request, f'Coupon {cp.code} applied: {cp.percent}% off.')
    else:
        messages.error(request, 'That coupon is not valid for this cart.')
    return redirect('orders:cart')


@login_required
def checkout(request):
    user = request.user
    if user.role != Role.CUSTOMER:
        messages.info(request, 'Please sign in with a customer account to place orders.')
        return redirect('accounts:login')
    if settings.REQUIRE_VERIFIED_EMAIL and not user.email_verified:
        return render(request, 'orders/verify_needed.html')
    cart = Cart(request)
    coupon = _coupon(request)
    summary = cart.groups(coupon)
    if not summary['groups']:
        messages.info(request, 'Your cart is empty.')
        return redirect('core:products')
    addresses = list(user.addresses.all())
    default = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
    initial = {'full_name': user.display_name, 'phone': user.phone, 'mpesa_phone': user.phone,
               'payment_method': PaymentMethod.MPESA}
    if default:
        initial.update(full_name=default.full_name, phone=default.phone, line1=default.line1, city=default.city,
                       county=default.county, lat=default.lat, lng=default.lng)
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        if not summary['ok']:
            messages.error(request, 'Some items in your cart are no longer available in that quantity.')
            return redirect('orders:cart')
        d = form.cleaned_data
        address = {k: d[k] for k in ('full_name', 'phone', 'line1', 'city', 'county', 'lat', 'lng')}
        try:
            order = create_order(user, summary, address, d['payment_method'], d['notes'], coupon, request)
        except OrderError as exc:
            messages.error(request, str(exc))
            return redirect('orders:cart')
        if d['save_address'] and not Address.objects.filter(user=user, line1=d['line1'], city=d['city']).exists():
            Address.objects.create(user=user, label='Saved', is_default=not addresses, **address)
        cart.clear()
        try:
            url = start_payment(request, order, d['payment_method'], d['mpesa_phone'])
        except PaymentError as exc:
            messages.warning(request, f'{exc} Your order is saved. You can pay now or choose another method.')
            url = reverse('orders:pay', args=[order.number])
        return redirect(url)
    return render(request, 'orders/checkout.html', {'form': form, 'summary': summary, 'addresses': addresses,
                                                    'coupon': coupon})


def _my_order(request, number):
    return get_object_or_404(Order.objects.prefetch_related('payments', 'shop_orders__shop'),
                             number=number, customer=request.user)


@login_required
def pay(request, number):
    order = _my_order(request, number)
    payment = order.payments.first()
    if order.payment_status == PaymentStatus.PAID or (payment and payment.method == PaymentMethod.COD):
        return render(request, 'orders/done.html', {'order': order, 'payment': payment})
    return render(request, 'orders/pay.html', {
        'order': order, 'payment': payment, 'methods': PaymentMethod.choices,
        'simulated': bool(payment and payment.simulated)})


@login_required
def pay_status(request, number):
    order = _my_order(request, number)
    payment = order.payments.first()
    done = order.payment_status == PaymentStatus.PAID
    return JsonResponse({'state': payment.state if payment else '', 'paid': done,
                         'reason': payment.failure_reason if payment else '',
                         'receipt': payment.receipt if payment else ''})


@login_required
@require_POST
def pay_retry(request, number):
    order = _my_order(request, number)
    if order.payment_status == PaymentStatus.PAID:
        return redirect('orders:pay', number=number)
    if order.status == 'cancelled':
        messages.error(request, 'This order was cancelled. Please place a new order.')
        return redirect('orders:cart')
    try:
        url = start_payment(request, order, request.POST.get('payment_method', PaymentMethod.MPESA),
                            request.POST.get('mpesa_phone', ''))
    except PaymentError as exc:
        messages.error(request, str(exc))
        url = reverse('orders:pay', args=[number])
    return redirect(url)


@login_required
@require_POST
def simulate(request, number):
    """Demo mode only: lets you walk through the payment flow without real M-Pesa or card keys."""
    order = _my_order(request, number)
    payment = order.payments.filter(simulated=True, state=PaymentState.PENDING).first()
    if not payment:
        messages.error(request, 'Nothing to confirm.')
        return redirect('orders:pay', number=number)
    if request.POST.get('action') == 'fail':
        mark_failed(payment, 'Declined in demo mode')
        messages.warning(request, 'Payment declined (demo). You can try again.')
    else:
        receipt = 'SIM' + order.number.replace('-', '')[-8:]
        mark_paid(payment, receipt=receipt, request=request)
        messages.success(request, 'Payment confirmed (demo).')
    return redirect('orders:pay', number=number)


@login_required
def stripe_return(request, number):
    order = _my_order(request, number)
    payment = order.payments.filter(method=PaymentMethod.STRIPE).exclude(stripe_session_id='').first()
    if payment and payment.state != PaymentState.SUCCEEDED and stripe_service.is_configured():
        try:
            session = stripe_service.retrieve_session(payment.stripe_session_id)
            if session.get('payment_status') == 'paid':
                mark_paid(payment, receipt=session.get('payment_intent') or '', request=request)
        except Exception:
            pass
    return redirect('orders:pay', number=number)


@login_required
@require_POST
def pay_cancel(request, number):
    """Customer gives up on paying online: cancel the whole order and put the stock back."""
    order = _my_order(request, number)
    payment = order.payments.first()
    if payment and payment.state == PaymentState.PENDING and not payment.simulated:
        messages.warning(request, 'A payment prompt is still open. Finish or cancel it on your phone, then try again.')
        return redirect('orders:pay', number=number)
    try:
        cancel_unpaid_order(order, request.user, 'Cancelled by the customer before payment', request)
        messages.success(request, f'Order {order.number} was cancelled. Nothing was charged.')
        return redirect('core:home')
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect('orders:pay', number=number)
