import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import Role
from portals.common import show
from shops.models import Shop, ShopStatus

from . import services
from .models import Block, Conversation, ConversationKind, Message

User = get_user_model()


def _conv_or_404(request, pk):
    conv = get_object_or_404(Conversation.objects.select_related('shop'), pk=pk)
    if not services.can_access(request.user, conv):
        raise Http404
    return conv


def _others(conv, user):
    return [m.user for m in conv.memberships.all() if m.user_id != user.pk]


def _title_for(conv, user):
    if conv.kind == ConversationKind.TEAM:
        return f'{conv.shop.name} team'
    if conv.kind == ConversationKind.SHOP:
        if user.shop and conv.shop_id == user.shop.pk:       # shop side: show the customer
            cust = next((m.user for m in conv.memberships.all() if m.user.role == Role.CUSTOMER), None)
            return cust.display_name if cust else conv.subject
        return conv.shop.name                                 # customer side: show the shop
    if conv.kind == ConversationKind.SUPPORT:
        if user.role in (Role.ADMIN, Role.SUPPORT):
            cust = next((m.user for m in conv.memberships.all() if m.user.role not in (Role.ADMIN, Role.SUPPORT)), None)
            return f'Support: {cust.display_name}' if cust else 'Support'
        return 'Nyota support'
    others = _others(conv, user)
    return ', '.join(o.display_name for o in others[:2]) or conv.subject or 'Chat'


@login_required
def inbox(request, pk=None):
    convs = list(services.conversations_for(request.user)[:60])
    for c in convs:                                           # people who see a chat through their shop role get unread counts too
        if not any(m.user_id == request.user.pk for m in c.memberships.all()):
            services.ensure_participant(request.user, c)
    if convs:
        convs = list(services.conversations_for(request.user)[:60])
    rows = []
    for c in convs:
        last = c.messages.order_by('-id').first()
        rows.append({'conv': c, 'title': _title_for(c, request.user), 'kind': c.kind,
                     'unread': services.unread_count(request.user, c),
                     'last': ('Message deleted' if last and last.deleted else (last.body[:60] if last else 'No messages yet')),
                     'last_at': last.created_at if last else c.created_at})
    active, other, i_blocked = None, None, False
    if pk:
        active = _conv_or_404(request, pk)
        services.mark_read(request.user, active)
        if active.kind == ConversationKind.DIRECT:
            other = next(iter(_others(active, request.user)), None)
            if other and other.role not in (Role.ADMIN, Role.SUPPORT):
                i_blocked = Block.objects.filter(blocker=request.user, blocked=other).exists()
            else:
                other = None
    elif convs:
        return redirect('chat:thread', pk=convs[0].pk)
    return show(request, 'chat/inbox.html', {
        'rows': rows, 'active': active, 'active_title': _title_for(active, request.user) if active else '',
        'me_id': request.user.pk, 'can_moderate': request.user.role == Role.ADMIN,
        'other': other, 'i_blocked': i_blocked}, 'Messages')


@login_required
def new_chat(request):
    q = request.GET.get('q', '').strip()
    found = services.find_people(request.user, q)
    return show(request, 'chat/new.html', {'q': q, 'found': found, 'has_shop': bool(request.user.shop),
                                           'is_customer': request.user.role == Role.CUSTOMER}, 'New conversation')


@login_required
def history(request, pk):
    conv = _conv_or_404(request, pk)
    qs = (Message.objects.filter(conversation=conv).select_related('sender', 'reply_to__sender')
          .prefetch_related('reactions'))
    after, before = request.GET.get('after'), request.GET.get('before')
    if after and after.isdigit():
        qs = qs.filter(id__gt=int(after)).order_by('id')[:100]
        items = list(qs)
    else:
        if before and before.isdigit():
            qs = qs.filter(id__lt=int(before))
        items = list(qs.order_by('-id')[:50])[::-1]
    return JsonResponse({'messages': [services.serialize(m) for m in items], 'me': request.user.pk})


@login_required
@require_POST
def send(request, pk):
    """HTTP fallback for when the WebSocket is unavailable."""
    conv = _conv_or_404(request, pk)
    try:
        data = json.loads(request.body or b'{}')
        msg = services.send_message(request.user, conv, data.get('body', ''), data.get('reply_to') or None,
                                    data.get('client_id') or None)
    except services.ChatError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'message': 'Bad request.'}, status=400)
    return JsonResponse({'ok': True, 'message': services.serialize(services.fetch(msg.pk))})


@login_required
@require_POST
def react(request, message_id):
    try:
        data = json.loads(request.body or b'{}')
        result = services.toggle_reaction(request.user, message_id, data.get('emoji', ''))
    except services.ChatError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
    except (ValueError, Message.DoesNotExist):
        return JsonResponse({'ok': False, 'message': 'Not found.'}, status=404)
    return JsonResponse({'ok': True, **result})


@login_required
@require_POST
def delete(request, message_id):
    try:
        services.delete_message(request.user, message_id)
    except services.ChatError as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=403)
    except Message.DoesNotExist:
        return JsonResponse({'ok': False, 'message': 'Not found.'}, status=404)
    return JsonResponse({'ok': True})


@login_required
def start_shop(request, slug):
    shop = get_object_or_404(Shop, slug=slug, status=ShopStatus.ACTIVE)
    if request.user.role != Role.CUSTOMER:
        messages.info(request, 'Only customers can start a chat with a shop. Shops reply from their inbox.')
        return redirect(shop.get_absolute_url())
    return redirect('chat:thread', pk=services.start_shop_chat(request.user, shop).pk)


@login_required
def start_support(request):
    return redirect('chat:thread', pk=services.start_support_chat(request.user).pk)


@login_required
def start_team(request):
    """The shop's private team room (owner and staff)."""
    if not request.user.shop:
        raise Http404
    return redirect('chat:thread', pk=services.start_team_chat(request.user.shop).pk)


@login_required
def start_user(request, pk):
    """Direct chat with one person, when the rules in services.can_message allow it."""
    other = get_object_or_404(User, pk=pk, is_active=True)
    if not services.can_message(request.user, other):
        messages.error(request, 'You cannot start a chat with that person.')
        return redirect('chat:new')
    return redirect('chat:thread', pk=services.start_direct(request.user, other).pk)


@login_required
@require_POST
def block_toggle(request, pk):
    other = get_object_or_404(User, pk=pk)
    if other.role in (Role.ADMIN, Role.SUPPORT) or other.pk == request.user.pk:
        messages.error(request, 'You cannot block that account.')
    else:
        row = Block.objects.filter(blocker=request.user, blocked=other)
        if row.exists():
            row.delete()
            messages.success(request, f'{other.display_name} was unblocked.')
        else:
            Block.objects.create(blocker=request.user, blocked=other)
            messages.success(request, f'{other.display_name} was blocked. They can no longer message you.')
    return redirect(request.META.get('HTTP_REFERER') or 'chat:inbox')
