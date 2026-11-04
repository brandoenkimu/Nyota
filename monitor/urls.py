from django.urls import path

from . import views

app_name = 'monitor'
urlpatterns = [path('api/client-error/', views.client_error, name='client_error')]
