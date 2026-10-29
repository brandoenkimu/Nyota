"""Warehouse build (ETL) and mining jobs.

Extract  : paid-or-COD orders that are not cancelled, from the live tables
Transform: flatten to one row per order line, attach date / shop / product / customer dimensions
Load     : rebuild the star schema, then run the mining jobs and store their output

It rebuilds everything each run (idempotent). That is perfectly fine up to a few hundred thousand
order lines; beyond that, switch to incremental loads keyed on Order.placed_at.
"""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalog.models import Product, Review
from orders.models import OrderItem, ShopOrderStatus
from shops.models import Shop

from . import mining
from .models import DimCustomer, DimDate, DimProduct, DimShop, EtlRun, FactSales, MiningResult


def _valid_items():
    """Order lines that count as sales: not cancelled/returned, and either paid or pay-on-delivery."""
    from django.db.models import Q
    return (OrderItem.objects
            .filter(Q(shop_order__order__payment_status='paid') | Q(shop_order__order__payment_method='cod'))
            .exclude(shop_order__status__in=[ShopOrderStatus.CANCELLED, ShopOrderStatus.RETURNED])
            .select_related('shop_order__order__customer', 'shop_order__shop', 'product__category'))


def _dim_date(day):
    iso = day.isocalendar()
    return DimDate(date=day, year=day.year, quarter=(day.month - 1) // 3 + 1, month=day.month, week=iso[1],
                   day=day.day, weekday=day.weekday(), is_weekend=day.weekday() >= 5)


def run_etl():
    run = EtlRun.objects.create()
    try:
        with transaction.atomic():
            rows = _build()
        run.ok, run.fact_rows, run.message = True, rows, 'Warehouse and mining results rebuilt.'
    except Exception as exc:  # recorded, then re-raised so the caller/task sees it
        run.message = f'{type(exc).__name__}: {exc}'[:300]
        run.finished_at = timezone.now()
        run.save()
        raise
    run.finished_at = timezone.now()
    run.save()
    return run


def _build():
    FactSales.objects.all().delete()
    DimProduct.objects.all().delete()
    DimShop.objects.all().delete()
    DimCustomer.objects.all().delete()
    DimDate.objects.all().delete()
    MiningResult.objects.all().delete()

    items = list(_valid_items())
    shops = {s.pk: s for s in Shop.objects.all()}
    dshops = {}
    for s in shops.values():
        dshops[s.pk] = DimShop.objects.create(shop_id=s.pk, name=s.name, city=s.city, county=s.county,
                                              status=s.status, opened_on=s.created_at.date())
    dprods = {}
    for p in Product.objects.select_related('category'):
        dprods[p.pk] = DimProduct(product_id=p.pk, shop=dshops[p.shop_id], name=p.name, category=p.category.name,
                                  brand=p.brand, price=p.price, cost=p.cost_price)
    DimProduct.objects.bulk_create(dprods.values())
    dprods = {d.product_id: d for d in DimProduct.objects.all()}

    # customers and their first order date
    cust, first = {}, {}
    for it in items:
        o = it.shop_order.order
        cust[o.customer_id] = o.customer
        d = timezone.localtime(o.placed_at).date()
        first[o.customer_id] = min(first.get(o.customer_id, d), d)
    dcusts = {}
    for cid, u in cust.items():
        dcusts[cid] = DimCustomer(customer_id=cid, name=u.display_name, county=_county(u), first_order_on=first[cid])
    DimCustomer.objects.bulk_create(dcusts.values())
    dcusts = {d.customer_id: d for d in DimCustomer.objects.all()}

    days = {}
    facts = []
    for it in items:
        so = it.shop_order
        o = so.order
        day = timezone.localtime(o.placed_at).date()
        days.setdefault(day, _dim_date(day))
        gross = it.unit_price * it.quantity
        share = (gross / so.subtotal) if so.subtotal else Decimal(0)
        discount = (so.discount * share).quantize(Decimal('0.01'))
        net = gross - discount
        commission = (so.commission_amount * share).quantize(Decimal('0.01'))
        pid = it.product_id
        if pid not in dprods:                       # product deleted since: skip (history kept in orders)
            continue
        facts.append(FactSales(
            date_id=day, shop=dshops[so.shop_id], product=dprods[pid], customer=dcusts[o.customer_id],
            order_number=o.number, quantity=it.quantity, gross=gross, discount=discount, net=net,
            cost=(it.unit_cost or Decimal(0)) * it.quantity, commission=commission,
            seller_earnings=net - commission))
    # make sure every day in the range exists so charts have no holes
    if days:
        d, end = min(days), max(days)
        while d <= end:
            days.setdefault(d, _dim_date(d))
            d += dt.timedelta(days=1)
    DimDate.objects.bulk_create(days.values())
    FactSales.objects.bulk_create(facts, batch_size=1000)

    _mine(items, shops, dprods, dcusts)
    return len(facts)


def _county(user):
    addr = user.addresses.first() if hasattr(user, 'addresses') else None
    return addr.county if addr else ''


def _store(kind, payload, shop_id=None):
    MiningResult.objects.create(kind=kind, shop_id=shop_id, payload=payload)


def _mine(items, shops, dprods, dcusts):
    today = timezone.localdate()
    # ---- customer segmentation (platform wide)
    orders, seen = [], set()
    for it in items:
        o = it.shop_order.order
        if o.pk in seen:
            continue
        seen.add(o.pk)
        orders.append({'customer_id': o.customer_id, 'date': timezone.localtime(o.placed_at).date(),
                       'amount': float(o.total)})
    segs = mining.rfm_segments(orders, today)
    by_id = {s['customer_id']: s for s in segs}
    for cid, dc in dcusts.items():
        s = by_id.get(cid)
        if s:
            dc.segment, dc.rfm = s['segment'], s['rfm_score']
    DimCustomer.objects.bulk_update(list(dcusts.values()), ['segment', 'rfm'])
    names = {cid: dc.name for cid, dc in dcusts.items()}
    for s in segs:
        s['name'] = names.get(s['customer_id'], str(s['customer_id']))
    summary = defaultdict(lambda: {'customers': 0, 'revenue': 0.0})
    for s in segs:
        summary[s['segment']]['customers'] += 1
        summary[s['segment']]['revenue'] += s['monetary']
    _store('rfm', {'rows': segs[:200], 'summary': dict(summary)})

    # ---- daily revenue series, forecast and anomalies (platform and per shop)
    daily = defaultdict(lambda: defaultdict(float))        # shop_id (0 = all) -> date -> net
    for it in items:
        so = it.shop_order
        d = timezone.localtime(so.order.placed_at).date()
        v = float(it.unit_price * it.quantity)
        daily[0][d] += v
        daily[so.shop_id][d] += v
    for sid, series in daily.items():
        start, end = min(series), max(series)
        n = (end - start).days + 1
        dates = [start + dt.timedelta(days=i) for i in range(n)]
        values = [series.get(d, 0.0) for d in dates]
        fc = mining.holt_forecast(values, horizon=14)
        anomalies = mining.detect_anomalies(values)
        _store('forecast', {
            'dates': [d.isoformat() for d in dates], 'values': [round(v, 2) for v in values],
            'average7': [round(v, 2) for v in mining.moving_average(values, 7)],
            'forecast_dates': [(end + dt.timedelta(days=i + 1)).isoformat() for i in range(len(fc))],
            'forecast': [round(v, 2) for v in fc],
            'anomalies': [{'date': dates[i].isoformat(), 'value': round(values[i], 2)} for i in anomalies],
        }, shop_id=sid or None)

    # ---- ABC classification and market basket (platform and per shop)
    revenue = defaultdict(lambda: defaultdict(float))     # shop_id (0 = all) -> product_id -> revenue
    baskets = defaultdict(lambda: defaultdict(set))       # shop_id -> order_id -> product ids
    for it in items:
        if not it.product_id:
            continue
        sid = it.shop_order.shop_id
        rev = float(it.unit_price * it.quantity)
        for key in (0, sid):
            revenue[key][it.product_id] += rev
            baskets[key][it.shop_order.order_id].add(str(it.product_id))
    pname = {pid: d.name for pid, d in dprods.items()}
    for key, rows in revenue.items():
        abc = mining.abc_classification([{'id': pid, 'revenue': r} for pid, r in rows.items()])
        for r in abc:
            r['name'] = pname.get(r['id'], str(r['id']))
        _store('abc', {'rows': abc[:100]}, shop_id=key or None)
        pairs = mining.market_basket([sorted(b) for b in baskets[key].values()],
                                     min_support=0.02 if key == 0 else 0.03, top=15)
        for p in pairs:
            p['a_name'] = pname.get(int(p['a']), p['a'])
            p['b_name'] = pname.get(int(p['b']), p['b'])
        _store('basket', {'rules': pairs, 'baskets': len(baskets[key])}, shop_id=key or None)

    # ---- review sentiment per shop
    by_shop = defaultdict(list)
    for r in Review.objects.select_related('product'):
        by_shop[r.product.shop_id].append(r.sentiment)
        by_shop[0].append(r.sentiment)
    for key, vals in by_shop.items():
        avg = sum(vals) / len(vals)
        _store('sentiment', {
            'average': round(avg, 3), 'label': mining.sentiment_label(avg), 'reviews': len(vals),
            'positive': sum(1 for v in vals if mining.sentiment_label(v) == 'positive'),
            'negative': sum(1 for v in vals if mining.sentiment_label(v) == 'negative')}, shop_id=key or None)


def latest(kind, shop_id=None):
    """Most recent mining payload, or {} if the warehouse has not been built yet."""
    row = MiningResult.objects.filter(kind=kind, shop_id=shop_id).order_by('-built_at').first()
    return row.payload if row else {}
