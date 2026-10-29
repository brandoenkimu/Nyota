from celery import shared_task
from django.db.models import F

from core.notify import notify


@shared_task
def low_stock_alerts():
    """Tell each shop owner about products that are running low."""
    from .models import Product
    low = (Product.objects.filter(is_active=True, stock__lte=F('low_stock_threshold'))
           .select_related('shop__owner'))
    count = 0
    for p in low:
        notify(p.shop.owner, f'Low stock: {p.name}', f'Only {p.stock} left.', '/seller/products/')
        count += 1
    return count
