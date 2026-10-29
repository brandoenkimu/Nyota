from datetime import date, datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Role(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    SELLER_OWNER = 'seller_owner', 'Seller (shop owner)'
    SELLER_STAFF = 'seller_staff', 'Seller staff'
    ADMIN = 'admin', 'Administrator'
    ANALYST = 'analyst', 'Analyst'
    DEVELOPER = 'developer', 'Developer'
    CEO = 'ceo', 'CEO'
    SUPPORT = 'support', 'Support agent'


PLATFORM_ROLES = (Role.ADMIN, Role.ANALYST, Role.DEVELOPER, Role.CEO, Role.SUPPORT)
SELLER_ROLES = (Role.SELLER_OWNER, Role.SELLER_STAFF)

HOME_URLS = {
    Role.CUSTOMER: 'portals:customer_home',
    Role.SELLER_OWNER: 'portals:seller_home',
    Role.SELLER_STAFF: 'portals:seller_home',
    Role.ADMIN: 'portals:admin_home',
    Role.ANALYST: 'portals:analyst_home',
    Role.DEVELOPER: 'portals:developer_home',
    Role.CEO: 'portals:ceo_home',
    Role.SUPPORT: 'portals:support_home',
}


class NyotaUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra):
        """`createsuperuser` makes an Administrator who can use the staff door and the Django admin."""
        extra.setdefault('role', Role.ADMIN)
        extra.setdefault('email_verified', True)
        return super().create_superuser(username, email, password, **extra)


class User(AbstractUser):
    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    bio = models.CharField(max_length=240, blank=True)
    email_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    theme = models.CharField(max_length=20, default='auto')
    accent = models.CharField(max_length=20, default='violet')
    last_seen = models.DateTimeField(null=True, blank=True)

    objects = NyotaUserManager()

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

    @property
    def initials(self):
        parts = (self.get_full_name() or self.username).replace('.', ' ').split()
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    @property
    def is_platform_staff(self):
        return self.role in PLATFORM_ROLES

    @property
    def is_seller_side(self):
        return self.role in SELLER_ROLES

    @property
    def notification_email(self):
        """Staff sign in with a generated company identity, but mail goes to their personal address."""
        profile = getattr(self, 'staff_profile', None)
        return (profile.personal_email if profile and profile.personal_email else self.email)

    @property
    def shop(self):
        """The shop this person owns or works for (None for everyone else)."""
        if self.role == Role.SELLER_OWNER:
            return getattr(self, 'owned_shop', None)
        if self.role == Role.SELLER_STAFF:
            membership = getattr(self, 'shop_membership', None)
            return membership.shop if membership and membership.active else None
        return None

    @property
    def home_url(self):
        return reverse(HOME_URLS.get(self.role, 'core:home'))


class StaffProfile(models.Model):
    """Extra details for platform staff and for the staff of a shop."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    job_title = models.CharField(max_length=80)
    employee_no = models.CharField(max_length=30, unique=True)
    department = models.CharField(max_length=80, blank=True)
    personal_email = models.EmailField(blank=True)
    hired_on = models.DateField(default=date.today)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='staff_created')

    def __str__(self):
        return f'{self.user} ({self.job_title})'


class Attendance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=timezone.localdate)
    clock_in = models.DateTimeField(default=timezone.now)
    clock_out = models.DateTimeField(null=True, blank=True)
    late = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = [('user', 'date')]
        ordering = ['-date', '-clock_in']
        indexes = [models.Index(fields=['date'])]

    @property
    def hours(self):
        end = self.clock_out or timezone.now()
        return round((end - self.clock_in).total_seconds() / 3600, 2)

    @property
    def is_open(self):
        return self.clock_out is None


class SocialAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='social_accounts')
    provider = models.CharField(max_length=20)
    uid = models.CharField(max_length=190)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('provider', 'uid')]


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=40, default='Home')
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    line1 = models.CharField('Street / building', max_length=200)
    city = models.CharField(max_length=80)
    county = models.CharField(max_length=80, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', 'id']

    def __str__(self):
        return f'{self.label}: {self.line1}, {self.city}'
