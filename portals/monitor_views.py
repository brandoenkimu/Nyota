"""Error tracker + member timeline (support, admin, developer) and the usage / warehouse pages (analyst)."""
import datetime as dt

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from analytics.models import DimCustomer, DimDate, DimProduct, DimShop, EtlRun, FactSales, MiningResult
from audit.models import AuditLog
from audit.service import record
from core.utils import paginate
from monitor.models import ActivityEvent, ErrorEvent, ErrorGroup, ErrorStatus
from orders.models import Order

from .common import badge, chart, dash, kpi, link, listing, role_required, show, table

User = get_user_model()
FIXERS = ('support', 'admin', 'developer')


# ------------------------------------------------------------- error tracker
@role_required(*FIXERS)
def error_list(request):
    status, source, q = request.GET.get('status', 'open'), request.GET.get('source', ''), request.GET.get('q', '').strip()
    qs = ErrorGroup.objects.select_related('assigned_to')
    if status == 'open':
        qs = qs.filter(status__in=[ErrorStatus.OPEN, ErrorStatus.INVESTIGATING])
    elif status:
        qs = qs.filter(status=status)
    if source:
        qs = qs.filter(source=source)
    if q:
        qs = qs.filter(Q(message__icontains=q) | Q(exc_type__icontains=q) | Q(location__icontains=q)
                       | Q(events__reference__iexact=q) | Q(events__user_label__icontains=q)).distinct()
    page = paginate(request, qs, 25)
    rows = [{'cells': [link(f'/staff/errors/{g.pk}/', g.exc_type or g.source), g.message[:80], g.location[-50:],
                       g.count, g.users_affected, timezone.localtime(g.last_seen).strftime('%d %b %H:%M'),
                       g.assigned_to.display_name if g.assigned_to else '-', badge(g.status, g.get_status_display())],
             'url': f'/staff/errors/{g.pk}/'} for g in page.object_list]
    filters = [{'name': 'q', 'label': 'Search (type, text, user, or reference like NY-1A2B3C)', 'type': 'text', 'value': q},
               {'name': 'status', 'label': 'Status', 'type': 'select', 'value': status,
                'options': [('open', 'Needs attention'), ('', 'All')] + list(ErrorStatus.choices)},
               {'name': 'source', 'label': 'Where', 'type': 'select', 'value': source,
                'options': [('', 'Anywhere'), ('server', 'Server'), ('browser', 'Browser')]}]
    return listing(request, 'Error tracker', ['Problem', 'Message', 'Where', 'Times', 'Users', 'Last seen', 'Owner', 'Status'],
                   rows, page, filters, empty='No errors. Everything is calm.',
                   subtitle='Identical crashes are grouped into one ticket. Members see a reference like NY-1A2B3C on the error page.')


@role_required(*FIXERS)
def error_detail(request, pk):
    g = get_object_or_404(ErrorGroup.objects.select_related('assigned_to'), pk=pk)
    if request.method == 'POST':
        action, note = request.POST.get('action'), request.POST.get('note', '').strip()
        if action == 'take':
            g.assigned_to, g.status = request.user, ErrorStatus.INVESTIGATING
        elif action == 'resolve':
            g.status, g.resolved_at = ErrorStatus.RESOLVED, timezone.now()
            g.resolution_note = note or g.resolution_note
        elif action == 'ignore':
            g.status = ErrorStatus.IGNORED
        elif action == 'reopen':
            g.status, g.resolved_at = ErrorStatus.OPEN, None
        elif action == 'note':
            g.resolution_note = note
        g.save()
        record('system.error_updated', target=g, request=request, error_action=action)
        messages.success(request, 'Saved.')
        return redirect('portals:error_detail', pk=pk)
    events = list(g.events.select_related('user')[:30])
    return show(request, 'portal/error_detail.html', {'g': g, 'events': events}, f'Error: {g.exc_type or g.source}')


# ----------------------------------------------------------- member timeline
@role_required('support', 'admin')
def member_lookup(request):
    q = request.GET.get('q', '').strip()
    rows = []
    if q:
        qs = User.objects.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                                 | Q(last_name__icontains=q) | Q(phone__icontains=q))[:30]
        ev = ErrorEvent.objects.filter(reference__iexact=q).select_related('user').first()
        if ev and ev.user:
            return redirect('portals:member_timeline', pk=ev.user_id)
        rows = [{'cells': [link(f'/staff/members/{u.pk}/', u.display_name), u.email, u.get_role_display(),
                           timezone.localtime(u.last_seen).strftime('%d %b %H:%M') if u.last_seen else '-'],
                 'url': f'/staff/members/{u.pk}/'} for u in qs]
    return listing(request, 'Find a member', ['Name', 'Email', 'Role', 'Last seen'], rows,
                   filters=[{'name': 'q', 'label': 'Name, email, phone or error reference', 'type': 'text', 'value': q}],
                   empty='Search for the member who reported a problem.' if not q else 'No match.')


@role_required('support', 'admin')
def member_timeline(request, pk):
    m = get_object_or_404(User, pk=pk)
    record('support.member_viewed', target=m, request=request)       # looking at someone's trail is itself audited
    acts = list(ActivityEvent.objects.filter(user=m)[:60])
    errs = list(ErrorEvent.objects.filter(user=m).select_related('group')[:15])
    audits = list(AuditLog.objects.filter(actor=m)[:40])
    orders = list(Order.objects.filter(customer=m)[:8]) if m.role == 'customer' else []
    return show(request, 'portal/member_timeline.html', {'m': m, 'acts': acts, 'errs': errs, 'audits': audits,
                                                          'orders': orders}, f'Timeline: {m.display_name}')


# --------------------------------------------------------------- analyst: usage
def page_group(path):
    segs = [s for s in path.strip('/').split('/') if s]
    if not segs:
        return 'Home'
    if segs[0] in ('p', 'shop', 'category') and len(segs) > 1:
        return f'/{segs[0]}/*'
    if segs[0] == 'account' and len(segs) > 2:
        return '/account/orders/*'
    if segs[0] == 'chat' and len(segs) > 1:
        return '/chat/*'
    return '/' + '/'.join(segs[:2]) + '/'


@role_required('analyst', 'admin', 'ceo')
def analyst_usage(request):
    days = 30 if request.GET.get('days') != '7' else 7
    since = timezone.now() - dt.timedelta(days=days)
    qs = ActivityEvent.objects.filter(created_at__gte=since)
    views = qs.filter(kind='view')
    sessions = qs.values('session').distinct().count()
    members = qs.exclude(user=None).values('user').distinct().count()
    n_views = views.count()
    avg_ms = int(views.aggregate(a=Avg('ms'))['a'] or 0)
    errors = ErrorEvent.objects.filter(created_at__gte=since).count()

    def sess(**f):
        return qs.filter(**f).values('session').distinct().count()
    visitors = sessions
    product_viewers = qs.filter(kind='view', path__startswith='/p/').values('session').distinct().count()
    carters, buyers = sess(kind='add_to_cart'), sess(kind='order')
    abandon = round(100 * (carters - buyers) / carters) if carters else 0
    kpis = [kpi('Visits (sessions)', visitors, icon='users'), kpi('Signed-in members', members, icon='user'),
            kpi('Page views', n_views, icon='eye'), kpi('Cart abandonment', f'{abandon}%', hint='added to cart, never ordered', icon='cart'),
            kpi('Avg page time', f'{avg_ms} ms', hint=f'{errors} errors in {days} days', icon='pulse')]
    daily = (views.annotate(d=TruncDate('created_at')).values('d').annotate(v=Count('id'), s=Count('session', distinct=True))
             .order_by('d'))
    hours = {h: 0 for h in range(24)}
    for r in views.annotate(h=ExtractHour('created_at', tzinfo=timezone.get_current_timezone())).values('h').annotate(c=Count('id')):
        hours[r['h']] = r['c']
    dev = list(views.values('device').annotate(c=Count('id')).order_by('-c'))
    funnel = [('Visited', visitors), ('Viewed a product', product_viewers), ('Added to cart', carters), ('Placed an order', buyers)]
    groups = {}
    for r in views.values('path').annotate(c=Count('id'), ms=Avg('ms')).order_by('-c')[:600]:
        g = groups.setdefault(page_group(r['path']), [0, 0])
        g[0] += r['c']; g[1] += r['c'] * (r['ms'] or 0)
    top_pages = sorted(groups.items(), key=lambda kv: -kv[1][0])[:12]
    slow = sorted(((k, v[0], int(v[1] / v[0])) for k, v in groups.items() if v[0] >= 5), key=lambda x: -x[2])[:8]
    searches = list(qs.filter(kind='search').values('label').annotate(c=Count('id'), r=Avg('count')).order_by('-c')[:10])
    nohit = list(qs.filter(kind='search', count=0).values('label').annotate(c=Count('id')).order_by('-c')[:10])
    by_role = list(qs.exclude(user=None).values('user__role').annotate(c=Count('id')).order_by('-c'))
    charts = [
        chart('uv', 'line', 'Page views and visits per day', [r['d'].strftime('%d %b') for r in daily],
              [{'label': 'Page views', 'data': [r['v'] for r in daily]}, {'label': 'Visits', 'data': [r['s'] for r in daily]}], wide=True),
        chart('fun', 'bar', 'Shopping funnel (distinct visits)', [f[0] for f in funnel], [{'label': 'Visits', 'data': [f[1] for f in funnel]}]),
        chart('hr', 'bar', 'When people use Nyota (hour of day)', [f'{h:02d}h' for h in range(24)], [{'label': 'Page views', 'data': [hours[h] for h in range(24)]}], wide=True),
        chart('dev', 'doughnut', 'Devices', [d['device'] or 'unknown' for d in dev], [{'label': 'Views', 'data': [d['c'] for d in dev]}]),
        chart('rol', 'bar', 'Activity by role', [r['user__role'] for r in by_role], [{'label': 'Events', 'data': [r['c'] for r in by_role]}]),
    ]
    tables = [
        table('Most visited pages', ['Page', 'Views'], [{'cells': [k, v[0]]} for k, v in top_pages]),
        table('Slowest pages (average ms)', ['Page', 'Views', 'Avg ms'], [{'cells': list(x)} for x in slow], 'Not enough data yet.'),
        table('Top searches', ['Search', 'Times', 'Avg results'], [{'cells': [s['label'], s['c'], int(s['r'] or 0)]} for s in searches], 'No searches yet.'),
        table('Searches with no results (stock these!)', ['Search', 'Times'], [{'cells': [s['label'], s['c']]} for s in nohit], 'None. Nice.'),
    ]
    return dash(request, 'How members use Nyota', kpis, charts, tables,
                actions=[('Last 7 days', '?days=7'), ('Last 30 days', '?days=30')],
                notes=[('info', 'Activity is recorded without personal details beyond the signed-in account, and skipped for browsers that send Do-Not-Track.')],
                subtitle=f'Last {days} days. Visits are counted by anonymised session.')


@role_required('analyst', 'admin', 'ceo', 'developer')
def analyst_warehouse(request):
    last = EtlRun.objects.first()
    counts = [('Dates', DimDate.objects.count()), ('Shops', DimShop.objects.count()), ('Products', DimProduct.objects.count()),
              ('Customers', DimCustomer.objects.count()), ('Sales facts', FactSales.objects.count()),
              ('Mining results', MiningResult.objects.count()), ('Activity events', ActivityEvent.objects.count()),
              ('Error tickets', ErrorGroup.objects.count())]
    kpis = [kpi(n, c, icon='db') for n, c in counts]
    notes = []
    if last:
        notes.append(('info' if last.ok else 'warn', f'Last build {timezone.localtime(last.started_at):%d %b %H:%M}: '
                      f'{"succeeded" if last.ok else "FAILED"}, {last.fact_rows} sales rows. {last.message}'))
    else:
        notes.append(('warn', 'The warehouse has not been built yet. Press "Rebuild warehouse".'))
    results = [{'cells': [m.kind, m.shop_id or 'platform', timezone.localtime(m.built_at).strftime('%d %b %H:%M')]}
               for m in MiningResult.objects.order_by('-built_at')[:15]]
    runs = [{'cells': [timezone.localtime(r.started_at).strftime('%d %b %H:%M'), badge('succeeded' if r.ok else 'failed', 'ok' if r.ok else 'failed'), r.fact_rows]}
            for r in EtlRun.objects.all()[:10]]
    return dash(request, 'Data warehouse', kpis, [], [
        table('Latest mining outputs', ['Kind', 'Scope', 'Built'], results, 'Nothing mined yet.'),
        table('Recent warehouse builds', ['Started', 'Result', 'Sales rows'], runs, 'No builds yet.')],
        actions=[('Rebuild warehouse', '/staff/analyst/refresh/', 'post'), ('Usage analytics', '/staff/analyst/usage/')],
        notes=notes, subtitle='Star schema (dates, shops, products, customers, sales) plus the mining results built from it.')
