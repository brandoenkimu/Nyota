from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class AccountStateMiddleware:
    """Keeps 'last seen' fresh and forces a password change after an administrator-issued password."""

    ALLOWED_PREFIXES = ('/static/', '/media/', '/logout/', '/account/password/', '/ws/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            key = f'seen:{user.pk}'
            if not cache.get(key):
                cache.set(key, 1, 300)
                get_user_model().objects.filter(pk=user.pk).update(last_seen=timezone.now())
            if user.must_change_password and not request.path.startswith(self.ALLOWED_PREFIXES):
                return redirect(reverse('accounts:password_change'))
        return self.get_response(request)