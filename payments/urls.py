from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('mpesa/callback/<str:token>/', views.mpesa_callback, name='mpesa_callback'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
]
