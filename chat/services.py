import re
import unicodedata

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from core.notify import notify
from shops.permissions import shop_permissions

from .models import Block, Conversation, ConversationKind, Message, Participant, Reaction

MAX_BODY = 2000
RATE_LIMIT = 20            # messages
RATE_WINDOW = 10           # seconds
_CONTROL = re.compile(r'[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f‪-‮⁦-⁩]')


class ChatError(Exception):
    pass


def clean_text(text: str) -> str:
    text = unicodedata.normalize('NFC', text or '')
    return _CONTROL.sub('', text).strip()


def valid_emoji(value: str) -> bool:
    """One 'character' of at most 16 code points that is not plain letters or digits."""
    value = (value or '').strip()
    if not value or len(value) > 16:
        return False
    if all(c.isalnum() and ord(c) < 0x2000 for c in value):
        return False
    return not any(c in '<>&"\'' or c.isspace() for c in value)


# ------------------------------------------------------------------ access
def team_members(shop):
    """The owner and every active staff member of a shop."""
    return [shop.owner] + [m.user for m in shop.members.select_related('user').filter(active=True)]


def can_access(user, conv) -> bool:
    if not user.is_authenticated:
        return False
    if conv.kind == ConversationKind.TEAM:               # internal: only people who work in that shop
        return bool(user.shop and user.shop.pk == conv.shop_id)
    if conv.memberships.filter(user=user).exists():
        return True
    if conv.shop_id and user.shop and user.shop.pk == conv.shop_id and 'chat' in shop_permissions(user):
        return True                                       # shop staff with the chat permission share customer chats
    if user.role in ('admin', 'support') and conv.kind == ConversationKind.SUPPORT:
        return True
    return False


def conversations_for(user):
    q = Q(memberships__user=user) & ~Q(kind=ConversationKind.TEAM)
    shop = user.shop
    if shop:
        q |= Q(kind=ConversationKind.TEAM, shop=shop)
        if 'chat' in shop_permissions(user):
            q |= Q(shop=shop) & ~Q(kind=ConversationKind.TEAM)
    if user.role in ('admin', 'support'):
        q |= Q(kind=ConversationKind.SUPPORT)
    return (Conversation.objects.filter(q).distinct().select_related('shop')
            .prefetch_related('memberships__user').order_by('-updated_at'))


def ensure_participant(user, conv):
    """People who can see a chat through their shop role get a read marker too, so unread counts work."""
    Participant.objects.get_or_create(conversation=conv, user=user, defaults={'last_read_at': conv.created_at})


# --------------------------------------------------- who may message whom
HELP_ROLES = ('admin', 'support')


def is_blocked(a, b) -> bool:
    return Block.objects.filter(Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)).exists()


def can_message(me, other) -> bool:
    if me.pk == other.pk or not other.is_active:
        return False
    if me.role in HELP_ROLES or other.role in HELP_ROLES:
        return True                                       # the Nyota team can always be reached (and can reach anyone)
    if is_blocked(me, other):
        return False
    if me.is_platform_staff:
        return other.is_platform_staff
    if me.is_seller_side:
        mine, theirs = me.shop, other.shop
        if mine and theirs and mine.pk == theirs.pk:
            return True                                   # owner <-> staff <-> staff
        if mine and other.role == 'customer':
            from orders.models import Order
            return (Order.objects.filter(customer=other, shop_orders__shop=mine).exists()
                    or Conversation.objects.filter(kind=ConversationKind.SHOP, shop=mine,
                                                   memberships__user=other).exists())
        return False
    if me.role == 'customer':
        return other.role == 'customer'                   # customers reach shops through the shop page
    return False


def find_people(me, q):
    """Everyone `me` may start a chat with that matches the search text, grouped for the new-chat page."""
    from django.contrib.auth import get_user_model
    from shops.models import Shop, ShopStatus
    User = get_user_model()
    q = (q or '').strip()
    out = {'team': [], 'customers': [], 'people': [], 'shops': []}

    def by_text(qs):
        if not q:
            return qs
        return qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q)
                         | Q(email__icontains=q))

    if me.shop:
        out['team'] = [u for u in team_members(me.shop) if u.pk != me.pk and
                       (not q or q.lower() in f'{u.display_name} {u.username} {u.email}'.lower())]
        cust = (User.objects.filter(role='customer', is_active=True)
                .filter(Q(orders__shop_orders__shop=me.shop)
                        | Q(chat_memberships__conversation__shop=me.shop,
                            chat_memberships__conversation__kind=ConversationKind.SHOP)).distinct())
        out['customers'] = list(by_text(cust)[:25])
    if me.role == 'customer':
        if len(q) >= 2:
            out['shops'] = list(Shop.objects.filter(status=ShopStatus.ACTIVE, name__icontains=q)[:8])
        if len(q) >= 3:                                   # other customers: exact username or email only (privacy)
            out['people'] = list(User.objects.filter(role='customer', is_active=True)
                                 .filter(Q(username__iexact=q) | Q(email__iexact=q)).exclude(pk=me.pk)[:5])
    elif me.role in HELP_ROLES and len(q) >= 2:
        out['people'] = list(by_text(User.objects.filter(is_active=True).exclude(pk=me.pk))[:25])
    elif me.is_platform_staff and len(q) >= 2:
        out['people'] = list(by_text(User.objects.filter(is_active=True, role__in=[
            'admin', 'support', 'analyst', 'developer', 'ceo']).exclude(pk=me.pk))[:25])
    return out


# --------------------------------------------------------------- serialising
def serialize(msg: Message) -> dict:
    reply = None
    if msg.reply_to_id:
        r = msg.reply_to
        reply = {'id': r.id, 'sender': r.sender.display_name, 'body': '' if r.deleted else r.body[:140],
                 'deleted': r.deleted}
    grouped = {}
    for rx in msg.reactions.all():
        grouped.setdefault(rx.emoji, []).append(rx.user_id)
    s = msg.sender
    return {
        'id': msg.id, 'conversation': msg.conversation_id, 'client_id': str(msg.client_id) if msg.client_id else '',
        'sender': {'id': s.id, 'name': s.display_name, 'role': s.role, 'initials': s.initials},
        'body': '' if msg.deleted else msg.body, 'deleted': msg.deleted, 'reply_to': reply,
        'reactions': [{'emoji': e, 'users': u} for e, u in grouped.items()],
        'created_at': msg.created_at.isoformat(),
    }


def fetch(message_id):
    return (Message.objects.select_related('sender', 'reply_to__sender', 'conversation')
            .prefetch_related('reactions').get(pk=message_id))


def broadcast(conv_id, event, data):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(f'chat_{conv_id}', {'type': 'chat.event', 'event': event, 'data': data})


# ---------------------------------------------------------------- operations
def _rate_check(user):
    key = f'chatrate:{user.pk}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT:
        raise ChatError('You are sending messages too fast. Please slow down.')
    if count == 0:
        cache.set(key, 1, RATE_WINDOW)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, RATE_WINDOW)


def send_message(user, conv, body, reply_to_id=None, client_id=None) -> Message:
    if not can_access(user, conv):
        raise ChatError('You are not part of this conversation.')
    if conv.kind == ConversationKind.DIRECT:
        others = [m.user for m in conv.memberships.select_related('user') if m.user_id != user.pk]
        if any(o.role not in HELP_ROLES and is_blocked(user, o) for o in others):
            raise ChatError('You cannot message this person.')
    body = clean_text(body)
    if not body:
        raise ChatError('Write a message first.')
    if len(body) > MAX_BODY:
        raise ChatError(f'Messages can be at most {MAX_BODY} characters.')
    if client_id:
        existing = Message.objects.filter(sender=user, client_id=client_id).first()
        if existing:
            return existing                   # a retry of something already saved
    _rate_check(user)
    reply = None
    if reply_to_id:
        reply = Message.objects.filter(pk=reply_to_id, conversation=conv).first()
        if reply is None:
            raise ChatError('The message you are replying to was not found.')
    try:
        msg = Message.objects.create(conversation=conv, sender=user, body=body, reply_to=reply, client_id=client_id or None)
    except IntegrityError:
        return Message.objects.get(sender=user, client_id=client_id)
    Conversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now())
    Participant.objects.filter(conversation=conv, user=user).update(last_read_at=timezone.now())
    msg = fetch(msg.pk)
    broadcast(conv.pk, 'message', serialize(msg))
    # a bell notification for everyone else involved
    others = {p.user for p in conv.memberships.select_related('user') if p.user_id != user.pk}
    if conv.shop_id and user.pk != conv.shop.owner_id:
        others.add(conv.shop.owner)
    for other in others:
        notify(other, f'New message from {user.display_name}', body[:100], f'/chat/{conv.pk}/')
    return msg


def delete_message(user, message_id):
    msg = Message.objects.select_related('conversation').get(pk=message_id)
    if not can_access(user, msg.conversation):
        raise ChatError('You are not part of this conversation.')
    if msg.sender_id != user.pk and user.role != 'admin':
        raise ChatError('You can only delete your own messages.')
    if not msg.deleted:
        msg.deleted_at = timezone.now()
        msg.body = ''
        msg.save(update_fields=['deleted_at', 'body'])
        msg.reactions.all().delete()
        broadcast(msg.conversation_id, 'deleted', {'id': msg.id})
    return msg


def toggle_reaction(user, message_id, emoji):
    msg = Message.objects.select_related('conversation').get(pk=message_id)
    if not can_access(user, msg.conversation):
        raise ChatError('You are not part of this conversation.')
    if msg.deleted:
        raise ChatError('That message was deleted.')
    if not valid_emoji(emoji):
        raise ChatError('Please pick an emoji.')
    _rate_check(user)
    rx = Reaction.objects.filter(message=msg, user=user, emoji=emoji).first()
    if rx:
        rx.delete()
    else:
        Reaction.objects.create(message=msg, user=user, emoji=emoji)
    grouped = {}
    for r in msg.reactions.all():
        grouped.setdefault(r.emoji, []).append(r.user_id)
    data = {'id': msg.id, 'reactions': [{'emoji': e, 'users': u} for e, u in grouped.items()]}
    broadcast(msg.conversation_id, 'reactions', data)
    return data


def mark_read(user, conv):
    Participant.objects.update_or_create(conversation=conv, user=user, defaults={'last_read_at': timezone.now()})


def unread_count(user, conv):
    part = conv.memberships.filter(user=user).first()
    if not part:
        return 0
    return conv.messages.filter(created_at__gt=part.last_read_at).exclude(sender=user).count()


# ---------------------------------------------------------------- starting
def start_shop_chat(customer, shop, order=None):
    conv = (Conversation.objects.filter(kind=ConversationKind.SHOP, shop=shop, memberships__user=customer)
            .order_by('-updated_at').first())
    if conv is None:
        conv = Conversation.objects.create(kind=ConversationKind.SHOP, shop=shop, order=order, subject=shop.name)
        Participant.objects.create(conversation=conv, user=customer)
        Participant.objects.create(conversation=conv, user=shop.owner)
    return conv


def start_support_chat(user, subject='Help from the Nyota team'):
    conv = (Conversation.objects.filter(kind=ConversationKind.SUPPORT, memberships__user=user)
            .order_by('-updated_at').first())
    if conv is None:
        conv = Conversation.objects.create(kind=ConversationKind.SUPPORT, subject=subject)
        Participant.objects.create(conversation=conv, user=user)
    return conv


def start_team_chat(shop):
    """The shop's internal room: owner and all staff, never visible to customers."""
    conv = Conversation.objects.filter(kind=ConversationKind.TEAM, shop=shop).first()
    if conv is None:
        conv = Conversation.objects.create(kind=ConversationKind.TEAM, shop=shop, subject=f'{shop.name} team')
    for u in team_members(shop):
        Participant.objects.get_or_create(conversation=conv, user=u, defaults={'last_read_at': conv.created_at})
    return conv


def start_direct(user, other):
    """Direct line between two accounts. Allowed when one side is platform admin/support,
    or when a seller wants to talk to a customer of theirs (checked by the caller)."""
    mine = Conversation.objects.filter(kind=ConversationKind.DIRECT, memberships__user=user)
    conv = mine.filter(memberships__user=other).first()
    if conv is None:
        conv = Conversation.objects.create(kind=ConversationKind.DIRECT,
                                           subject=f'{user.display_name} and {other.display_name}')
        Participant.objects.create(conversation=conv, user=user)
        Participant.objects.create(conversation=conv, user=other)
    return conv
