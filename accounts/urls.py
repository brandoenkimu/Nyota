from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

from . import oauth, views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.PortalLoginView.as_view(portal='customer'), name='login'),
    path('seller/login/', views.PortalLoginView.as_view(portal='seller'), name='seller_login'),
    path('staff/login/', views.PortalLoginView.as_view(portal='staff'), name='staff_login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.CustomerSignupView.as_view(), name='signup'),
    path('seller/signup/', views.SellerSignupView.as_view(), name='seller_signup'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('account/verify/resend/', views.resend_verification, name='resend_verification'),

    path('password/reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password/reset/sent/', TemplateView.as_view(template_name='accounts/password_reset_done.html'),
         name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', views.PasswordResetConfirm.as_view(), name='password_reset_confirm'),
    path('password/reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
         name='password_reset_complete'),
    path('account/password/', views.PasswordChange.as_view(), name='password_change'),
    path('account/password/done/', views.password_change_done, name='password_change_done'),

    path('oauth/<str:provider>/start/', oauth.start, name='oauth_start'),
    path('oauth/<str:provider>/callback/', oauth.callback, name='oauth_callback'),
    path('attendance/clock/', views.clock, name='clock'),
]
