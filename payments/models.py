from django.db import models
from django.utils import timezone


class PaymentState(models.TextChoices):
    INITIATED = 'initiated', 'Initiated'
    PENDING = 'pending', 'Waiting for customer'
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class Payment(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    method = models.CharField(max_length=10)
    state = models.CharField(max_length=12, choices=PaymentState.choices, default=PaymentState.INITIATED, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    phone = models.CharField(max_length=20, blank=True)
    # M-Pesa
    merchant_request_id = models.CharField(max_length=60, blank=True)
    checkout_request_id = models.CharField(max_length=60, blank=True, db_index=True)
    receipt = models.CharField(max_length=40, blank=True)
    # Stripe
    stripe_session_id = models.CharField(max_length=120, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)
    simulated = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=200, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.method} {self.amount} {self.state}'


class WebhookLog(models.Model):
    provider = models.CharField(max_length=20)
    payload = models.TextField()
    signature_ok = models.BooleanField(default=True)
    handled = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-received_at']
