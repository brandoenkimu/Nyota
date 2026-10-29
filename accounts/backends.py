from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Sign in with either the e-mail address or the username (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None
        ident = username.strip()
        user = (User.objects.filter(Q(username__iexact=ident) | Q(email__iexact=ident))
                .order_by('id').first())
        if user is None:
            User().set_password(password)      # keep timing similar for unknown accounts
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
