import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

log = logging.getLogger(__name__)


def deliver(subject, text, html, recipients):
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, list(recipients))
    if html:
        msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)


def send_mail_async(subject, text, html, recipients):
    """Queue the mail on Celery; if the queue is unreachable, send it inline. Never raises."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return
    from .tasks import send_email_task
    try:
        send_email_task.delay(subject, text, html, recipients)
    except Exception:
        try:
            deliver(subject, text, html, recipients)
        except Exception:
            log.exception('Could not send e-mail "%s"', subject)
