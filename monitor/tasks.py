import datetime as dt

from celery import shared_task
from django.utils import timezone

from .models import ActivityEvent, ErrorEvent, ErrorGroup, ErrorStatus


@shared_task
def purge_old_monitoring(activity_days=180, error_days=365):
    """Keep the tracking tables small: old page views and old closed errors are removed."""
    a = ActivityEvent.objects.filter(created_at__lt=timezone.now() - dt.timedelta(days=activity_days)).delete()[0]
    ErrorEvent.objects.filter(created_at__lt=timezone.now() - dt.timedelta(days=error_days)).delete()
    g = ErrorGroup.objects.filter(last_seen__lt=timezone.now() - dt.timedelta(days=error_days),
                                  status__in=[ErrorStatus.RESOLVED, ErrorStatus.IGNORED]).delete()[0]
    return {'activity': a, 'error_groups': g}
