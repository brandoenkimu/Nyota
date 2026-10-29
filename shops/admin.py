from django.contrib import admin

from .models import Shop, ShopMember


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'city', 'status', 'is_verified', 'rating_avg', 'created_at')
    list_filter = ('status', 'is_verified', 'county')
    search_fields = ('name', 'owner__email', 'city')
    prepopulated_fields = {'slug': ('name',)}


admin.site.register(ShopMember)
