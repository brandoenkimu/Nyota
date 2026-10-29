from django.contrib import admin

from .models import Payment, WebhookLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'method', 'state', 'amount', 'receipt', 'simulated')
    list_filter = ('method', 'state', 'simulated')
    search_fields = ('order__number', 'receipt', 'phone')


admin.site.register(WebhookLog)
