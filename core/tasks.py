import logging

from celery import shared_task

from .mail import deliver

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, subject, text, html, recipients):
    try:
        deliver(subject, text, html, recipients)
    except Exception as exc:
        log.warning('e-mail "%s" failed: %s', subject, exc)
        raise self.retry(exc=exc)
