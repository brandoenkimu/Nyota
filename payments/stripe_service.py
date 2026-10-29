"""Stripe Checkout (hosted card page). The `stripe` package is imported lazily."""
from django.conf import settings


def is_configured() -> bool:
    return bool(settings.STRIPE['secret_key'])


def _stripe():
    import stripe
    stripe.api_key = settings.STRIPE['secret_key']
    return stripe


def create_checkout_session(order, success_url, cancel_url):
    stripe = _stripe()
    items = [{
        'price_data': {'currency': settings.CURRENCY.lower(),
                       'product_data': {'name': f'Nyota order {order.number}'},
                       'unit_amount': int(order.total * 100)},
        'quantity': 1,
    }]
    return stripe.checkout.Session.create(
        mode='payment', line_items=items, success_url=success_url, cancel_url=cancel_url,
        client_reference_id=order.number, customer_email=order.customer.email,
        metadata={'order_number': order.number})


def retrieve_session(session_id):
    return _stripe().checkout.Session.retrieve(session_id)


def construct_event(payload: bytes, signature: str):
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE['webhook_secret'])
