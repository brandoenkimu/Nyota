from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from audit.service import record

from . import emails, throttle
from .forms import (CustomerSignupForm, PasswordResetRequestForm, PortalAuthForm, SellerSignupForm,
                    StyledPasswordChangeForm, StyledSetPasswordForm)
from .models import Attendance, Role

User = get_user_model()

PORTALS = {
    'customer': {
        'title': 'Welcome back', 'sub': 'Sign in to follow your orders, chat with sellers and keep your wishlist.',
        'allowed': (Role.CUSTOMER,), 'aura': 'violet', 'badge': 'Customer',
    },
    'seller': {
        'title': 'Seller studio', 'sub': 'Manage your shop, stock, orders and team in one place.',
        'allowed': (Role.SELLER_OWNER, Role.SELLER_STAFF), 'aura': 'emerald', 'badge': 'Seller',
    },
    'staff': {
        'title': 'Nyota mission control', 'sub': 'For administrators, analysts, developers, support and the CEO.',
        'allowed': (Role.ADMIN, Role.ANALYST, Role.DEVELOPER, Role.CEO, Role.SUPPORT), 'aura': 'sky',
        'badge': 'Staff',
    },
}


class PortalLoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = PortalAuthForm
    redirect_authenticated_user = False
    portal = 'customer'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['allowed_roles'] = PORTALS[self.portal]['allowed']
        kwargs['portal'] = self.portal
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(portal=self.portal, p=PORTALS[self.portal], next=self.request.GET.get('next', ''))
        return ctx

    def get_success_url(self):
        return self.get_redirect_url() or self.request.user.home_url

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.POST.get('remember'):
            self.request.session.set_expiry(0)       # forget the sign-in when the browser closes
        return response


def logout_view(request):
    if request.method == 'POST' or request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been signed out.')
    return redirect('core:home')


class CustomerSignupView(FormView):
    template_name = 'accounts/signup.html'
    form_class = CustomerSignupForm
    kind = 'customer'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.user.home_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(portal=self.kind, p=PORTALS[self.kind])
        return ctx

    def form_valid(self, form):
        user = form.save()
        record('auth.signup', target=user, request=self.request, actor=user, role=user.role)
        emails.send_verification(self.request, user)
        login(self.request, user, backend='accounts.backends.EmailOrUsernameBackend')
        messages.success(self.request, 'Welcome aboard! We sent a confirmation link to your email.')
        return redirect(user.home_url)


class SellerSignupView(CustomerSignupView):
    form_class = SellerSignupForm
    kind = 'seller'
    template_name = 'accounts/signup.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        if settings.REQUIRE_SELLER_VERIFICATION or not settings.SHOP_AUTO_APPROVE:
            messages.info(self.request, 'Your shop goes live after verification: open Verification in your seller menu and upload your documents.')
        return response


def verify_email(request, token):
    data = emails.read_verification_token(token)
    if not data:
        messages.error(request, 'That confirmation link is invalid or has expired. Request a new one below.')
        return redirect('core:home')
    uid, email = data
    user = User.objects.filter(pk=uid, email=email).first()
    if not user:
        messages.error(request, 'That confirmation link is no longer valid.')
        return redirect('core:home')
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        record('auth.email_verified', target=user, request=request, actor=user)
    messages.success(request, 'Email confirmed. Thank you!')
    return redirect(user.home_url if request.user.is_authenticated else 'accounts:login')


@login_required
@require_POST
def resend_verification(request):
    if request.user.email_verified:
        messages.info(request, 'Your email is already confirmed.')
    elif throttle.is_locked(f'verify:{request.user.pk}', ''):
        messages.warning(request, 'Please wait a few minutes before asking for another email.')
    else:
        throttle.register_failure(f'verify:{request.user.pk}', '')
        emails.send_verification(request, request.user)
        messages.success(request, 'Confirmation email sent.')
    return redirect(request.META.get('HTTP_REFERER') or request.user.home_url)


class PasswordResetRequestView(FormView):
    template_name = 'accounts/password_reset.html'
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def get_initial(self):
        initial = super().get_initial()
        ident = self.request.GET.get('identifier', '').strip()
        if ident:
            initial['identifier'] = ident
        return initial

    def form_valid(self, form):
        ident = form.cleaned_data['identifier'].strip()
        ip = throttle.client_ip(self.request)
        key = f'reset:{ident.lower()}'
        if not throttle.is_locked(key, ip):
            throttle.register_failure(key, ip)       # counts requests: at most 5 per window
            from django.db.models import Q
            user = User.objects.filter(Q(email__iexact=ident) | Q(username__iexact=ident), is_active=True).first()
            if user and user.has_usable_password():
                emails.send_password_reset(self.request, user)
                record('auth.password_reset_requested', target=user, request=self.request, actor=user)
        # identical answer whether or not the account exists
        return super().form_valid(form)


class PasswordResetConfirm(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    form_class = StyledSetPasswordForm

    def dispatch(self, request, *args, **kwargs):
        # The real token only appears once, on the first click; Django immediately swaps it for a one-time
        # 'set-password' placeholder in the URL (so the real token never stays in browser history), so that
        # first request is the one moment we can log "this link was actually opened".
        is_first_click = kwargs.get('token') not in (None, auth_views.INTERNAL_RESET_URL_TOKEN)
        response = super().dispatch(request, *args, **kwargs)
        # Log every open of a reset link against the account it names — not just a successful reset — so
        # support can see, from the audit log, that a link was opened/used if someone reports trouble,
        # without the link or token itself ever being stored or shown to anyone.
        user = getattr(self, 'user', None)
        if request.method == 'GET' and is_first_click and user is not None:
            record('auth.password_reset_link_opened', target=user, request=request, actor=user,
                  valid=bool(self.validlink))
        return response

    def form_valid(self, form):
        response = super().form_valid(form)
        User.objects.filter(pk=self.user.pk).update(must_change_password=False)
        record('auth.password_reset_done', target=self.user, request=self.request, actor=self.user)
        return response


class PasswordChange(auth_views.PasswordChangeView):
    """Change password while signed in (needs the current password — this is intentional here, unlike
    'forgot password', which never needs it). Someone who knows the account is signed in but has forgotten the
    current password cannot brute-force their way past this: repeated wrong guesses lock the attempt out, same
    as a failed sign-in, and the page offers a way out via email instead (see get_context_data)."""
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')
    form_class = StyledPasswordChangeForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            ip = throttle.client_ip(request)
            self._key = f'oldpw:{request.user.pk}'
            if throttle.is_locked(self._key, ip):
                messages.error(request, 'Too many incorrect attempts. Use "Forgot your current password?" below, '
                                        'or try again in a few minutes.')
                return redirect('accounts:password_change')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        throttle.clear(self._key, throttle.client_ip(self.request))
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            User.objects.filter(pk=self.request.user.pk).update(must_change_password=False)
        record('auth.password_changed', target=self.request.user, request=self.request)
        return response

    def form_invalid(self, form):
        if 'old_password' in form.errors:
            throttle.register_failure(self._key, throttle.client_ip(self.request))
        return super().form_invalid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs['class'] = 'form-control'
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['forgot_url'] = (f"{reverse_lazy('accounts:password_reset')}?identifier="
                             f"{self.request.user.email if hasattr(self, 'request') else ''}")
        return ctx


def password_change_done(request):
    messages.success(request, 'Your password was changed.')
    return redirect(request.user.home_url if request.user.is_authenticated else 'core:home')


@login_required
@require_POST
def clock(request):
    """Staff clock in / clock out (attendance)."""
    user = request.user
    if not (user.is_platform_staff or user.is_seller_side):
        messages.error(request, 'Attendance is for staff accounts.')
        return redirect(user.home_url)
    today = timezone.localdate()
    now = timezone.now()
    row = Attendance.objects.filter(user=user, date=today).first()
    action = request.POST.get('action')
    if action == 'in':
        if row:
            messages.info(request, 'You have already clocked in today.')
        else:
            late = timezone.localtime(now).time() > settings.WORK_START
            Attendance.objects.create(user=user, date=today, clock_in=now, late=late,
                                      ip=throttle.client_ip(request) or None)
            record('attendance.clock_in', target=user, request=request, late=late)
            messages.success(request, 'Clocked in. Have a productive day!' if not late else
                             'Clocked in (marked late). Have a productive day!')
    elif action == 'out':
        if row and row.clock_out is None:
            row.clock_out = now
            row.save(update_fields=['clock_out'])
            record('attendance.clock_out', target=user, request=request, hours=row.hours)
            messages.success(request, f'Clocked out after {row.hours} hours. See you tomorrow!')
        else:
            messages.info(request, 'You are not clocked in.')
    return redirect(request.POST.get('next') or user.home_url)


def person(request, username):
    """A member's profile as the viewer is allowed to see it (see accounts/profiles.py)."""
    from django.contrib.auth.decorators import login_required
    from django.http import Http404
    from django.shortcuts import get_object_or_404, render
    from django.urls import reverse
    from chat.services import can_message
    from portals.common import show
    from .profiles import profile_access, profile_context
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    target = get_object_or_404(get_user_model(), username=username)
    level = profile_access(request.user, target)
    if level is None:
        return show(request, 'portal/person_denied.html', {}, 'Profile not available', status=403)
    if target.role == Role.SELLER_OWNER and request.user.role == Role.CUSTOMER and target.shop:
        return redirect(target.shop.get_absolute_url())
    if level in ('staff', 'full') and request.user.pk != target.pk:
        record('profile.viewed', target=target, request=request, level=level)
    ctx = profile_context(request.user, target, level)
    ctx['can_message'] = can_message(request.user, target)
    return show(request, 'portal/person.html', ctx, target.display_name)
