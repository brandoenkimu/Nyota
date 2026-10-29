from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=140)
    body = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']


class HeroSlide(models.Model):
    """Slides of the home-page carousel, managed by administrators."""
    kicker = models.CharField(max_length=60, blank=True)
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=200, blank=True)
    cta_label = models.CharField(max_length=40, default='Explore')
    cta_url = models.CharField(max_length=200, default='/products/')
    art_variant = models.PositiveSmallIntegerField(default=0)
    sort = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort', 'id']


class SiteSetting(models.Model):
    key = models.CharField(max_length=60, unique=True)
    value = models.TextField(blank=True)

    def __str__(self):
        return self.key
