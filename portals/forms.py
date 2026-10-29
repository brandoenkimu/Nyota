from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from accounts.forms import BootstrapMixin
from catalog.models import Category, Product
from core.models import HeroSlide
from orders.models import Coupon, Payout
from shops.models import Shop

User = get_user_model()
MAX_IMAGE = 5 * 1024 * 1024


def _check_image(f):
    if f and hasattr(f, 'size') and f.size > MAX_IMAGE:
        raise forms.ValidationError('Please upload an image smaller than 5 MB.')
    return f


class ProductForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'brand', 'sku', 'description', 'tags', 'price', 'compare_at_price',
                  'cost_price', 'stock', 'low_stock_threshold', 'weight_kg', 'image', 'is_active', 'is_featured']
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def clean_image(self):
        return _check_image(self.cleaned_data.get('image'))

    def clean(self):
        data = super().clean()
        price, compare = data.get('price'), data.get('compare_at_price')
        if price is not None and price <= 0:
            self.add_error('price', 'Price must be more than zero.')
        if price and compare and compare <= price:
            self.add_error('compare_at_price', 'The "was" price should be higher than the selling price.')
        return data


class ShopProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'tagline', 'about', 'brand_color', 'logo', 'banner', 'phone', 'contact_email', 'whatsapp',
                  'website', 'instagram', 'facebook', 'tiktok', 'address', 'city', 'county', 'lat', 'lng',
                  'opening_hours', 'shipping_fee', 'free_shipping_over', 'return_policy']
        widgets = {
            'about': forms.Textarea(attrs={'rows': 5}),
            'opening_hours': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mon-Fri 08:00-18:00\nSat 09:00-15:00'}),
            'return_policy': forms.Textarea(attrs={'rows': 3}),
            'brand_color': forms.TextInput(attrs={'type': 'color'}),
            'lat': forms.NumberInput(attrs={'step': 'any'}), 'lng': forms.NumberInput(attrs={'step': 'any'}),
        }

    def clean_logo(self):
        return _check_image(self.cleaned_data.get('logo'))

    def clean_banner(self):
        return _check_image(self.cleaned_data.get('banner'))

    def clean_brand_color(self):
        c = self.cleaned_data['brand_color']
        if not (len(c) == 7 and c.startswith('#') and all(ch in '0123456789abcdefABCDEF' for ch in c[1:])):
            raise forms.ValidationError('Pick a colour.')
        return c


class ReplyForm(BootstrapMixin, forms.Form):
    reply = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows': 2}))


class PayoutRequestForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Payout
        fields = ['amount', 'method', 'destination']

    def __init__(self, *args, available=Decimal('0'), **kwargs):
        super().__init__(*args, **kwargs)
        self.available = available

    def clean_amount(self):
        a = self.cleaned_data['amount']
        if a <= 0:
            raise forms.ValidationError('Enter an amount above zero.')
        if a > self.available:
            raise forms.ValidationError('That is more than your available balance.')
        return a


# --------------------------------------------------------------------- admin
class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'parent', 'description', 'sort']


class CouponForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'percent', 'min_total', 'valid_until', 'usage_limit', 'active']
        widgets = {'valid_until': forms.DateInput(attrs={'type': 'date'})}

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

    def clean_percent(self):
        p = self.cleaned_data['percent']
        if not 1 <= p <= 90:
            raise forms.ValidationError('Choose a percentage between 1 and 90.')
        return p


class SlideForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = ['kicker', 'title', 'subtitle', 'cta_label', 'cta_url', 'art_variant', 'sort', 'active']


class ShopAdminForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['status', 'is_verified', 'commission_override']


class UserAdminForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'is_active', 'email_verified']
