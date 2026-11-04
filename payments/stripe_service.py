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


def create_generic_checkout_session(description, amount, success_url, cancel_url, metadata=None, customer_email=''):
    """Like create_checkout_session but for a purchase that isn't an order (e.g. a seller buying an ad slot)."""
    stripe = _stripe()
    items = [{
        'price_data': {'currency': settings.CURRENCY.lower(), 'product_data': {'name': description[:120]},
                       'unit_amount': int(amount * 100)},
        'quantity': 1,
    }]
    kwargs = dict(mode='payment', line_items=items, success_url=success_url, cancel_url=cancel_url,
                  metadata=metadata or {})
    if customer_email:
        kwargs['customer_email'] = customer_email
    return stripe.checkout.Session.create(**kwargs)


def retrieve_session(session_id):
    return _stripe().checkout.Session.retrieve(session_id)


def construct_event(payload: bytes, signature: str):
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE['webhook_secret'])
