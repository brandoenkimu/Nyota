"""Who may look at whose profile, and how much they see. It depends on the direction:
a customer sees a small public card of another customer, a shop sees the customers who ordered from it,
colleagues see each other's work details, and the Nyota team can see everyone."""
from .models import Role

LEVELS = ('card', 'seller_view', 'staff', 'full')


def _chatted(a, b):
    from chat.models import Participant
    mine = Participant.objects.filter(user=a).values_list('conversation_id', flat=True)
    return Participant.objects.filter(user=b, conversation_id__in=mine).exists()


def _blocked(a, b):
    from chat.services import is_blocked
    return is_blocked(a, b)


def _customer_of(shop, target):
    from orders.models import ShopOrder
    return ShopOrder.objects.filter(shop=shop, order__customer=target).exclude(status='cancelled').exists()


def profile_access(viewer, target):
    """Return None (no access) or one of 'card', 'seller_view', 'staff', 'full'."""
    if not viewer.is_authenticated or not target.is_active:
        return None
    if viewer.pk == target.pk:
        return 'full'
    if viewer.role in (Role.ADMIN, Role.SUPPORT, Role.CEO):
        return 'full'
    if _blocked(viewer, target):
        return None
    vshop, tshop = viewer.shop, target.shop
    if viewer.is_platform_staff and target.is_platform_staff:
        return 'staff'                                           # developer / analyst <-> colleagues
    if viewer.is_seller_side and vshop:
        if tshop and tshop.pk == vshop.pk:
            return 'staff'                                       # owner <-> staff <-> staff of the same shop
        if target.role == Role.CUSTOMER and _customer_of(vshop, target):
            return 'seller_view'
    if viewer.role == Role.CUSTOMER and target.role == Role.CUSTOMER:
        return 'card' if target.profile_visibility != 'private' else None
    if _chatted(viewer, target):
        return 'card'                                            # people already talking can see each other's card
    if viewer.role == Role.CUSTOMER and target.role == Role.SELLER_OWNER:
        return 'card' if tshop and tshop.is_public else None
    return None


def profile_context(viewer, target, level):
    """Only the fields the level allows are put into the page: hiding in a template alone would still leak."""
    from orders.models import Order, ShopOrder
    from catalog.models import Review
    ctx = {'p': target, 'level': level, 'facts': []}
    ctx['reviews'] = Review.objects.filter(user=target).count() if target.role == Role.CUSTOMER else None
    if level in ('staff', 'full'):
        sp = getattr(target, 'staff_profile', None)
        if sp:
            ctx['facts'] += [('Job title', sp.job_title), ('Department', sp.department or '-'), ('Employee no.', sp.employee_no),
                             ('Hired', sp.hired_on.strftime('%d %b %Y'))]
        ctx['facts'] += [('Work email', target.email), ('Phone', target.phone or '-')]
        if target.shop:
            ctx['facts'].append(('Shop', target.shop.name))
    if level == 'seller_view':
        shop = viewer.shop
        qs = ShopOrder.objects.filter(shop=shop, order__customer=target).exclude(status='cancelled')
        ctx['facts'] += [('Orders with your shop', qs.count()), ('Phone (for deliveries)', target.phone or '-')]
        last = qs.select_related('order').order_by('-created_at').first()
        if last:
            ctx['facts'] += [('Last order', last.created_at.strftime('%d %b %Y')), ('Delivers to', last.order.ship_city)]
    if level == 'full':
        ctx['facts'] += [('Email', target.email), ('Role', target.get_role_display()),
                         ('Last seen', target.last_seen.strftime('%d %b %Y %H:%M') if target.last_seen else 'never'),
                         ('Email verified', 'Yes' if target.email_verified else 'No')]
        if target.role == Role.CUSTOMER:
            ctx['facts'].append(('Orders', Order.objects.filter(customer=target).count()))
    return ctx
