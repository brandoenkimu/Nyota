from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class ShopStatus(models.TextChoices):
    PENDING = 'pending', 'Awaiting approval'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'


class Shop(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_shop')
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=60, unique=True)
    tagline = models.CharField(max_length=140, blank=True)
    about = models.TextField(blank=True)
    logo = models.ImageField(upload_to='shops/logos/', blank=True)
    banner = models.ImageField(upload_to='shops/banners/', blank=True)
    brand_color = models.CharField('Brand colour', max_length=7, default='#8b5cf6')

    phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    instagram = models.CharField(max_length=60, blank=True)
    facebook = models.CharField(max_length=60, blank=True)
    tiktok = models.CharField(max_length=60, blank=True)

    address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    county = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=60, default='Kenya')
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    opening_hours = models.TextField(blank=True, help_text='One line per day, e.g. "Mon-Fri 08:00-18:00"')

    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('250'))
    free_shipping_over = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    return_policy = models.TextField(blank=True)

    status = models.CharField(max_length=12, choices=ShopStatus.choices, default=ShopStatus.PENDING, db_index=True)
    is_verified = models.BooleanField(default=False)
    commission_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                              help_text='Percent. Leave empty to use the platform default.')
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    followers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='followed_shops')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:50] or 'shop'
            slug, n = base, 2
            while Shop.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:shop', args=[self.slug])

    @property
    def commission_percent(self):
        if self.commission_override is not None:
            return self.commission_override
        return Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))

    @property
    def is_public(self):
        return self.status == ShopStatus.ACTIVE

    @property
    def has_location(self):
        return self.lat is not None and self.lng is not None

    @property
    def hours_lines(self):
        return [ln.strip() for ln in self.opening_hours.splitlines() if ln.strip()]


class MemberRole(models.TextChoices):
    MANAGER = 'manager', 'Manager'
    CASHIER = 'cashier', 'Cashier / sales assistant'
    INVENTORY = 'inventory', 'Inventory clerk'
    SUPPORT = 'support', 'Customer support'
    ANALYST = 'analyst', 'Shop analyst'


class ShopMember(models.Model):
    """Staff of a seller (the 'assistants'). Each has a generated company identity."""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='members')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_membership')
    role = models.CharField(max_length=12, choices=MemberRole.choices, default=MemberRole.CASHIER)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shop', 'role']

    def __str__(self):
        return f'{self.user} @ {self.shop}'
