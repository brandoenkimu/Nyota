"""What each position inside a shop may do. The owner can do everything."""
ROLE_PERMS = {
    'manager': {'products', 'orders', 'staff', 'attendance', 'analytics', 'profile', 'chat', 'reviews', 'payouts'},
    'cashier': {'orders', 'chat'},
    'inventory': {'products', 'orders'},
    'support': {'chat', 'reviews', 'orders'},
    'analyst': {'analytics'},
}
ALL_PERMS = {'products', 'orders', 'staff', 'attendance', 'analytics', 'profile', 'chat', 'reviews', 'payouts'}


def shop_permissions(user) -> set:
    if not getattr(user, 'is_authenticated', False):
        return set()
    if user.role == 'seller_owner':
        return set(ALL_PERMS)
    if user.role == 'seller_staff':
        membership = getattr(user, 'shop_membership', None)
        if membership and membership.active:
            return set(ROLE_PERMS.get(membership.role, set()))
    return set()
