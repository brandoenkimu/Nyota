"""A seller buys a PromotionPlan to get their shop onto the home-page carousel. Reuses the same M-Pesa/Stripe
rails as order payments (payments/mpesa.py, payments/stripe_service.py), through a generic Payment row
(payments.models.Payment.promotion) rather than one tied to an order."""
import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from audit.service import record
from core.models import HeroSlide
from core.notify import notify
from payments import mpesa, stripe_service
from payments.models import Payment, PaymentState

from .models import Promotion, PromotionStatus

log = logging.getLogger(__name__)


class PromotionError(Exception):
    pass


ART_VARIANTS = 6


@transaction.atomic
def start_purchase(request, shop, plan, method, phone=''):
    """Create a Promotion + Payment and kick off the chosen payment method. Returns the URL to send the seller to."""
    if not plan.active:
        raise PromotionError('That plan is no longer available.')
    if shop.promotions.filter(status=PromotionStatus.PENDING_PAYMENT).exists():
        raise PromotionError('You already have an advertising purchase waiting for payment.')
    promo = Promotion.objects.create(shop=shop, plan=plan, amount=plan.price, payment_method=method,
                                     created_by=request.user)
    record('promotion.started', target=promo, request=request, plan=plan.name, amount=str(plan.price))
    pay_url = reverse('ads:pay', args=[promo.pk])
    reference = f'AD-{promo.pk}'
    description = f'Nyota: feature {shop.name} for {plan.days} days'

    if method == 'mpesa':
        number = mpesa.normalize_phone(phone or shop.phone)
        if not number:
            raise PromotionError('Enter a valid Safaricom number such as 0712 345 678.')
        payment = Payment.objects.create(promotion=promo, method=method, state=PaymentState.INITIATED,
                                         amount=plan.price, currency=settings.CURRENCY, phone=number)
        if mpesa.is_configured():
            try:
                data = mpesa.stk_push(number, plan.price, reference, description)
            except Exception as exc:
                payment.state, payment.failure_reason = PaymentState.FAILED, str(exc)[:200]
                payment.save()
                raise PromotionError(f'M-Pesa could not start the payment: {exc}')
            payment.merchant_request_id = data.get('MerchantRequestID', '')
            payment.checkout_request_id = data.get('CheckoutRequestID', '')
            payment.state = PaymentState.PENDING
            payment.save()
        elif settings.PAYMENTS_SIMULATE:
            payment.simulated, payment.state = True, PaymentState.PENDING
            payment.checkout_request_id = f'SIM-{reference}'
            payment.save()
        else:
            payment.state, payment.failure_reason = PaymentState.FAILED, 'M-Pesa is not configured'
            payment.save()
            raise PromotionError('M-Pesa is not available right now. Please try card payment instead.')
        return pay_url

    if method == 'stripe':
        payment = Payment.objects.create(promotion=promo, method=method, state=PaymentState.INITIATED,
                                         amount=plan.price, currency=settings.CURRENCY)
        if stripe_service.is_configured():
            try:
                session = stripe_service.create_generic_checkout_session(
                    description, plan.price, request.build_absolute_uri(pay_url),
                    request.build_absolute_uri(pay_url), metadata={'promotion_id': str(promo.pk)},
                    customer_email=shop.contact_email or shop.owner.email)
            except Exception as exc:
                payment.state, payment.failure_reason = PaymentState.FAILED, str(exc)[:200]
                payment.save()
                raise PromotionError('Card payment could not be started. Please try again.')
            payment.stripe_session_id = session['id']
            payment.state = PaymentState.PENDING
            payment.save()
            return session['url']
        if settings.PAYMENTS_SIMULATE:
            payment.simulated, payment.state = True, PaymentState.PENDING
            payment.save()
            return pay_url
        payment.state, payment.failure_reason = PaymentState.FAILED, 'Stripe is not configured'
        payment.save()
        raise PromotionError('Card payments are not available right now.')
    raise PromotionError('Unknown payment method.')


@transaction.atomic
def activate(promo, request=None):
    """Called once the Payment succeeds: turns the purchase into a live home-page slide."""
    promo = Promotion.objects.select_for_update().get(pk=promo.pk)
    if promo.status == PromotionStatus.ACTIVE:
        return promo
    shop = promo.shop
    now = timezone.now()
    starts = max(now, promo.ends_at) if promo.slide_id and promo.ends_at and promo.ends_at > now else now
    slide = promo.slide
    if slide is None:
        slide = HeroSlide.objects.create(
            kicker='Featured seller', title=shop.name, subtitle=shop.tagline or f'Shop {shop.name} on Nyota',
            cta_label='Visit shop', cta_url=shop.get_absolute_url(), art_variant=shop.pk % ART_VARIANTS, sort=0,
            active=True)
        promo.slide = slide
    else:
        slide.active = True
        slide.save(update_fields=['active'])
    promo.status = PromotionStatus.ACTIVE
    promo.starts_at = starts
    promo.ends_at = starts + timezone.timedelta(days=promo.plan.days)
    promo.save()
    notify(shop.owner, f'{shop.name} is now featured!', f'Live on the home page for {promo.plan.days} days.',
           '/seller/advertise/')
    record('promotion.activated', target=promo, request=request, days=promo.plan.days, until=str(promo.ends_at))
    return promo


@transaction.atomic
def mark_purchase_failed(promo, reason='', request=None):
    promo = Promotion.objects.select_for_update().get(pk=promo.pk)
    if promo.status != PromotionStatus.PENDING_PAYMENT:
        return promo
    promo.status = PromotionStatus.CANCELLED
    promo.save(update_fields=['status'])
    record('promotion.failed', target=promo, request=request, reason=reason[:150])
    return promo


def expire_promotions():
    """Turn off the slide for any promotion whose paid period has ended. Returns how many were expired."""
    now = timezone.now()
    n = 0
    for promo in Promotion.objects.filter(status=PromotionStatus.ACTIVE, ends_at__lte=now).select_related('slide', 'shop'):
        promo.status = PromotionStatus.EXPIRED
        promo.save(update_fields=['status'])
        if promo.slide_id:
            HeroSlide.objects.filter(pk=promo.slide_id).update(active=False)
        notify(promo.shop.owner, f'{promo.shop.name} is no longer featured', 'Your advertising period ended. '
               'Buy another slot any time from Advertise.', '/seller/advertise/')
        record('promotion.expired', target=promo)
        n += 1
    return n


@transaction.atomic
def grant_free(shop, plan, granted_by, note='', request=None):
    """An admin/CEO features a shop for free — a promotion or reward, not a sale. Goes live immediately,
    exactly like a paid purchase, just with no Payment involved (amount recorded as 0, method 'comp' so
    it's easy to tell apart from paid slots in the Platform fees report)."""
    if shop.promotions.filter(status=PromotionStatus.PENDING_PAYMENT).exists():
        raise PromotionError('This shop already has an advertising purchase waiting for payment.')
    promo = Promotion.objects.create(shop=shop, plan=plan, amount=0, payment_method='comp',
                                     created_by=granted_by, status=PromotionStatus.PENDING_PAYMENT)
    record('promotion.granted', target=promo, request=request, plan=plan.name,
          by=granted_by.get_full_name() or granted_by.username, note=note[:200])
    return activate(promo, request=request)


@transaction.atomic
def cancel_pending(promo, request=None):
    if promo.status != PromotionStatus.PENDING_PAYMENT:
        raise PromotionError('Only a purchase still waiting for payment can be cancelled.')
    promo.status = PromotionStatus.CANCELLED
    promo.save(update_fields=['status'])
    record('promotion.cancelled', target=promo, request=request)
