from django.conf import settings
from django.db import models
from django.utils import timezone


class PromotionPlan(models.Model):
    """A paid advertising package a seller can buy to get their shop on the home-page slides."""
    name = models.CharField(max_length=60)
    days = models.PositiveSmallIntegerField(help_text='How many days the shop stays featured.')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True, help_text='Sellers can only buy an active plan.')
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort', 'days']

    def __str__(self):
        return f'{self.name} ({self.days} days, {self.price})'


class PromotionStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', 'Waiting for payment'
    ACTIVE = 'active', 'Live on the home page'
    EXPIRED = 'expired', 'Expired'
    CANCELLED = 'cancelled', 'Cancelled'


class Promotion(models.Model):
    """One purchase of a featured slot. While active, `slide` points at the HeroSlide built from it."""
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='promotions')
    plan = models.ForeignKey(PromotionPlan, on_delete=models.PROTECT, related_name='promotions')
    status = models.CharField(max_length=16, choices=PromotionStatus.choices, default=PromotionStatus.PENDING_PAYMENT,
                              db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)             # snapshot of the plan price paid
    payment_method = models.CharField(max_length=10, blank=True)
    slide = models.OneToOneField('core.HeroSlide', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='promotion')
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.shop.name} featured for {self.plan.days}d ({self.status})'

    @property
    def is_live(self):
        return self.status == PromotionStatus.ACTIVE and self.ends_at and self.ends_at > timezone.now()

    @property
    def days_left(self):
        if not self.is_live:
            return 0
        return max(0, (self.ends_at - timezone.now()).days)
