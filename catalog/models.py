from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)       # also selects the artwork, see core/art.py
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    description = models.CharField(max_length=200, blank=True)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    brand = models.CharField(max_length=80, blank=True)
    sku = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text='Comma separated')
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text='Private. Used for profit analytics.')
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    image_url = models.CharField(max_length=300, blank=True,
                                 help_text='Filled by the fetch_product_images command or pasted by hand.')
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    sold = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['shop', 'is_active']), models.Index(fields=['category', 'is_active'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or 'product'
            slug = base
            while Product.objects.filter(slug=slug).exists():
                slug = f'{base}-{get_random_string(4, "abcdefghjkmnpqrstuvwxyz23456789")}'
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:product', args=[self.slug])

    @property
    def real_image(self):
        """URL of a real photo if there is one; the templates fall back to generated artwork."""
        if self.image:
            return self.image.url
        return self.image_url or ''

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def low_stock(self):
        return 0 < self.stock <= self.low_stock_threshold

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int((self.compare_at_price - self.price) / self.compare_at_price * 100)
        return 0

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def margin(self):
        if self.cost_price is None:
            return None
        return self.price - self.cost_price


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/')
    alt = models.CharField(max_length=120, blank=True)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort', 'id']


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=100, blank=True)
    body = models.TextField(blank=True)
    sentiment = models.FloatField(default=0)
    seller_reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('product', 'user')]
        ordering = ['-created_at']


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'product')]
        ordering = ['-created_at']
