"""Safaricom Daraja: STK push (Lipa na M-Pesa Online). Sandbox by default."""
import base64
import hashlib
import hmac
import math
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache

TIMEOUT = 20


def is_configured() -> bool:
    c = settings.MPESA
    return bool(c['consumer_key'] and c['consumer_secret'] and c['passkey'] and c['callback_url'])


def base_url() -> str:
    return 'https://api.safaricom.co.ke' if settings.MPESA['env'] == 'production' else 'https://sandbox.safaricom.co.ke'


def callback_token() -> str:
    """Secret path segment so only Safaricom (who is given the full URL) can post to our callback."""
    return hmac.new(settings.SECRET_KEY.encode(), b'mpesa-callback', hashlib.sha256).hexdigest()[:24]


def callback_url() -> str:
    return settings.MPESA['callback_url'].rstrip('/') + f'/payments/mpesa/callback/{callback_token()}/'


def normalize_phone(phone: str):
    """'0712 345 678', '+254712345678', '712345678' -> '254712345678'; None if it is not a Kenyan mobile."""
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('0'):
        digits = '254' + digits[1:]
    elif digits.startswith(('7', '1')) and len(digits) == 9:
        digits = '254' + digits
    return digits if re.fullmatch(r'254[17]\d{8}', digits) else None


def access_token() -> str:
    token = cache.get('mpesa:token')
    if token:
        return token
    c = settings.MPESA
    r = requests.get(f'{base_url()}/oauth/v1/generate?grant_type=client_credentials',
                     auth=(c['consumer_key'], c['consumer_secret']), timeout=TIMEOUT)
    r.raise_for_status()
    token = r.json()['access_token']
    cache.set('mpesa:token', token, 3000)
    return token


def stk_push(phone: str, amount, reference: str, description: str) -> dict:
    c = settings.MPESA
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f"{c['shortcode']}{c['passkey']}{ts}".encode()).decode()
    payload = {
        'BusinessShortCode': c['shortcode'], 'Password': password, 'Timestamp': ts,
        'TransactionType': 'CustomerPayBillOnline', 'Amount': int(math.ceil(float(amount))),
        'PartyA': phone, 'PartyB': c['shortcode'], 'PhoneNumber': phone, 'CallBackURL': callback_url(),
        'AccountReference': reference[:12], 'TransactionDesc': description[:13] or 'Payment',
    }
    r = requests.post(f'{base_url()}/mpesa/stkpush/v1/processrequest', json=payload,
                      headers={'Authorization': f'Bearer {access_token()}'}, timeout=TIMEOUT)
    data = r.json() if r.content else {}
    if r.status_code != 200 or data.get('ResponseCode') != '0':
        raise RuntimeError(data.get('errorMessage') or data.get('ResponseDescription') or 'M-Pesa rejected the request')
    return data


def parse_callback(body: dict) -> dict:
    cb = (body or {}).get('Body', {}).get('stkCallback', {})
    items = {i.get('Name'): i.get('Value') for i in cb.get('CallbackMetadata', {}).get('Item', [])}
    return {
        'merchant_request_id': cb.get('MerchantRequestID', ''),
        'checkout_request_id': cb.get('CheckoutRequestID', ''),
        'result_code': cb.get('ResultCode'),
        'result_desc': cb.get('ResultDesc', ''),
        'receipt': str(items.get('MpesaReceiptNumber', '')),
        'amount': items.get('Amount'),
        'phone': str(items.get('PhoneNumber', '')),
    }
