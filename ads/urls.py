from django.urls import path

from . import views

app_name = 'ads'
urlpatterns = [
    path('seller/advertise/', views.plans, name='plans'),
    path('seller/advertise/buy/<int:pk>/', views.buy, name='buy'),
    path('seller/advertise/pay/<int:pk>/', views.pay, name='pay'),
    path('seller/advertise/pay/<int:pk>/status/', views.pay_status, name='pay_status'),
    path('seller/advertise/pay/<int:pk>/simulate/', views.simulate, name='simulate'),
    path('seller/advertise/pay/<int:pk>/cancel/', views.cancel, name='cancel'),
    path('seller/advertise/pay/<int:pk>/stripe-return/', views.stripe_return, name='stripe_return'),
]
