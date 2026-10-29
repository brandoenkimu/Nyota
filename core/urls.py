from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='products'),
    path('category/<slug:slug>/', views.category_page, name='category'),
    path('p/<slug:slug>/', views.product_detail, name='product'),
    path('shops/', views.shop_directory, name='shops'),
    path('shop/<slug:slug>/', views.shop_site, name='shop'),
    path('shop/<slug:slug>/follow/', views.shop_follow, name='shop_follow'),
    path('wishlist/toggle/<int:pk>/', views.wishlist_toggle, name='wishlist_toggle'),
    path('review/<int:pk>/', views.review_add, name='review_add'),
    path('api/search/', views.search_suggest, name='search_suggest'),
    path('api/theme/', views.save_theme, name='save_theme'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read/', views.notifications_read, name='notifications_read'),
    path('track/', views.track_lookup, name='track'),
    path('about/', views.about, name='about'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
]
