from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_default_plans(sender, **kwargs):
    """First migrate after this app is installed: seed a few starter plans so the Advertise page
    isn't empty before anyone has touched the admin. Safe to run every time — it only adds, never edits."""
    from .models import PromotionPlan
    if PromotionPlan.objects.exists():
        return
    PromotionPlan.objects.bulk_create([
        PromotionPlan(name='3-Day Spotlight', days=3, price=500, sort=1,
                      description='A quick boost for a sale or new launch.'),
        PromotionPlan(name='2-Week Feature', days=14, price=2000, sort=2,
                      description='Our most popular plan.'),
        PromotionPlan(name='Monthly Showcase', days=30, price=3500, sort=3,
                      description='Best value for an established shop.'),
    ])


class AdsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ads'

    def ready(self):
        post_migrate.connect(_create_default_plans, sender=self)
