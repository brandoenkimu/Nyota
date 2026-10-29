import hmac
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import mpesa, stripe_service
from .models import Payment, PaymentState, WebhookLog
from .services import mark_failed, mark_paid

log = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def mpesa_callback(request, token):
    """Safaricom posts the STK result here. Always answers 200 so Safaricom does not retry forever."""
    ok_token = hmac.compare_digest(token, mpesa.callback_token())
    raw = request.body.decode('utf-8', 'replace')[:20000]
    entry = WebhookLog.objects.create(provider='mpesa', payload=raw, signature_ok=ok_token)
    ack = JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
    if not ok_token:
        return ack
    try:
        data = mpesa.parse_callback(json.loads(raw))
        payment = Payment.objects.filter(checkout_request_id=data['checkout_request_id'],
                                         method='mpesa').first()
        if payment is None:
            entry.note = 'unknown checkout request'
        elif data['result_code'] == 0:
            if data['amount'] is not None and float(data['amount']) + 0.99 < float(payment.amount):
                entry.note = 'amount mismatch'
                mark_failed(payment, 'Amount paid was less than the order total', raw=json.loads(raw))
            else:
                mark_paid(payment, receipt=data['receipt'], raw=json.loads(raw))
                entry.handled = True
        else:
            mark_failed(payment, data['result_desc'], raw=json.loads(raw), cancelled=data['result_code'] == 1032)
            entry.handled = True
    except Exception as exc:
        log.exception('mpesa callback failed')
        entry.note = f'error: {exc}'[:200]
    entry.save()
    return ack


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    entry = WebhookLog.objects.create(provider='stripe', payload=payload.decode('utf-8', 'replace')[:20000])
    try:
        event = stripe_service.construct_event(payload, sig)
    except Exception:
        entry.signature_ok = False
        entry.note = 'bad signature'
        entry.save()
        return HttpResponse(status=400)
    try:
        obj = event['data']['object']
        if event['type'] == 'checkout.session.completed' and obj.get('payment_status') == 'paid':
            payment = Payment.objects.filter(stripe_session_id=obj['id']).first()
            if payment:
                payment.stripe_payment_intent = obj.get('payment_intent') or ''
                payment.save(update_fields=['stripe_payment_intent'])
                mark_paid(payment, receipt=obj.get('payment_intent') or '', raw=dict(obj))
                entry.handled = True
        elif event['type'] in ('checkout.session.expired', 'payment_intent.payment_failed'):
            payment = Payment.objects.filter(stripe_session_id=obj.get('id', '')).first()
            if payment and payment.state != PaymentState.SUCCEEDED:
                mark_failed(payment, event['type'])
                entry.handled = True
    except Exception as exc:
        log.exception('stripe webhook failed')
        entry.note = f'error: {exc}'[:200]
    entry.save()
    return HttpResponse(status=200)
