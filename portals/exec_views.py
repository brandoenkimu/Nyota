"""Analyst, CEO, developer and support portals."""
import platform
import sys
import time

import django
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token

from accounts.models import PLATFORM_ROLES, Attendance, Role
from analytics import etl, queries
from analytics.models import DimCustomer, EtlRun, FactSales
from audit.models import AuditLog
from audit.service import record, verify_chain
from chat.models import Conversation, ConversationKind
from orders.models import Order, Payout
from payments import mpesa, stripe_service
from payments.models import WebhookLog
from shops.models import Shop, ShopStatus

from .common import badge, chart, csv_response, dash, kpi, link, listing, role_required, show, table

ANALYST = ('analyst', 'admin', 'developer', 'ceo')


def _no_data(request):
    return show(request, 'portal/empty_analytics.html', {'can_refresh': True}, 'Analytics')


# ------------------------------------------------------------------ analyst
@role_required('analyst', 'admin', 'developer')
def analyst_home(request):
    k = queries.kpis(None, 30)
    daily = queries.daily_series(None, 60)
    if not daily:
        return _no_data(request)
    kpis = [kpi('Revenue (30 days)', k['revenue'], k['revenue_growth'], 'vs previous 30 days', 'wallet', True),
            kpi('Orders', k['orders'], k['orders_growth'], 'vs previous 30 days', 'box'),
            kpi('Average order', k['aov'], icon='chart', money=True),
            kpi('Active customers', k['customers'], icon='users'),
            kpi('Commission earned', k['commission'], icon='wallet', money=True)]
    monthly = queries.monthly_series()
    cats = queries.by_category()
    counties = queries.by_county()
    wd = queries.weekday_pattern()
    charts = [
        chart('daily', 'line', 'Daily revenue', [d['date'][5:] for d in daily],
              [{'label': 'Revenue', 'data': [d['revenue'] for d in daily]},
               {'label': 'Orders', 'data': [d['orders'] for d in daily]}], wide=True, money=False),
        chart('monthly', 'bar', 'Monthly revenue and commission', [m['month'] for m in monthly],
              [{'label': 'Revenue', 'data': [m['revenue'] for m in monthly]},
               {'label': 'Commission', 'data': [m['commission'] for m in monthly]}], wide=True, money=True),
        chart('cats', 'doughnut', 'Revenue by category', [c['cat'] for c in cats],
              [{'label': 'Revenue', 'data': [float(c['rev']) for c in cats]}], money=True),
        chart('wd', 'bar', 'Which days sell best', [d['day'] for d in wd],
              [{'label': 'Revenue', 'data': [d['revenue'] for d in wd]}], money=True),
        chart('cty', 'bar', 'Revenue by customer county', [c['county'] for c in counties],
              [{'label': 'Revenue', 'data': [float(c['rev']) for c in counties]}], money=True),
    ]
    tables = [
        table('Top shops (90 days)', ['Shop', 'Revenue', 'Orders', 'Commission'],
              [{'cells': [s['name'], s['rev'], s['orders'], s['comm']]} for s in queries.top_shops()]),
        table('Top products (90 days)', ['Product', 'Shop', 'Revenue', 'Units'],
              [{'cells': [p['name'], p['shop_name'], p['rev'], p['units']]} for p in queries.top_products()]),
    ]
    last = EtlRun.objects.filter(ok=True).first()
    return dash(request, 'Analytics overview', kpis, charts, tables,
                actions=[('Rebuild warehouse', '/staff/analyst/refresh/', 'post'),
                         ('Export sales CSV', '/staff/analyst/export/sales/')],
                subtitle=f'Warehouse last built {timezone.localtime(last.finished_at):%d %b %H:%M}' if last else '')


@role_required('analyst', 'admin', 'developer')
def analyst_customers(request):
    rfm = etl.latest('rfm')
    if not rfm:
        return _no_data(request)
    summary = rfm.get('summary', {})
    names = sorted(summary, key=lambda s: -summary[s]['customers'])
    charts = [chart('seg', 'doughnut', 'Customers by segment', names, [{'label': 'Customers',
                                                                        'data': [summary[n]['customers'] for n in names]}]),
              chart('segrev', 'bar', 'Spend by segment', names,
                    [{'label': 'Total spend', 'data': [round(summary[n]['revenue'], 2) for n in names]}], money=True)]
    rows = [{'cells': [r['name'], r['segment'], r['rfm_score'], r['recency_days'], r['frequency'], r['monetary']]}
            for r in rfm.get('rows', [])[:50]]
    tables = [table('Top customers (RFM)', ['Customer', 'Segment', 'RFM', 'Days since last order', 'Orders', 'Spend'], rows)]
    notes = [('info', 'RFM scores each customer 1 to 5 on Recency, Frequency and Monetary value. '
                      'Champions and Loyal customers deserve rewards; At Risk and Hibernating need a win-back offer.')]
    return dash(request, 'Customer segments', [], charts, tables, notes=notes,
                actions=[('Export CSV', '/staff/analyst/export/rfm/')])


@role_required('analyst', 'admin', 'developer')
def analyst_products(request):
    abc = etl.latest('abc').get('rows', [])
    if not abc:
        return _no_data(request)
    basket = etl.latest('basket')
    sent = etl.latest('sentiment')
    classes = {c: sum(1 for r in abc if r['abc'] == c) for c in 'ABC'}
    charts = [chart('abc', 'bar', 'Cumulative revenue share (Pareto)', [r['name'][:18] for r in abc[:15]],
                    [{'label': 'Share %', 'data': [round(r['share'] * 100, 1) for r in abc[:15]]},
                     {'label': 'Cumulative %', 'data': [round(r['cum_share'] * 100, 1) for r in abc[:15]]}], wide=True),
              chart('cls', 'doughnut', 'Products by class', list(classes), [{'label': 'Products', 'data': list(classes.values())}])]
    tables = [
        table('ABC classification', ['Product', 'Revenue', 'Share', 'Class'],
              [{'cells': [r['name'], r['revenue'], f"{r['share'] * 100:.1f}%", r['abc']]} for r in abc[:30]]),
        table(f"Bought together (from {basket.get('baskets', 0)} orders)",
              ['If a customer buys', 'They also buy', 'Orders', 'Confidence', 'Lift'],
              [{'cells': [b['a_name'], b['b_name'], b['count'], f"{b['confidence'] * 100:.0f}%", f"{b['lift']:.1f}x"]}
               for b in basket.get('rules', [])], 'No frequent pairs yet.'),
    ]
    notes = [('info', 'Class A products make up about 80% of revenue, B the next 15%, C the rest. Lift above 1 means the '
                      'two products are bought together more often than chance.')]
    if sent:
        notes.append(('info', f"Review sentiment overall: {sent['label']} ({sent['average']:+.2f}) from {sent['reviews']} reviews: "
                              f"{sent['positive']} positive, {sent['negative']} negative."))
    return dash(request, 'Products and baskets', [], charts, tables, notes=notes,
                actions=[('Export ABC CSV', '/staff/analyst/export/abc/'), ('Export pairs CSV', '/staff/analyst/export/basket/')])


@role_required('analyst', 'admin', 'developer', 'ceo')
def analyst_forecast(request):
    fc = etl.latest('forecast')
    if not fc:
        return _no_data(request)
    n = len(fc['values'][-45:])
    labels = [d[5:] for d in fc['dates'][-45:] + fc['forecast_dates']]
    actual = fc['values'][-45:] + [None] * len(fc['forecast'])
    pred = [None] * (n - 1) + [fc['values'][-1]] + fc['forecast']
    avg = fc['average7'][-45:] + [None] * len(fc['forecast'])
    charts = [chart('fc', 'line', 'Revenue: last 45 days and next 14 (Holt linear trend)', labels,
                    [{'label': 'Actual', 'data': actual}, {'label': '7-day average', 'data': avg},
                     {'label': 'Forecast', 'data': pred}], wide=True, money=True)]
    rows = [{'cells': [d, v]} for d, v in zip(fc['forecast_dates'], fc['forecast'])]
    arows = [{'cells': [a['date'], a['value']]} for a in fc['anomalies']]
    tables = [table('Forecast, next 14 days', ['Date', 'Expected revenue'], rows),
              table('Unusual days (z-score above 2.5)', ['Date', 'Revenue'], arows, 'No unusual days found.')]
    notes = [('info', f"Expected revenue over the next 14 days: KES {sum(fc['forecast']):,.0f}. "
                      'A forecast is a guide, not a promise: it assumes recent trends continue.')]
    return dash(request, 'Sales forecast', [], charts, tables, notes=notes)


@role_required('analyst', 'admin', 'developer')
@require_POST
def analyst_refresh(request):
    if cache.add('etl:lock', 1, 120):
        try:
            run = etl.run_etl()
            messages.success(request, f'Warehouse rebuilt: {run.fact_rows} sales rows.')
        except Exception as exc:
            messages.error(request, f'The build failed: {exc}')
    else:
        messages.info(request, 'A rebuild ran a moment ago. Please wait a minute.')
    return redirect(request.META.get('HTTP_REFERER') or 'portals:analyst_home')


@role_required('analyst', 'admin', 'developer')
def analyst_export(request, kind):
    if kind == 'sales':
        rows = FactSales.objects.select_related('date', 'shop', 'product', 'customer').order_by('-date_id')[:20000]
        return csv_response('sales.csv', ['date', 'order', 'shop', 'product', 'customer', 'qty', 'gross', 'discount', 'net',
                                          'commission'],
                            [[r.date_id, r.order_number, r.shop.name, r.product.name, r.customer.name, r.quantity, r.gross,
                              r.discount, r.net, r.commission] for r in rows])
    if kind == 'rfm':
        rows = etl.latest('rfm').get('rows', [])
        return csv_response('customer-segments.csv', ['customer', 'segment', 'rfm', 'recency_days', 'orders', 'spend'],
                            [[r['name'], r['segment'], r['rfm_score'], r['recency_days'], r['frequency'], r['monetary']]
                             for r in rows])
    if kind == 'abc':
        rows = etl.latest('abc').get('rows', [])
        return csv_response('product-abc.csv', ['product', 'revenue', 'share', 'class'],
                            [[r['name'], r['revenue'], round(r['share'], 4), r['abc']] for r in rows])
    if kind == 'basket':
        rows = etl.latest('basket').get('rules', [])
        return csv_response('basket-pairs.csv', ['if_buys', 'also_buys', 'orders', 'support', 'confidence', 'lift'],
                            [[r['a_name'], r['b_name'], r['count'], r['support'], r['confidence'], r['lift']] for r in rows])
    return redirect('portals:analyst_home')


# ---------------------------------------------------------------------- CEO
@role_required('ceo', 'admin')
def ceo_home(request):
    k = queries.kpis(None, 30)
    monthly = queries.monthly_series()
    if not monthly:
        return _no_data(request)
    take = (float(k['commission']) / float(k['revenue']) * 100) if k['revenue'] else 0
    today = timezone.localdate()
    staff_total = get_user_model().objects.filter(
        Q(role__in=PLATFORM_ROLES) | Q(role='seller_staff'), is_active=True).count()
    present = Attendance.objects.filter(date=today).count()
    kpis = [kpi('Revenue (30 days)', k['revenue'], k['revenue_growth'], 'vs previous 30 days', 'wallet', True),
            kpi('Commission earned', k['commission'], icon='wallet', money=True, hint=f'{take:.1f}% take rate'),
            kpi('Orders', k['orders'], k['orders_growth'], 'vs previous 30 days', 'box'),
            kpi('Active shops', Shop.objects.filter(status=ShopStatus.ACTIVE).count(), icon='store'),
            kpi('Average order', k['aov'], icon='chart', money=True),
            kpi('Staff present today', f'{present}/{staff_total}', icon='clock')]
    fc = etl.latest('forecast')
    segs = queries.customer_segments()
    shops = queries.top_shops(90, 8)
    cats = queries.by_category()
    charts = [chart('m', 'bar', 'Revenue and commission by month', [m['month'] for m in monthly],
                    [{'label': 'Revenue', 'data': [m['revenue'] for m in monthly]},
                     {'label': 'Commission', 'data': [m['commission'] for m in monthly]}], wide=True, money=True),
              chart('shops', 'bar', 'Top shops (90 days)', [s['name'] for s in shops],
                    [{'label': 'Revenue', 'data': [float(s['rev']) for s in shops]}], money=True),
              chart('cat', 'doughnut', 'Category mix', [c['cat'] for c in cats],
                    [{'label': 'Revenue', 'data': [float(c['rev']) for c in cats]}], money=True),
              chart('seg', 'doughnut', 'Customer health', [s['segment'] for s in segs],
                    [{'label': 'Customers', 'data': [s['n'] for s in segs]}])]
    notes = []
    if fc.get('forecast'):
        notes.append(('info', f"Forecast: about KES {sum(fc['forecast']):,.0f} in sales over the next 14 days."))
    owed = Payout.objects.filter(status__in=['requested', 'approved'])
    if owed.exists():
        notes.append(('warn', f"{owed.count()} payout request(s) are waiting, KES {sum(p.amount for p in owed):,.0f} in total."))
    return dash(request, 'Executive view', kpis, charts, [], notes=notes, subtitle='Read-only summary for decision making')


@role_required('ceo', 'admin')
def ceo_shops(request):
    rows = [{'cells': [s['name'], s['rev'], s['orders'], s['comm']]} for s in queries.top_shops(90, 50)]
    return listing(request, 'Shops league table (90 days)', ['Shop', 'Revenue', 'Orders', 'Commission to Nyota'], rows,
                   empty='No sales in the warehouse yet.')


# ---------------------------------------------------------------- developer
def _check(name, fn):
    t = time.perf_counter()
    try:
        detail = fn()
        return {'name': name, 'ok': True, 'detail': detail or 'OK', 'ms': round((time.perf_counter() - t) * 1000, 1)}
    except Exception as exc:
        return {'name': name, 'ok': False, 'detail': f'{type(exc).__name__}: {exc}'[:160],
                'ms': round((time.perf_counter() - t) * 1000, 1)}


def _db():
    with connection.cursor() as cur:
        cur.execute('SELECT 1')
    return connection.vendor


def _cache():
    cache.set('healthcheck', '1', 10)
    assert cache.get('healthcheck') == '1'
    return settings.CACHES['default']['BACKEND'].rsplit('.', 1)[-1]


def _layer():
    layer = get_channel_layer()
    async_to_sync(layer.group_send)('healthcheck', {'type': 'noop'})
    return type(layer).__name__


@role_required('developer', 'admin')
def developer_home(request):
    checks = [_check('Database', _db), _check('Cache', _cache), _check('Channel layer (live chat)', _layer)]
    flags = [
        ('DEBUG', settings.DEBUG), ('Redis configured', bool(settings.REDIS_URL)),
        ('Celery runs inline (no worker)', settings.CELERY_TASK_ALWAYS_EAGER),
        ('M-Pesa configured', mpesa.is_configured()), ('Stripe configured', stripe_service.is_configured()),
        ('Payments demo mode', settings.PAYMENTS_SIMULATE),
        ('Email via SMTP', not settings.EMAIL_BACKEND.endswith('console.EmailBackend')),
        ('Google sign-in', bool(settings.OAUTH['google']['client_id'])),
        ('GitHub sign-in', bool(settings.OAUTH['github']['client_id'])),
        ('Shop subdomains', bool(settings.ROOT_DOMAIN)),
    ]
    counts = {'Users': request.user.__class__.objects.count(), 'Shops': Shop.objects.count(),
              'Orders': Order.objects.count(), 'Audit entries': AuditLog.objects.count(),
              'Warehouse rows': FactSales.objects.count()}
    return show(request, 'portal/developer_home.html', {
        'checks': checks, 'flags': flags, 'counts': counts,
        'versions': {'Python': sys.version.split()[0], 'Django': django.get_version(), 'Platform': platform.platform()},
    }, 'System health')


@role_required('developer', 'admin')
def developer_audit(request):
    ok, bad_id, checked = verify_chain()
    rows = [{'cells': [a.id, timezone.localtime(a.created_at).strftime('%d %b %H:%M:%S'), a.actor_label or '-', a.action,
                       a.row_hash[:12] + '...']} for a in AuditLog.objects.all()[:25]]
    note = ('ok', f'Hash chain intact: {checked} entries verified.') if ok else (
        'bad', f'Chain broken at entry #{bad_id}. Something was edited or removed after it was written.')
    return dash(request, 'Audit integrity', [kpi('Entries verified', checked, icon='shield')], [],
                [table('Latest entries', ['#', 'Time', 'Who', 'Action', 'Hash'], rows)], notes=[note],
                subtitle='Every entry stores the hash of the one before it')


@role_required('developer', 'admin')
def developer_webhooks(request):
    rows = [{'cells': [timezone.localtime(w.received_at).strftime('%d %b %H:%M:%S'), w.provider,
                       badge('active' if w.signature_ok else 'failed', 'valid' if w.signature_ok else 'bad signature'),
                       badge('succeeded' if w.handled else 'pending', 'handled' if w.handled else 'not handled'),
                       w.note or '-', w.payload[:90]]} for w in WebhookLog.objects.all()[:60]]
    return listing(request, 'Payment webhooks', ['Received', 'Provider', 'Signature', 'Result', 'Note', 'Payload'], rows,
                   empty='No webhook calls received yet.')


@role_required('developer', 'admin')
def developer_api(request):
    token = Token.objects.filter(user=request.user).first()
    return show(request, 'portal/developer_api.html', {'token': token}, 'API access')


@role_required('developer', 'admin')
@require_POST
def developer_token(request):
    Token.objects.filter(user=request.user).delete()
    Token.objects.create(user=request.user)
    record('api.token_regenerated', target=request.user, request=request)
    messages.success(request, 'New API token created. The old one no longer works.')
    return redirect('portals:developer_api')


@role_required('developer', 'admin')
def developer_jobs(request):
    runs = EtlRun.objects.all()[:15]
    rows = [{'cells': [timezone.localtime(r.started_at).strftime('%d %b %H:%M:%S'),
                       badge('succeeded' if r.ok else 'failed', 'ok' if r.ok else 'failed'), r.fact_rows, r.message]}
            for r in runs]
    return listing(request, 'Warehouse jobs', ['Started', 'Result', 'Sales rows', 'Message'], rows,
                   empty='The warehouse has not been built yet.',
                   extra_actions=[('Rebuild now', '/staff/analyst/refresh/', 'post')])


# ------------------------------------------------------------------ support
@role_required('support', 'admin')
def support_home(request):
    convs = (Conversation.objects.filter(kind=ConversationKind.SUPPORT).prefetch_related('memberships__user')
             .order_by('-updated_at')[:30])
    rows = []
    for c in convs:
        who = ', '.join(m.user.display_name for m in c.memberships.all())
        last = c.messages.order_by('-id').first()
        rows.append({'cells': [who, (last.body[:60] if last and not last.deleted else '-'),
                               timezone.localtime(c.updated_at).strftime('%d %b %H:%M')], 'url': f'/chat/{c.pk}/'})
    q = request.GET.get('number', '').strip().upper()
    if q:
        order = Order.objects.filter(number=q).first()
        if order:
            return redirect('portals:support_order', number=order.number)
        messages.error(request, 'No order with that number.')
    return listing(request, 'Support desk', ['Customer', 'Last message', 'Updated'], rows,
                   filters=[{'name': 'number', 'label': 'Find an order by number', 'type': 'text', 'value': q}],
                   empty='No support conversations yet.')


@role_required('support', 'admin')
def support_order(request, number):
    from .customer import order_context
    order = get_object_or_404(Order, number=number)
    ctx = order_context(order, 'support')
    ctx['customer'] = order.customer
    return show(request, 'portal/order_detail.html', ctx, f'Order {order.number}')
