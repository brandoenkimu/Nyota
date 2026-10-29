import random
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class OrderStatus(models.TextChoices):
    PLACED = 'placed', 'Placed'
    IN_PROGRESS = 'in_progress', 'In progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PENDING = 'pending', 'Awaiting payment'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class PaymentMethod(models.TextChoices):
    MPESA = 'mpesa', 'M-Pesa'
    STRIPE = 'stripe', 'Card (Stripe)'
    COD = 'cod', 'Pay on delivery'


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    percent = models.PositiveSmallIntegerField(default=10)
    min_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_until = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=0, help_text='0 = unlimited')
    used = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.code} (-{self.percent}%)'

    def is_valid_for(self, total):
        if not self.active:
            return False
        if self.valid_until and self.valid_until < timezone.localdate():
            return False
        if self.usage_limit and self.used >= self.usage_limit:
            return False
        return total >= self.min_total


def _new_number():
    return f'NY{timezone.localdate():%y%m%d}-{random.randint(0, 99999):05d}'


class Order(models.Model):
    number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=12, choices=OrderStatus.choices, default=OrderStatus.PLACED, db_index=True)
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID,
                                      db_index=True)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.MPESA)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)

    # delivery address, copied at checkout so later edits never rewrite history
    ship_name = models.CharField(max_length=120)
    ship_phone = models.CharField(max_length=20)
    ship_line1 = models.CharField(max_length=200)
    ship_city = models.CharField(max_length=80)
    ship_county = models.CharField(max_length=80, blank=True)
    ship_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ship_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    placed_at = models.DateTimeField(default=timezone.now, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-placed_at']

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            number = _new_number()
            while Order.objects.filter(number=number).exists():
                number = _new_number()
            self.number = number
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('portals:order_detail', args=[self.number])

    @property
    def ship_address(self):
        parts = [self.ship_line1, self.ship_city, self.ship_county]
        return ', '.join(p for p in parts if p)

    @property
    def has_ship_point(self):
        return self.ship_lat is not None and self.ship_lng is not None

    def refresh_status(self, save=True):
        """Derive the overall status from the per-shop parts."""
        states = list(self.shop_orders.values_list('status', flat=True))
        if not states:
            return
        if all(s == ShopOrderStatus.CANCELLED for s in states):
            new = OrderStatus.CANCELLED
        elif all(s in (ShopOrderStatus.DELIVERED, ShopOrderStatus.CANCELLED, ShopOrderStatus.RETURNED) for s in states):
            new = OrderStatus.COMPLETED
        elif any(s != ShopOrderStatus.PENDING for s in states):
            new = OrderStatus.IN_PROGRESS
        else:
            new = OrderStatus.PLACED
        if new != self.status:
            self.status = new
            if save:
                self.save(update_fields=['status'])


class ShopOrderStatus(models.TextChoices):
    PENDING = 'pending', 'Order received'
    CONFIRMED = 'confirmed', 'Confirmed by seller'
    PACKED = 'packed', 'Packed'
    SHIPPED = 'shipped', 'Shipped'
    OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for delivery'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'
    RETURNED = 'returned', 'Returned'


# the happy path, used for progress bars and for validating status changes
FLOW = ['pending', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']


class ShopOrder(models.Model):
    """The part of an order that belongs to one seller. Each seller ships and is paid separately."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='shop_orders')
    shop = models.ForeignKey('shops.Shop', on_delete=models.PROTECT, related_name='shop_orders')
    status = models.CharField(max_length=20, choices=ShopOrderStatus.choices, default=ShopOrderStatus.PENDING,
                              db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    seller_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    courier = models.CharField(max_length=60, blank=True)
    tracking_number = models.CharField(max_length=60, blank=True)
    expected_delivery = models.DateField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('order', 'shop')]

    def __str__(self):
        return f'{self.order.number} / {self.shop}'

    @property
    def total(self):
        return self.subtotal + self.shipping_fee - self.discount

    @property
    def flow_index(self):
        try:
            return FLOW.index(self.status)
        except ValueError:
            return -1

    @property
    def is_closed(self):
        return self.status in (ShopOrderStatus.DELIVERED, ShopOrderStatus.CANCELLED, ShopOrderStatus.RETURNED)

    def next_status(self):
        i = self.flow_index
        return FLOW[i + 1] if 0 <= i < len(FLOW) - 1 else None


class OrderItem(models.Model):
    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', null=True, on_delete=models.SET_NULL, related_name='order_items')
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class TrackingEvent(models.Model):
    shop_order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, choices=ShopOrderStatus.choices)
    title = models.CharField(max_length=120)
    detail = models.CharField(max_length=300, blank=True)
    location_label = models.CharField(max_length=120, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='tracking_events')

    class Meta:
        ordering = ['occurred_at', 'id']


class PayoutStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    APPROVED = 'approved', 'Approved'
    PAID = 'paid', 'Paid'
    REJECTED = 'rejected', 'Rejected'


class Payout(models.Model):
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, default='M-Pesa')
    destination = models.CharField(max_length=60, blank=True, help_text='Phone number or account')
    status = models.CharField(max_length=10, choices=PayoutStatus.choices, default=PayoutStatus.REQUESTED)
    reference = models.CharField(max_length=60, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='payouts_processed')

    class Meta:
        ordering = ['-requested_at']


def split_commission(subtotal: Decimal, percent: Decimal) -> tuple:
    """(commission, seller_earnings) on a shop's subtotal, rounded to cents."""
    commission = (subtotal * percent / Decimal(100)).quantize(Decimal('0.01'))
    return commission, subtotal - commission
