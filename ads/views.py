"""Seller-facing 'Advertise my shop' purchase flow. Mirrors orders/views.py's pay page (same polling pattern)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from payments import stripe_service
from payments.models import Payment, PaymentState
from payments.services import mark_failed, mark_paid
from portals.common import show

from . import services
from .models import Promotion, PromotionPlan, PromotionStatus


def _shop(request):
    if not request.user.is_authenticated or request.user.role != 'seller_owner' or not request.user.shop:
        return None
    return request.user.shop


@login_required
def plans(request):
    shop = _shop(request)
    if shop is None:
        messages.warning(request, 'Only a shop owner can buy advertising.')
        return redirect('core:home')
    live = shop.promotions.filter(status=PromotionStatus.ACTIVE).order_by('-ends_at').first()
    pending = shop.promotions.filter(status=PromotionStatus.PENDING_PAYMENT).first()
    return show(request, 'ads/plans.html', {
        'plans': PromotionPlan.objects.filter(active=True), 'live': live, 'pending': pending, 'shop': shop,
        'history': shop.promotions.exclude(status=PromotionStatus.PENDING_PAYMENT)[:10]}, 'Advertise my shop')


@login_required
@require_POST
def buy(request, pk):
    shop = _shop(request)
    if shop is None:
        return redirect('core:home')
    plan = get_object_or_404(PromotionPlan, pk=pk, active=True)
    try:
        url = services.start_purchase(request, shop, plan, request.POST.get('payment_method', 'mpesa'),
                                      request.POST.get('mpesa_phone', ''))
    except services.PromotionError as exc:
        messages.error(request, str(exc))
        return redirect('ads:plans')
    return redirect(url)


def _my_promo(request, pk):
    shop = _shop(request)
    return get_object_or_404(Promotion, pk=pk, shop=shop) if shop else None


@login_required
def pay(request, pk):
    promo = _my_promo(request, pk)
    if promo is None:
        return redirect('ads:plans')
    if promo.status == PromotionStatus.ACTIVE:
        return render(request, 'ads/done.html', {'promo': promo})
    payment = promo.payments.first()
    return render(request, 'ads/pay.html', {'promo': promo, 'payment': payment,
                                            'simulated': bool(payment and payment.simulated)})


@login_required
def pay_status(request, pk):
    promo = _my_promo(request, pk)
    if promo is None:
        return JsonResponse({'error': 'not found'}, status=404)
    payment = promo.payments.first()
    return JsonResponse({'state': payment.state if payment else '', 'active': promo.status == PromotionStatus.ACTIVE,
                         'failed': promo.status == PromotionStatus.CANCELLED,
                         'reason': payment.failure_reason if payment else ''})


@login_required
@require_POST
def simulate(request, pk):
    promo = _my_promo(request, pk)
    if promo is None:
        return redirect('ads:plans')
    payment = promo.payments.filter(simulated=True, state=PaymentState.PENDING).first()
    if not payment:
        messages.error(request, 'Nothing to simulate.')
        return redirect('ads:pay', pk=pk)
    if request.POST.get('action') == 'fail':
        mark_failed(payment, 'Declined in demo mode')
        messages.warning(request, 'Payment declined (demo).')
    else:
        mark_paid(payment, receipt=f'DEMO-AD-{promo.pk}', request=request)
        messages.success(request, 'Payment confirmed — your shop is now featured!')
    return redirect('ads:pay', pk=pk)


@login_required
@require_POST
def cancel(request, pk):
    promo = _my_promo(request, pk)
    if promo is None:
        return redirect('ads:plans')
    try:
        services.cancel_pending(promo, request)
        messages.success(request, 'Purchase cancelled.')
    except services.PromotionError as exc:
        messages.error(request, str(exc))
    return redirect('ads:plans')


@login_required
def stripe_return(request, pk):
    promo = _my_promo(request, pk)
    if promo is None:
        return redirect('ads:plans')
    payment = promo.payments.filter(method='stripe').exclude(stripe_session_id='').first()
    if payment and payment.state != PaymentState.SUCCEEDED and stripe_service.is_configured():
        try:
            session = stripe_service.retrieve_session(payment.stripe_session_id)
            if session.get('payment_status') == 'paid':
                mark_paid(payment, receipt=session.get('payment_intent') or '', request=request)
        except Exception:
            pass
    return redirect('ads:pay', pk=pk)
