from django.db.models import Q
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog.models import Product
from catalog.search import search_products
from orders.models import Order, ShopOrder
from shops.models import Shop, ShopStatus


class ShopSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ['id', 'name', 'slug', 'tagline', 'city', 'county', 'lat', 'lng', 'rating_avg', 'rating_count',
                  'is_verified', 'url']

    def get_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.get_absolute_url())


class ProductSerializer(serializers.ModelSerializer):
    shop = serializers.CharField(source='shop.slug', read_only=True)
    category = serializers.CharField(source='category.slug', read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'brand', 'price', 'compare_at_price', 'stock', 'in_stock', 'shop',
                  'category', 'rating_avg', 'rating_count', 'image_url', 'url']

    def get_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.get_absolute_url())


class ShopOrderSerializer(serializers.ModelSerializer):
    number = serializers.CharField(source='order.number')
    shop = serializers.CharField(source='shop.slug')
    payment_status = serializers.CharField(source='order.payment_status')
    placed_at = serializers.DateTimeField(source='order.placed_at')
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    events = serializers.SerializerMethodField()

    class Meta:
        model = ShopOrder
        fields = ['id', 'number', 'shop', 'status', 'payment_status', 'placed_at', 'total', 'courier',
                  'tracking_number', 'expected_delivery', 'events']

    def get_events(self, obj):
        return [{'status': e.status, 'title': e.title, 'at': e.occurred_at, 'location': e.location_label}
                for e in obj.events.all()]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        qs = (Product.objects.filter(is_active=True, shop__status=ShopStatus.ACTIVE)
              .select_related('shop', 'category'))
        p = self.request.query_params
        if p.get('shop'):
            qs = qs.filter(shop__slug=p['shop'])
        if p.get('category'):
            qs = qs.filter(category__slug=p['category'])
        return search_products(qs, p.get('q')) if p.get('q') else qs.order_by('-sold')


class ShopViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShopSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'
    queryset = Shop.objects.filter(status=ShopStatus.ACTIVE)


class MyOrdersViewSet(viewsets.ReadOnlyModelViewSet):
    """Customers see their own orders; sellers see their shop's orders; admins see everything."""
    serializer_class = ShopOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = ShopOrder.objects.select_related('order', 'shop').prefetch_related('events')
        if u.role == 'admin':
            return qs
        if u.shop:
            return qs.filter(shop=u.shop)
        return qs.filter(order__customer=u)


@api_view(['GET'])
def me(request):
    u = request.user
    if not u.is_authenticated:
        return Response({'authenticated': False})
    return Response({'authenticated': True, 'username': u.username, 'role': u.role, 'name': u.display_name,
                     'shop': u.shop.slug if u.shop else None})


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok'})
