from django.contrib import admin

from .models import Category, Product, ProductImage, Review, Wishlist


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'category', 'price', 'stock', 'is_active', 'sold')
    list_filter = ('is_active', 'is_featured', 'category')
    search_fields = ('name', 'brand', 'sku', 'shop__name')
    inlines = [ImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'sort')
    prepopulated_fields = {'slug': ('name',)}


admin.site.register(Review)
admin.site.register(Wishlist)
