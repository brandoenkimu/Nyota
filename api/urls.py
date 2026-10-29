from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('shops', views.ShopViewSet, basename='shop')
router.register('orders', views.MyOrdersViewSet, basename='order')

urlpatterns = [
    path('v1/', include(router.urls)),
    path('v1/me/', views.me),
    path('health/', views.health),
]
