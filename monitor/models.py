import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def new_reference():
    return 'NY-' + secrets.token_hex(3).upper()


class ErrorStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    INVESTIGATING = 'investigating', 'Being investigated'
    RESOLVED = 'resolved', 'Fixed'
    IGNORED = 'ignored', 'Ignored'


class ErrorGroup(models.Model):
    """One row per distinct problem (same type, place and message), so 500 identical crashes are one ticket."""
    fingerprint = models.CharField(max_length=40, unique=True)
    source = models.CharField(max_length=10, default='server')          # server | browser
    exc_type = models.CharField(max_length=120, blank=True)
    message = models.CharField(max_length=300, blank=True)
    location = models.CharField(max_length=300, blank=True)             # file:line:function (server) or script (browser)
    sample_path = models.CharField(max_length=200, blank=True)
    traceback = models.TextField(blank=True)
    status = models.CharField(max_length=14, choices=ErrorStatus.choices, default=ErrorStatus.OPEN, db_index=True)
    count = models.PositiveIntegerField(default=1)
    users_affected = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='assigned_errors')
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f'{self.exc_type}: {self.message[:60]}'


class ErrorEvent(models.Model):
    """Each individual occurrence: who it happened to and where. The reference is shown to the user."""
    group = models.ForeignKey(ErrorGroup, on_delete=models.CASCADE, related_name='events')
    reference = models.CharField(max_length=12, unique=True, default=new_reference)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='error_events')
    user_label = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, blank=True)
    method = models.CharField(max_length=8, blank=True)
    path = models.CharField(max_length=200, blank=True)
    status_code = models.PositiveSmallIntegerField(default=500)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=500, blank=True)                 # what the user said they were doing

    class Meta:
        ordering = ['-created_at']


class ActivityEvent(models.Model):
    """What members do on the site (page views, searches, cart, checkout). Feeds the analyst usage dashboard
    and lets support see a member's recent journey when they report a problem."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='activity')
    session = models.CharField(max_length=16, blank=True, db_index=True)      # hashed, never the raw session key
    kind = models.CharField(max_length=20, db_index=True)                     # view | search | add_to_cart | checkout | order | login
    path = models.CharField(max_length=200, blank=True)
    label = models.CharField(max_length=200, blank=True)                      # page group, search text, product, ...
    device = models.CharField(max_length=10, blank=True)                      # mobile | tablet | desktop
    status_code = models.PositiveSmallIntegerField(default=200)
    ms = models.PositiveIntegerField(default=0)                               # server time to answer
    count = models.IntegerField(default=0)                                    # e.g. number of search results

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['kind', 'created_at']), models.Index(fields=['user', 'created_at'])]
