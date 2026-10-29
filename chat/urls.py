from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('chat/', views.inbox, name='inbox'),
    path('chat/<int:pk>/', views.inbox, name='thread'),
    path('chat/api/<int:pk>/messages/', views.history, name='history'),
    path('chat/api/<int:pk>/send/', views.send, name='send'),
    path('chat/api/message/<int:message_id>/react/', views.react, name='react'),
    path('chat/api/message/<int:message_id>/delete/', views.delete, name='delete'),
    path('chat/start/shop/<slug:slug>/', views.start_shop, name='start_shop'),
    path('chat/new/', views.new_chat, name='new'),
    path('chat/start/team/', views.start_team, name='start_team'),
    path('chat/block/<int:pk>/', views.block_toggle, name='block'),
    path('chat/start/support/', views.start_support, name='start_support'),
    path('chat/start/user/<int:pk>/', views.start_user, name='start_user'),
]
