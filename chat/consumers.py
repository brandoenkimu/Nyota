import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from . import services
from .models import Conversation


class ChatConsumer(AsyncWebsocketConsumer):
    """One socket per open conversation. All writes go through chat.services, which persists first
    and then broadcasts to everyone in the room (across processes, via the channel layer)."""

    async def connect(self):
        self.user = self.scope.get('user')
        self.conv_id = int(self.scope['url_route']['kwargs']['conv_id'])
        if not self.user or not self.user.is_authenticated or not await self._allowed():
            await self.close(code=4403)
            return
        self.group = f'chat_{self.conv_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group = getattr(self, 'group', None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    @database_sync_to_async
    def _allowed(self):
        conv = Conversation.objects.filter(pk=self.conv_id).select_related('shop').first()
        return bool(conv and services.can_access(self.user, conv))

    @database_sync_to_async
    def _handle(self, data):
        kind = data.get('type')
        conv = Conversation.objects.select_related('shop').get(pk=self.conv_id)
        try:
            if kind == 'send':
                msg = services.send_message(self.user, conv, data.get('body', ''), data.get('reply_to') or None,
                                            data.get('client_id') or None)
                return {'type': 'ack', 'client_id': data.get('client_id', ''), 'id': msg.id}
            if kind == 'react':
                services.toggle_reaction(self.user, int(data.get('message_id', 0)), data.get('emoji', ''))
                return None
            if kind == 'delete':
                services.delete_message(self.user, int(data.get('message_id', 0)))
                return None
            if kind == 'read':
                services.mark_read(self.user, conv)
                return None
        except services.ChatError as exc:
            return {'type': 'error', 'message': str(exc), 'client_id': data.get('client_id', '')}
        except (ValueError, TypeError):
            return {'type': 'error', 'message': 'Bad request.'}
        except Exception:
            return {'type': 'error', 'message': 'Something went wrong. Please try again.',
                    'client_id': data.get('client_id', '')}
        return None

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or len(text_data) > 8000:
            return
        try:
            data = json.loads(text_data)
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        reply = await self._handle(data)
        if reply:
            await self.send(text_data=json.dumps(reply))

    async def chat_event(self, event):
        await self.send(text_data=json.dumps({'type': event['event'], **{'data': event['data']}}))
