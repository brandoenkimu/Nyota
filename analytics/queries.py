"""Read-side helpers over the warehouse used by the dashboards (analyst, CEO, seller, admin)."""
import datetime as dt
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import DimCustomer, FactSales


def _f(qs, shop_id=None, days=None):
    if shop_id:
        qs = qs.filter(shop__shop_id=shop_id)
    if days:
        qs = qs.filter(date_id__gte=timezone.localdate() - dt.timedelta(days=days))
    return qs


def kpis(shop_id=None, days=30):
    cur = _f(FactSales.objects.all(), shop_id, days).aggregate(
        revenue=Sum('net'), orders=Count('order_number', distinct=True), units=Sum('quantity'),
        commission=Sum('commission'), cost=Sum('cost'), earnings=Sum('seller_earnings'))
    prev_qs = FactSales.objects.filter(
        date_id__gte=timezone.localdate() - dt.timedelta(days=days * 2),
        date_id__lt=timezone.localdate() - dt.timedelta(days=days))
    if shop_id:
        prev_qs = prev_qs.filter(shop__shop_id=shop_id)
    prev = prev_qs.aggregate(revenue=Sum('net'), orders=Count('order_number', distinct=True))
    out = {k: (v or 0) for k, v in cur.items()}
    out['aov'] = (Decimal(out['revenue']) / out['orders']) if out['orders'] else 0
    out['gross_profit'] = Decimal(out['revenue']) - Decimal(out['cost']) if out['cost'] else None
    for k in ('revenue', 'orders'):
        p = prev[k] or 0
        out[f'{k}_growth'] = round((float(out[k]) - float(p)) / float(p) * 100, 1) if p else None
    customers = _f(FactSales.objects.all(), shop_id, days).values('customer').distinct().count()
    out['customers'] = customers
    return out


def daily_series(shop_id=None, days=60):
    rows = (_f(FactSales.objects.all(), shop_id, days).values('date_id')
            .annotate(rev=Sum('net'), orders=Count('order_number', distinct=True)).order_by('date_id'))
    return [{'date': r['date_id'].isoformat(), 'revenue': float(r['rev']), 'orders': r['orders']} for r in rows]


def monthly_series(shop_id=None):
    rows = (_f(FactSales.objects.all(), shop_id).annotate(m=TruncMonth('date__date')).values('m')
            .annotate(rev=Sum('net'), comm=Sum('commission')).order_by('m'))
    return [{'month': r['m'].strftime('%b %Y'), 'revenue': float(r['rev']), 'commission': float(r['comm'])}
            for r in rows if r['m']]


def top_products(shop_id=None, days=90, limit=10):
    rows = (_f(FactSales.objects.all(), shop_id, days).values(name=F('product__name'), shop_name=F('shop__name'))
            .annotate(rev=Sum('net'), units=Sum('quantity')).order_by('-rev')[:limit])
    return list(rows)


def top_shops(days=90, limit=10):
    rows = (_f(FactSales.objects.all(), None, days).values(name=F('shop__name'))
            .annotate(rev=Sum('net'), orders=Count('order_number', distinct=True), comm=Sum('commission'))
            .order_by('-rev')[:limit])
    return list(rows)


def by_category(shop_id=None, days=90):
    rows = (_f(FactSales.objects.all(), shop_id, days).values(cat=F('product__category'))
            .annotate(rev=Sum('net')).order_by('-rev'))
    return list(rows)


def by_county(shop_id=None, days=90):
    rows = (_f(FactSales.objects.all(), shop_id, days).values(county=F('customer__county'))
            .annotate(rev=Sum('net')).order_by('-rev')[:10])
    return [{'county': r['county'] or 'Unknown', 'rev': r['rev']} for r in rows]


def weekday_pattern(shop_id=None, days=90):
    names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    rows = (_f(FactSales.objects.all(), shop_id, days).values(wd=F('date__weekday'))
            .annotate(rev=Sum('net')).order_by('wd'))
    data = {r['wd']: float(r['rev']) for r in rows}
    return [{'day': names[i], 'revenue': data.get(i, 0.0)} for i in range(7)]


def customer_segments():
    rows = DimCustomer.objects.exclude(segment='').values('segment').annotate(n=Count('id')).order_by('-n')
    return list(rows)
