"""The data warehouse: a star schema (one fact table, four dimensions) rebuilt from live data by
analytics.etl. Dimensions keep plain ids of the source rows rather than foreign keys, so the
warehouse can later be moved to its own database without touching the shop tables."""
from django.db import models


class DimDate(models.Model):
    date = models.DateField(primary_key=True)
    year = models.PositiveSmallIntegerField()
    quarter = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()
    day = models.PositiveSmallIntegerField()
    weekday = models.PositiveSmallIntegerField()          # 0 = Monday
    is_weekend = models.BooleanField(default=False)


class DimShop(models.Model):
    shop_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=80)
    city = models.CharField(max_length=80, blank=True)
    county = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=12)
    opened_on = models.DateField(null=True)


class DimProduct(models.Model):
    product_id = models.PositiveIntegerField(unique=True)
    shop = models.ForeignKey(DimShop, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    brand = models.CharField(max_length=80, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True)


class DimCustomer(models.Model):
    customer_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=150)
    county = models.CharField(max_length=80, blank=True)
    first_order_on = models.DateField(null=True)
    segment = models.CharField(max_length=30, blank=True)
    rfm = models.CharField(max_length=3, blank=True)


class FactSales(models.Model):
    date = models.ForeignKey(DimDate, on_delete=models.CASCADE, related_name='sales')
    shop = models.ForeignKey(DimShop, on_delete=models.CASCADE, related_name='sales')
    product = models.ForeignKey(DimProduct, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(DimCustomer, on_delete=models.CASCADE, related_name='sales')
    order_number = models.CharField(max_length=20, db_index=True)
    quantity = models.PositiveIntegerField()
    gross = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=14, decimal_places=2)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    seller_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=['date', 'shop']), models.Index(fields=['customer', 'date'])]


class MiningResult(models.Model):
    """Output of a mining job (customer segments, basket rules, forecast, ABC classes, ...)."""
    kind = models.CharField(max_length=30, db_index=True)
    shop_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)   # null = whole platform
    payload = models.JSONField(default=dict)
    built_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['kind', 'shop_id'])]


class EtlRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    fact_rows = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-started_at']
