from django.conf import settings

THEMES = [
    # key, label, dark?, swatch (background, panel)
    ('midnight', 'Midnight', True, ('#070b1a', '#121a33')),
    ('aurora', 'Aurora', True, ('#04141a', '#0b2a33')),
    ('dusk', 'Dusk', True, ('#150a22', '#25143a')),
    ('ember', 'Ember', True, ('#160b08', '#2a1612')),
    ('ocean', 'Ocean', True, ('#06121f', '#0c2440')),
    ('carbon', 'Carbon', True, ('#0b0b0d', '#18181c')),
    ('dawn', 'Dawn', False, ('#f6f7fb', '#ffffff')),
    ('savanna', 'Savanna', False, ('#fbf5ea', '#fffdf8')),
    ('sakura', 'Sakura', False, ('#fff4f7', '#ffffff')),
    ('mint', 'Mint', False, ('#f0faf6', '#ffffff')),
]
ACCENTS = [
    ('violet', '#8b5cf6'), ('gold', '#f5b324'), ('emerald', '#10b981'), ('rose', '#f43f5e'),
    ('sky', '#0ea5e9'), ('orange', '#fb7c2c'), ('lime', '#84cc16'), ('fuchsia', '#d946ef'),
    ('teal', '#14b8a6'), ('crimson', '#dc2626'),
]
THEME_KEYS = {t[0] for t in THEMES} | {'auto'}
ACCENT_KEYS = {a[0] for a in ACCENTS}


def site(request):
    user = getattr(request, 'user', None)
    authed = bool(user and user.is_authenticated)
    cart = request.session.get('cart', {}) if hasattr(request, 'session') else {}
    ctx = {
        'COMPANY_NAME': settings.COMPANY_NAME,
        'CURRENCY': settings.CURRENCY,
        'THEMES': THEMES,
        'ACCENTS': ACCENTS,
        'cart_count': sum(int(q) for q in cart.values()) if cart else 0,
        'PAYMENTS_SIMULATE': settings.PAYMENTS_SIMULATE,
        'oauth_providers': [p for p, c in settings.OAUTH.items() if c.get('client_id')],
        'ui_theme': user.theme if authed and user.theme in THEME_KEYS else 'auto',
        'ui_accent': user.accent if authed and user.accent in ACCENT_KEYS else 'violet',
        'ui_authed': authed,
        'ui_dark': True,
        'unread_notifications': 0,
        'my_shop': None,
    }
    theme_dark = {t[0]: t[2] for t in THEMES}
    ctx['ui_dark'] = theme_dark.get(ctx['ui_theme'], True)  # 'auto' is resolved in the browser from the device setting
    if authed:
        from core.models import Notification
        ctx['unread_notifications'] = Notification.objects.filter(user=user, is_read=False).count()
        if user.is_seller_side:
            ctx['my_shop'] = user.shop
    return ctx
