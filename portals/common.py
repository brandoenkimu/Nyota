"""Shared plumbing for every portal: access control, sidebar navigation, and small helpers that
turn query results into the generic dashboard / list / form templates."""
import csv
from functools import wraps

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html

from shops.permissions import shop_permissions


# ------------------------------------------------------------------ access
def _login_for(path):
    if path.startswith('/seller/'):
        return 'accounts:seller_login'
    if path.startswith('/staff/'):
        return 'accounts:staff_login'
    return 'accounts:login'


def role_required(*roles, shop_perm=None):
    """Only these roles (and, for sellers, only staff holding `shop_perm`) may open the view."""
    def deco(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{reverse(_login_for(request.path))}?next={request.path}")
            if user.role not in roles:
                messages.warning(request, 'That area is not part of your account. Here is your own home.')
                return redirect(user.home_url)
            if shop_perm:
                if user.shop is None:
                    messages.warning(request, 'Your shop is not available. Please contact the administrator.')
                    return redirect('core:home')
                if shop_perm not in shop_permissions(user):
                    messages.warning(request, 'Your position in this shop does not include that area.')
                    return redirect('portals:seller_home')
            return view(request, *args, **kwargs)
        return wrapped
    return deco


# -------------------------------------------------------------- navigation
def _item(label, url, icon, key=None, perm=None):
    return {'label': label, 'url': url, 'icon': icon, 'key': key or url, 'perm': perm}


def nav_for(user):
    role = user.role
    if role == 'customer':
        return [
            _item('Overview', 'portals:customer_home', 'grid'),
            _item('My orders', 'portals:customer_orders', 'box'),
            _item('Wishlist', 'portals:customer_wishlist', 'heart'),
            _item('Messages', 'chat:inbox', 'chat'),
            _item('Addresses', 'portals:customer_addresses', 'pin'),
            _item('Profile & themes', 'portals:profile', 'user'),
        ]
    if role in ('seller_owner', 'seller_staff'):
        perms = shop_permissions(user)
        items = [
            _item('Overview', 'portals:seller_home', 'grid'),
            _item('Orders', 'portals:seller_orders', 'box', perm='orders'),
            _item('Products', 'portals:seller_products', 'tag', perm='products'),
            _item('Reviews', 'portals:seller_reviews', 'star', perm='reviews'),
            _item('Messages', 'chat:inbox', 'chat'),
            _item('Analytics', 'portals:seller_analytics', 'chart', perm='analytics'),
            _item('Payouts', 'portals:seller_payouts', 'wallet', perm='payouts'),
            _item('Team', 'portals:seller_staff', 'users', perm='staff'),
            _item('Attendance', 'portals:seller_attendance', 'clock', perm='attendance'),
            _item('Shop profile', 'portals:seller_profile', 'store', perm='profile'),
            _item('My profile', 'portals:profile', 'user'),
        ]
        return [i for i in items if not i['perm'] or i['perm'] in perms]
    if role == 'admin':
        return [
            _item('Overview', 'portals:admin_home', 'grid'),
            _item('Orders & tracking', 'portals:admin_orders', 'box'),
            _item('Shops', 'portals:admin_shops', 'store'),
            _item('Users', 'portals:admin_users', 'users'),
            _item('Staff', 'portals:admin_staff', 'id'),
            _item('Categories', 'portals:admin_categories', 'tag'),
            _item('Coupons', 'portals:admin_coupons', 'ticket'),
            _item('Home slides', 'portals:admin_slides', 'image'),
            _item('Payouts', 'portals:admin_payouts', 'wallet'),
            _item('Payments', 'portals:admin_payments', 'card'),
            _item('Attendance', 'portals:admin_attendance', 'clock'),
            _item('Audit log', 'portals:admin_audit', 'shield'),
            _item('Support chats', 'chat:inbox', 'chat'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'analyst':
        return [
            _item('Overview', 'portals:analyst_home', 'grid'),
            _item('Customers', 'portals:analyst_customers', 'users'),
            _item('Products & baskets', 'portals:analyst_products', 'tag'),
            _item('Forecast', 'portals:analyst_forecast', 'chart'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'developer':
        return [
            _item('System health', 'portals:developer_home', 'pulse'),
            _item('Audit integrity', 'portals:developer_audit', 'shield'),
            _item('Webhooks', 'portals:developer_webhooks', 'plug'),
            _item('API access', 'portals:developer_api', 'key'),
            _item('Warehouse jobs', 'portals:developer_jobs', 'db'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'ceo':
        return [
            _item('Executive view', 'portals:ceo_home', 'grid'),
            _item('Shops league', 'portals:ceo_shops', 'store'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'support':
        return [
            _item('Support desk', 'portals:support_home', 'headset'),
            _item('Chats', 'chat:inbox', 'chat'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    return []


def portal_name(user):
    return {'customer': 'My Nyota', 'seller_owner': 'Seller studio', 'seller_staff': 'Seller studio',
            'admin': 'Administration', 'analyst': 'Analytics lab', 'developer': 'Developer console',
            'ceo': 'Executive suite', 'support': 'Support desk'}.get(user.role, 'Nyota')


def show(request, template, ctx=None, title='', status=200):
    """Render inside the portal shell."""
    user = request.user
    current = request.resolver_match.view_name if request.resolver_match else ''
    nav = []
    for it in nav_for(user):
        nav.append({**it, 'href': reverse(it['url']), 'active': it['url'] == current})
    data = {'nav': nav, 'portal_name': portal_name(user), 'page_title': title}
    data.update(ctx or {})
    return render(request, template, data, status=status)


# ---------------------------------------------------------- cell builders
def link(url, text):
    return format_html('<a href="{}">{}</a>', url, text)


def badge(status, label=None):
    from core.templatetags.nyota import badge as _badge
    return _badge(status, label)


def dash(request, title, kpis=None, charts=None, tables=None, actions=None, notes=None, subtitle=''):
    return show(request, 'portal/dashboard.html', {
        'kpis': kpis or [], 'charts': charts or [], 'tables': tables or [], 'actions': actions or [],
        'notes': notes or [], 'subtitle': subtitle}, title)


def listing(request, title, headers, rows, page=None, filters=None, add=None, empty='Nothing here yet.', subtitle='',
            extra_actions=None):
    """rows: list of {'cells': [...], 'url': optional row link}"""
    return show(request, 'portal/list.html', {
        'headers': headers, 'rows': rows, 'page': page, 'filters': filters or [], 'add': add, 'empty': empty,
        'subtitle': subtitle, 'extra_actions': extra_actions or []}, title)


def form_page(request, title, form, submit='Save', cancel=None, note='', subtitle=''):
    return show(request, 'portal/form.html', {'form': form, 'submit': submit, 'cancel': cancel, 'note': note,
                                              'subtitle': subtitle}, title)


def kpi(label, value, delta=None, hint='', icon='chart', money=False):
    return {'label': label, 'value': value, 'delta': delta, 'hint': hint, 'icon': icon, 'money': money}


def chart(cid, kind, title, labels, datasets, wide=False, money=False):
    """datasets: [{'label':..., 'data':[...]}]"""
    return {'id': cid, 'type': kind, 'title': title, 'labels': labels, 'datasets': datasets, 'wide': wide,
            'money': money}


def table(title, headers, rows, empty='No data yet.', link_url=None, link_label=''):
    return {'title': title, 'headers': headers, 'rows': rows, 'empty': empty, 'link_url': link_url,
            'link_label': link_label}


def csv_response(filename, headers, rows):
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    w = csv.writer(resp)
    w.writerow(headers)
    for row in rows:
        # neutralise spreadsheet formulas
        w.writerow([("'" + str(c)) if isinstance(c, str) and c[:1] in '=+-@' else c for c in row])
    return resp
