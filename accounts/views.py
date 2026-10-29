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
from .forms import CustomerSignupForm, PasswordResetRequestForm, PortalAuthForm, SellerSignupForm
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
        if not settings.SHOP_AUTO_APPROVE:
            messages.info(self.request, 'Your shop is awaiting approval. You can set it up while you wait.')
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

    def form_valid(self, form):
        response = super().form_valid(form)
        User.objects.filter(pk=self.user.pk).update(must_change_password=False)
        record('auth.password_reset_done', target=self.user, request=self.request, actor=self.user)
        return response


class PasswordChange(auth_views.PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            User.objects.filter(pk=self.request.user.pk).update(must_change_password=False)
        record('auth.password_changed', target=self.request.user, request=self.request)
        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs['class'] = 'form-control'
        return form


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
