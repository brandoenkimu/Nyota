from django.contrib import admin

from .models import Conversation, Message, Participant, Reaction

admin.site.register(Conversation)
admin.site.register(Participant)
admin.site.register(Reaction)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'created_at', 'deleted_at')
    list_filter = ('created_at',)