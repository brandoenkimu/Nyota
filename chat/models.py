from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ConversationKind(models.TextChoices):
    SHOP = 'shop', 'Customer and shop'
    SUPPORT = 'support', 'Support'
    DIRECT = 'direct', 'Direct'
    TEAM = 'team', 'Shop team'


class Conversation(models.Model):
    kind = models.CharField(max_length=10, choices=ConversationKind.choices, default=ConversationKind.DIRECT)
    subject = models.CharField(max_length=140, blank=True)
    shop = models.ForeignKey('shops.Shop', null=True, blank=True, on_delete=models.CASCADE,
                             related_name='conversations')
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='conversations')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through='Participant',
                                          related_name='conversations')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.subject or f'Conversation {self.pk}'


class Participant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_memberships')
    last_read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('conversation', 'user')]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_messages')
    body = models.CharField(max_length=2000, blank=True)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    client_id = models.UUIDField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['sender', 'client_id'], condition=Q(client_id__isnull=False),
                                               name='uniq_sender_client_message')]

    @property
    def deleted(self):
        return self.deleted_at is not None


class Reaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_reactions')
    emoji = models.CharField(max_length=16)

    class Meta:
        unique_together = [('message', 'user', 'emoji')]


class Block(models.Model):
    """One person stops another from starting or continuing a direct chat with them."""
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_blocks')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_blocked_by')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('blocker', 'blocked')]
