from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.utils import unique_username
from shops.models import MemberRole, Shop, ShopStatus

from . import throttle
from .models import Address, Role, StaffProfile
from .staffnames import PLATFORM_CODES, SHOP_CODES, SHOP_ROLE_TITLES, build_identity, domain_part, temp_password

User = get_user_model()

LOGIN_LABELS = {
    'customer': ('Customer sign-in', '/login/'),
    'seller': ('Seller sign-in', '/seller/login/'),
    'staff': ('Staff sign-in', '/staff/login/'),
}
ROLE_PORTAL = {
    Role.CUSTOMER: 'customer', Role.SELLER_OWNER: 'seller', Role.SELLER_STAFF: 'seller',
    Role.ADMIN: 'staff', Role.ANALYST: 'staff', Role.DEVELOPER: 'staff', Role.CEO: 'staff', Role.SUPPORT: 'staff',
}


class BootstrapMixin:
    """Gives every widget the Bootstrap classes, so forms look right without hand-written markup."""

    def _style(self):
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                cls = 'form-check-input'
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                cls = 'form-select'
            elif isinstance(w, forms.FileInput):
                cls = 'form-control'
            else:
                cls = 'form-control'
            w.attrs['class'] = (w.attrs.get('class', '') + ' ' + cls).strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class PortalAuthForm(AuthenticationForm):
    """Sign-in form that also enforces which kind of account may use which door."""

    def __init__(self, request=None, *args, allowed_roles=(), portal='customer', **kwargs):
        super().__init__(request, *args, **kwargs)
        self.allowed_roles = tuple(allowed_roles)
        self.portal = portal
        self.fields['username'].label = 'Email or username'
        self.fields['username'].widget.attrs.update({'autocomplete': 'username', 'placeholder': ' ',
                                                     'autofocus': True})
        self.fields['password'].widget.attrs.update({'autocomplete': 'current-password', 'placeholder': ' '})
        for f in self.fields.values():
            f.widget.attrs['class'] = 'form-control'

    def clean(self):
        ident = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if ident and password:
            ip = throttle.client_ip(self.request)
            if throttle.is_locked(ident, ip):
                raise ValidationError('Too many failed attempts. Please wait 15 minutes and try again.',
                                      code='locked')
            self.user_cache = authenticate(self.request, username=ident, password=password)
            if self.user_cache is None:
                throttle.register_failure(ident, ip)
                raise self.get_invalid_login_error()
            throttle.clear(ident, ip)
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role not in self.allowed_roles:
            right = ROLE_PORTAL.get(user.role, 'customer')
            label, url = LOGIN_LABELS[right]
            raise ValidationError(f'This account belongs to a different door. Please use the {label} page: {url}',
                                  code='wrong_portal')


class PasswordFieldsMixin:
    def clean_passwords(self):
        p1, p2 = self.cleaned_data.get('password1'), self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'The two passwords do not match.')
        return p1


class CustomerSignupForm(PasswordFieldsMixin, BootstrapMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False, help_text='Used for M-Pesa and delivery updates')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    accept_terms = forms.BooleanField(label='I agree to the terms and privacy policy')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists. Try signing in.')
        return email

    def clean(self):
        data = super().clean()
        p1 = self.clean_passwords()
        if p1:
            probe = User(first_name=data.get('first_name', ''), last_name=data.get('last_name', ''),
                         email=data.get('email', ''))
            try:
                validate_password(p1, probe)
            except ValidationError as e:
                self.add_error('password1', e)
        return data

    def save(self):
        d = self.cleaned_data
        username = unique_username(d['email'].split('@')[0], lambda u: User.objects.filter(username__iexact=u).exists())
        user = User(username=username, email=d['email'], first_name=d['first_name'], last_name=d['last_name'],
                    phone=d.get('phone', ''), role=Role.CUSTOMER)
        user.set_password(d['password1'])
        user.save()
        return user


class SellerSignupForm(CustomerSignupForm):
    shop_name = forms.CharField(max_length=80, label='Shop name')
    city = forms.CharField(max_length=80)
    field_order = ['first_name', 'last_name', 'email', 'phone', 'shop_name', 'city',
                   'password1', 'password2', 'accept_terms']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError('A phone number is required so customers and couriers can reach you.')
        return phone

    def save(self):
        d = self.cleaned_data
        username = unique_username(d['email'].split('@')[0], lambda u: User.objects.filter(username__iexact=u).exists())
        user = User(username=username, email=d['email'], first_name=d['first_name'], last_name=d['last_name'],
                    phone=d['phone'], role=Role.SELLER_OWNER)
        user.set_password(d['password1'])
        user.save()
        Shop.objects.create(
            owner=user, name=d['shop_name'], city=d['city'], phone=d['phone'], contact_email=d['email'],
            status=ShopStatus.ACTIVE if settings.SHOP_AUTO_APPROVE else ShopStatus.PENDING)
        return user


class PasswordResetRequestForm(BootstrapMixin, forms.Form):
    identifier = forms.CharField(label='Email or username', max_length=254)


class ProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'bio', 'avatar']


class AddressForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Address
        fields = ['label', 'full_name', 'phone', 'line1', 'city', 'county', 'lat', 'lng', 'is_default']
        widgets = {'lat': forms.HiddenInput(), 'lng': forms.HiddenInput()}


# ---------------------------------------------------------------- staff creation
class StaffCreateForm(BootstrapMixin, forms.Form):
    """Used by administrators (platform staff) and by shop owners/managers (shop staff).
    The username and company e-mail are generated from name and position."""
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    position = forms.ChoiceField(choices=[])
    job_title = forms.CharField(max_length=80, required=False, help_text='Leave empty to use the position name')
    personal_email = forms.EmailField(help_text='The sign-in details are sent here. It is not the login.')
    phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop
        if shop is None:
            self.fields['position'].choices = [(r, r.replace('_', ' ').title()) for r in PLATFORM_CODES]
        else:
            self.fields['position'].choices = MemberRole.choices

    def preview_domain(self):
        return f'{domain_part(self.shop.slug)}.{settings.COMPANY_DOMAIN}' if self.shop else settings.COMPANY_DOMAIN

    def save(self, created_by):
        from django.db import transaction
        from shops.models import ShopMember
        d = self.cleaned_data
        position = d['position']
        code = (SHOP_CODES if self.shop else PLATFORM_CODES)[position]
        domain = self.preview_domain()
        username, email = build_identity(
            d['first_name'], d['last_name'], code, domain,
            lambda u, e: User.objects.filter(username__iexact=u).exists() or User.objects.filter(email__iexact=e).exists())
        password = temp_password()
        role = Role.SELLER_STAFF if self.shop else position
        title = d.get('job_title') or (SHOP_ROLE_TITLES[position] if self.shop else position.replace('_', ' ').title())
        with transaction.atomic():
            user = User(username=username, email=email, first_name=d['first_name'], last_name=d['last_name'],
                        phone=d.get('phone', ''), role=role, email_verified=True, must_change_password=True)
            user.set_password(password)
            user.save()
            n = StaffProfile.objects.count() + 1
            prefix = f'SH{self.shop.pk}' if self.shop else 'NY'
            StaffProfile.objects.create(user=user, job_title=title, personal_email=d['personal_email'],
                                        employee_no=f'{prefix}-{n:04d}', created_by=created_by,
                                        department=self.shop.name if self.shop else 'Nyota HQ')
            if self.shop:
                ShopMember.objects.create(shop=self.shop, user=user, role=position)
        return user, password
