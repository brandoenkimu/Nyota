import hashlib
import json

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class AuditLog(models.Model):
    """Append-only trail. Each row stores a hash of itself plus the previous row's hash,
    so any later edit or deletion breaks the chain and shows up in the developer portal."""
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='audit_entries')
    actor_label = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=60, db_index=True)
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=60, blank=True)
    target_repr = models.CharField(max_length=200, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=200, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    row_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-id']
        indexes = [models.Index(fields=['action', 'created_at'])]

    def payload(self):
        return json.dumps([
            self.created_at.isoformat(), self.actor_label, self.role, self.action, self.target_type,
            self.target_id, self.target_repr, self.detail, str(self.ip or ''), self.path, self.prev_hash,
        ], sort_keys=True, default=str)

    def compute_hash(self):
        return hashlib.sha256(self.payload().encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError('Audit entries cannot be edited.')
        with transaction.atomic():
            last = AuditLog.objects.select_for_update().order_by('-id').first()
            self.prev_hash = last.row_hash if last else ''
            self.row_hash = self.compute_hash()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError('Audit entries cannot be deleted.')
