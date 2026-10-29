from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .service import record


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    record('auth.login', target=user, request=request, actor=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        record('auth.logout', target=user, request=request, actor=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    ident = (credentials or {}).get('username', '')
    record('auth.login_failed', request=request, actor_label=str(ident)[:150])
