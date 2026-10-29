from .models import Notification


def notify(user, title, body='', url=''):
    """In-app notification (the bell in the header)."""
    if user is None:
        return None
    return Notification.objects.create(user=user, title=title[:140], body=body[:300], url=url[:200])


def notify_many(users, title, body='', url=''):
    Notification.objects.bulk_create([Notification(user=u, title=title[:140], body=body[:300], url=url[:200])
                                      for u in users])
