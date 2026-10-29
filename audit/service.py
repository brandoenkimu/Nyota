"""audit.record(...) is the one function the rest of the code calls to leave a trail."""
import logging
import threading

from .models import AuditLog

log = logging.getLogger(__name__)
_local = threading.local()


def set_request(request):
    _local.request = request


def get_request():
    return getattr(_local, 'request', None)


def _ip(request):
    if request is None:
        return None
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or None


def record(action, target=None, request=None, actor=None, **detail):
    """Write one audit entry. Never raises: auditing must not break the action being audited."""
    try:
        request = request or get_request()
        user = actor or (getattr(request, 'user', None) if request is not None else None)
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None
        AuditLog.objects.create(
            actor=user,
            actor_label=(user.username if user else detail.pop('actor_label', '')) or '',
            role=getattr(user, 'role', '') if user else '',
            action=action,
            target_type=type(target).__name__ if target is not None else '',
            target_id=str(getattr(target, 'pk', '') or '') if target is not None else '',
            target_repr=str(target)[:200] if target is not None else '',
            detail={k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in detail.items()},
            ip=_ip(request),
            path=(request.path[:200] if request is not None else ''),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:200] if request is not None else ''),
        )
    except Exception:  # pragma: no cover
        log.exception('audit write failed for %s', action)


def verify_chain(limit=5000):
    """Re-compute the hash chain. Returns (ok, first_bad_id, checked)."""
    prev = ''
    checked = 0
    for row in AuditLog.objects.order_by('id')[:limit]:
        checked += 1
        if row.prev_hash != prev or row.compute_hash() != row.row_hash:
            return False, row.id, checked
        prev = row.row_hash
    return True, None, checked
