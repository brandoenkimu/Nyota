import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from django import template
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeData
from django.utils.safestring import mark_safe

from core import art

register = template.Library()


@register.filter
def kes(value):
    try:
        return f'{settings.CURRENCY} {Decimal(str(value)):,.0f}'
    except (InvalidOperation, ValueError, TypeError):
        return f'{settings.CURRENCY} 0'


@register.filter
def kes2(value):
    try:
        return f'{settings.CURRENCY} {Decimal(str(value)):,.2f}'
    except (InvalidOperation, ValueError, TypeError):
        return f'{settings.CURRENCY} 0.00'


@register.filter
def getitem(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def stars(value):
    """4.3 -> list of 'full' / 'half' / 'empty' for five star icons."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0
    out = []
    for i in range(1, 6):
        out.append('full' if v >= i - 0.25 else 'half' if v >= i - 0.75 else 'empty')
    return out


@register.filter
def times(n):
    try:
        return range(int(n))
    except (TypeError, ValueError):
        return range(0)


@register.filter
def pct(value, total):
    try:
        return round(float(value) / float(total) * 100) if float(total) else 0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


STATUS_CLASS = {
    'paid': 'ok', 'delivered': 'ok', 'completed': 'ok', 'active': 'ok', 'succeeded': 'ok', 'approved': 'ok',
    'present': 'ok', 'confirmed': 'info', 'packed': 'info', 'shipped': 'info', 'out_for_delivery': 'info',
    'in_progress': 'info', 'placed': 'info', 'pending': 'warn', 'unpaid': 'warn', 'requested': 'warn',
    'initiated': 'warn', 'late': 'warn', 'cancelled': 'bad', 'failed': 'bad', 'suspended': 'bad',
    'rejected': 'bad', 'returned': 'bad', 'refunded': 'bad',
}


@register.simple_tag
def badge(status, label=None):
    key = str(status or '')
    text = label or key.replace('_', ' ').capitalize()
    return format_html('<span class="ny-badge ny-badge-{}">{}</span>', STATUS_CLASS.get(key, 'mute'), text)


@lru_cache(maxsize=512)
def _product_art(name, slug, seed):
    return art.product_svg(name, slug, seed)


@register.simple_tag
def product_image(product, css=''):
    """Real photo when there is one; otherwise (or if the photo fails to load) generated artwork,
    so a product card is never empty."""
    slug = product.category.slug if product.category_id else ''
    svg = _product_art(product.name, slug, str(product.pk))
    photo = ''
    if product.real_image:
        photo = format_html('<img src="{}" alt="{}" loading="lazy" onerror="this.remove()">',
                            product.real_image, product.name)
    return format_html('<div class="pimg {}"><div class="pimg-art">{}</div>{}</div>',
                       css, mark_safe(svg), photo)


@register.simple_tag
def shop_logo(shop, css=''):
    if shop.logo:
        return format_html('<span class="shop-logo {}"><img src="{}" alt="{}"></span>', css, shop.logo.url, shop.name)
    return format_html('<span class="shop-logo {}">{}</span>', css, mark_safe(art.shop_logo_svg(shop.name, str(shop.pk))))


@register.simple_tag
def brand_logo(mode='full', css=''):
    return format_html('<span class="brand-logo {}">{}</span>', css, mark_safe(art.brand_logo_svg(mode)))


@register.simple_tag
def hero_art(variant=0):
    return mark_safe(art.hero_svg(int(variant) % 4))


@register.simple_tag
def category_icon(slug):
    return mark_safe(art.category_icon_svg(slug))


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Current query string with some keys replaced (for pagination and filter links)."""
    params = context['request'].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ''):
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()


@register.filter
def cell(value):
    """Render any value for generic list/dashboard tables."""
    if value is None or value == '':
        return '\u2014'
    if isinstance(value, SafeData):
        return value
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, Decimal):
        return f'{settings.CURRENCY} {value:,.2f}'
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime('%d %b %Y, %H:%M')
    if isinstance(value, datetime.date):
        return value.strftime('%d %b %Y')
    return value


ICON_NAMES = {
    'search': '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    'cart': '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6"/>',
    'heart': '<path d="M20.8 5.6a5.2 5.2 0 0 0-7.4 0L12 7l-1.4-1.4a5.2 5.2 0 0 0-7.4 7.4L12 21.7l8.8-8.7a5.2 5.2 0 0 0 0-7.4z"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    'users': '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8"/><path d="M22 21a7 7 0 0 0-4-6.3"/>',
    'home': '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/>',
    'store': '<path d="M3 9 5 3h14l2 6"/><path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/><path d="M5 12v9h14v-9"/>',
    'box': '<path d="m21 8-9-5-9 5v8l9 5 9-5z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
    'truck': '<path d="M1 4h13v12H1z"/><path d="M14 8h4l4 4v4h-8"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    'chat': '<path d="M21 12a8 8 0 0 1-11.7 7L3 21l2-5.5A8 8 0 1 1 21 12z"/>',
    'send': '<path d="m22 2-11 11"/><path d="m22 2-7 20-4-9-9-4z"/>',
    'bell': '<path d="M6 9a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 21a2 2 0 0 0 4 0"/>',
    'chart': '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
    'pie': '<path d="M21 12A9 9 0 1 1 12 3v9z"/><path d="M15 3.5A9 9 0 0 1 20.5 9H15z"/>',
    'wallet': '<path d="M3 7h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 7a2 2 0 0 1 2-2h12"/><circle cx="17" cy="14" r="1.2"/>',
    'card': '<rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20"/>',
    'tag': '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    'star': '<path d="m12 2 3 6.5 7 .9-5.2 4.8 1.4 7L12 17.8 5.8 21.2l1.4-7L2 9.4l7-.9z"/>',
    'map': '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.6"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'calendar': '<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M8 2v4M16 2v4M3 10h18"/>',
    'shield': '<path d="M12 2 4 5v6c0 5 3.4 9 8 11 4.6-2 8-6 8-11V5z"/><path d="m9 12 2 2 4-4"/>',
    'key': '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3"/>',
    'lock': '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    'mail': '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="m2 7 10 7 10-7"/>',
    'phone': '<path d="M22 17v3a2 2 0 0 1-2.2 2A19 19 0 0 1 2 4.2 2 2 0 0 1 4 2h3l2 5-2.5 1.5a14 14 0 0 0 7 7L15 13l5 2z"/>',
    'check': '<path d="m4 12 5 5L20 6"/>',
    'x': '<path d="M18 6 6 18M6 6l12 12"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'minus': '<path d="M5 12h14"/>',
    'edit': '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    'trash': '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m6 6 1 15h10l1-15"/>',
    'arrow-right': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'arrow-left': '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    'chevron-left': '<path d="m15 6-6 6 6 6"/>', 'chevron-right': '<path d="m9 6 6 6-6 6"/>', 'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'menu': '<path d="M3 6h18M3 12h18M3 18h18"/>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
    'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    'palette': '<path d="M12 3a9 9 0 1 0 0 18c1.2 0 2-.8 2-1.8 0-.6-.3-1-.6-1.4-.3-.4-.4-.8-.4-1.1 0-.8.7-1.4 1.5-1.4H17a4 4 0 0 0 4-4C21 6.6 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.1"/><circle cx="10" cy="7" r="1.1"/><circle cx="15" cy="7" r="1.1"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    'moon': '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 21h16"/>',
    'refresh': '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/>',
    'eye': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    'file': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h6"/>',
    'code': '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    'database': '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    'activity': '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    'trending': '<path d="m22 7-9 9-4-4-7 7"/><path d="M16 7h6v6"/>',
    'gift': '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M5 12v9h14v-9M12 8a3 3 0 1 1 3-3c0 1.7-3 3-3 3zm0 0a3 3 0 1 0-3-3c0 1.7 3 3 3 3z"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    'smile': '<circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2.5 4 2.5S16 14 16 14M9 9.5h.01M15 9.5h.01"/>',
    'reply': '<path d="m9 17-5-5 5-5"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>',
    'verified': '<path d="m12 2 2.4 2 3.1-.2 1 3 2.6 1.8-.9 3 .9 3-2.6 1.8-1 3-3.1-.2L12 22l-2.4-2-3.1.2-1-3-2.6-1.8.9-3-.9-3 2.6-1.8 1-3 3.1.2z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    'headset': '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="2" y="14" width="5" height="7" rx="2"/><rect x="17" y="14" width="5" height="7" rx="2"/>',
    'list': '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    'layers': '<path d="m12 2 10 6-10 6L2 8z"/><path d="m2 16 10 6 10-6"/>',
    'percent': '<path d="m19 5-14 14"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    'globe': '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/>',
    'filter': '<path d="M3 4h18l-7 9v6l-4 2v-8z"/>',
    'instagram': '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    'facebook': '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
    'twitter': '<path d="M22 4.5a9 9 0 0 1-2.6.7 4.5 4.5 0 0 0 2-2.5 9 9 0 0 1-2.9 1.1A4.5 4.5 0 0 0 11 7.5 12.800 12.8 12.8 0 0 1 2 3s-4 9 5 13a13 13 0 0 1-5 1c9 5 20 0 20-11.5z"/>',
}


ICON_NAMES.update({
    'grid': '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    'pin': ICON_NAMES['map'], 'pulse': ICON_NAMES['activity'], 'db': ICON_NAMES['database'],
    'id': '<rect x="2" y="5" width="20" height="14" rx="3"/><circle cx="8.5" cy="11" r="2"/><path d="M5 16a3.5 3.5 0 0 1 7 0M14 10h5M14 14h4"/>',
    'ticket': '<path d="M3 9V6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3a3 3 0 0 0 0 6v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a3 3 0 0 0 0-6z"/><path d="M14 5v14" stroke-dasharray="2 3"/>',
    'plug': '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v5"/>',
})


@register.simple_tag
def icon(name, size=None, css=''):
    path = ICON_NAMES.get(name, ICON_NAMES['star'])
    style = f' style="width:{size}px;height:{size}px"' if size else ''
    return mark_safe(f'<svg class="ico {css}"{style} viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                     f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


@register.filter
def ph(bound):
    """Render a bound field with a blank placeholder so floating labels work."""
    attrs = {}
    if 'placeholder' not in bound.field.widget.attrs:
        attrs['placeholder'] = ' '
    return bound.as_widget(attrs=attrs)


@register.filter
def widget_kind(bound):
    w = bound.field.widget.__class__.__name__
    if w in ('CheckboxInput',):
        return 'check'
    if w in ('Select', 'SelectMultiple', 'RadioSelect', 'NullBooleanSelect'):
        return 'select'
    if w in ('FileInput', 'ClearableFileInput'):
        return 'file'
    if w == 'Textarea':
        return 'textarea'
    if w == 'HiddenInput':
        return 'hidden'
    if w == 'PasswordInput':
        return 'password'
    return 'text'


@register.filter
def chart_json(c):
    """Chart dict -> JSON safe to embed in an HTML attribute."""
    import json
    payload = {'type': c['type'], 'labels': [str(x) for x in c['labels']],
               'datasets': [{'label': d.get('label', ''), 'data': [float(v) if v is not None else None for v in d['data']]}
                            for d in c['datasets']]}
    return json.dumps(payload).replace('<', '\\u003c')
