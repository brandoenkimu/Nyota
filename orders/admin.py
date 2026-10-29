from django.contrib import admin

from .models import Coupon, Order, OrderItem, Payout, ShopOrder, TrackingEvent


class ShopOrderInline(admin.TabularInline):
    model = ShopOrder
    extra = 0
    show_change_link = True


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'status', 'payment_status', 'total', 'placed_at')
    list_filter = ('status', 'payment_status', 'payment_method')
    search_fields = ('number', 'customer__email', 'ship_phone')
    inlines = [ShopOrderInline]


class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class EventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0


@admin.register(ShopOrder)
class ShopOrderAdmin(admin.ModelAdmin):
    list_display = ('order', 'shop', 'status', 'subtotal', 'commission_amount')
    list_filter = ('status',)
    inlines = [ItemInline, EventInline]


admin.site.register(Coupon)
admin.site.register(Payout)
