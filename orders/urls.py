from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('cart/coupon/', views.cart_coupon, name='cart_coupon'),
    path('checkout/', views.checkout, name='checkout'),
    path('pay/<str:number>/', views.pay, name='pay'),
    path('pay/<str:number>/status/', views.pay_status, name='pay_status'),
    path('pay/<str:number>/cancel/', views.pay_cancel, name='pay_cancel'),
    path('pay/<str:number>/retry/', views.pay_retry, name='pay_retry'),
    path('pay/<str:number>/simulate/', views.simulate, name='simulate'),
    path('pay/<str:number>/stripe-return/', views.stripe_return, name='stripe_return'),
]
