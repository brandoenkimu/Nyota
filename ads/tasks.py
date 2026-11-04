from celery import shared_task

from .services import expire_promotions


@shared_task
def expire_promotions_task():
    return expire_promotions()
