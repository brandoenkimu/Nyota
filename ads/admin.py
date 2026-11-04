from django.contrib import admin

from .models import Promotion, PromotionPlan


@admin.register(PromotionPlan)
class PromotionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'days', 'price', 'active', 'sort']
    list_editable = ['active', 'sort']


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['shop', 'plan', 'status', 'amount', 'starts_at', 'ends_at']
    list_filter = ['status']
    readonly_fields = ['status', 'starts_at', 'ends_at', 'slide']   # decisions happen in services.py, so they're audited
