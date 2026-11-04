from django.contrib import admin

from .models import ActivityEvent, ErrorEvent, ErrorGroup


@admin.register(ErrorGroup)
class ErrorGroupAdmin(admin.ModelAdmin):
    list_display = ['exc_type', 'message', 'count', 'users_affected', 'status', 'last_seen']
    list_filter = ['status', 'source']
    search_fields = ['message', 'location']


@admin.register(ErrorEvent)
class ErrorEventAdmin(admin.ModelAdmin):
    list_display = ['reference', 'created_at', 'user_label', 'path', 'status_code']
    search_fields = ['reference', 'user_label', 'path']


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'kind', 'user', 'path', 'device']
    list_filter = ['kind', 'device']
