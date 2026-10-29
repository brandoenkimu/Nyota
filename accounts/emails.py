from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.mail import send_mail_async

VERIFY_SALT = 'nyota.verify-email'
VERIFY_MAX_AGE = 3 * 24 * 3600


def _abs(request, path):
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.SITE_URL.rstrip('/') + path


def send_verification(request, user):
    token = signing.dumps({'u': user.pk, 'e': user.email}, salt=VERIFY_SALT)
    ctx = {'user': user, 'url': _abs(request, reverse('accounts:verify_email', args=[token])),
           'COMPANY_NAME': settings.COMPANY_NAME}
    send_mail_async(f'Confirm your {settings.COMPANY_NAME} email',
                    render_to_string('emails/verify.txt', ctx),
                    render_to_string('emails/verify.html', ctx), [user.notification_email])


def read_verification_token(token):
    """Return (user_id, email) or None."""
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
        return data['u'], data['e']
    except (signing.BadSignature, KeyError):
        return None


def send_password_reset(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = _abs(request, reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': token}))
    ctx = {'user': user, 'url': url, 'COMPANY_NAME': settings.COMPANY_NAME}
    send_mail_async(f'Reset your {settings.COMPANY_NAME} password',
                    render_to_string('emails/reset.txt', ctx),
                    render_to_string('emails/reset.html', ctx), [user.notification_email])


def send_staff_welcome(request, user, password, shop=None):
    ctx = {'user': user, 'password': password, 'shop': shop, 'COMPANY_NAME': settings.COMPANY_NAME,
           'login_url': _abs(request, '/seller/login/' if shop else '/staff/login/')}
    send_mail_async(f'Your {settings.COMPANY_NAME} staff account',
                    render_to_string('emails/staff_welcome.txt', ctx),
                    render_to_string('emails/staff_welcome.html', ctx), [user.notification_email])
