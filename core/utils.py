import re
import unicodedata
from decimal import Decimal

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


def paginate(request, queryset, per_page=20):
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def unique_username(base: str, exists) -> str:
    text = unicodedata.normalize('NFKD', base or '').encode('ascii', 'ignore').decode().lower()
    text = re.sub(r'[^a-z0-9._]', '', text) or 'user'
    candidate, n = text[:140], 2
    while exists(candidate):
        candidate = f'{text[:135]}{n}'
        n += 1
    return candidate


def dec(value, default='0') -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def kes(value, currency='KES') -> str:
    try:
        return f'{currency} {Decimal(str(value)):,.0f}'
    except Exception:
        return f'{currency} 0'
