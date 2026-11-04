"""Records server crashes, browser errors and member activity. Everything here must be safe: it may never raise,
because a failure in monitoring must not turn a small problem into a bigger one."""
import hashlib
import logging
import re
import traceback as tb

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from audit.service import record as audit
from .models import ActivityEvent, ErrorEvent, ErrorGroup, ErrorStatus

log = logging.getLogger(__name__)
SKIP_PREFIXES = ('/static/', '/media/', '/favicon', '/api/health', '/api/theme', '/api/client-error', '/chat/poll',
                 '/ws/', '/api/v1/', '/notifications/count')
_ID = re.compile(r'/\d+(?=/|$)')


def _ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR')) or None


def _device(ua):
    ua = (ua or '').lower()
    if 'ipad' in ua or 'tablet' in ua:
        return 'tablet'
    if 'mobi' in ua or 'android' in ua or 'iphone' in ua:
        return 'mobile'
    return 'desktop'


def _fingerprint(*parts):
    return hashlib.sha1('|'.join(str(p) for p in parts).encode()).hexdigest()


def _normalise(msg):
    return re.sub(r'\d+', 'N', msg or '')[:200]


def _user(request):
    u = getattr(request, 'user', None)
    return u if u is not None and getattr(u, 'is_authenticated', False) else None


def log_error(request, exc=None, source='server', message='', exc_type='', location='', stack='', status=500, note=''):
    """Store one occurrence; returns its reference (shown to the member so support can find it)."""
    try:
        if exc is not None:
            exc_type = type(exc).__name__
            message = str(exc)
            frames = tb.extract_tb(exc.__traceback__)
            last = frames[-1] if frames else None
            location = f'{last.filename.split("site-packages/")[-1].split("nyota/")[-1]}:{last.lineno} in {last.name}' if last else ''
            stack = ''.join(tb.format_exception(type(exc), exc, exc.__traceback__))
        path = (request.path if request is not None else '')[:200]
        fp = _fingerprint(source, exc_type, location, _normalise(message), _ID.sub('/N', path) if source == 'server' else '')
        user = _user(request) if request is not None else None
        now = timezone.now()
        with transaction.atomic():
            group, created = ErrorGroup.objects.get_or_create(
                fingerprint=fp, defaults=dict(source=source, exc_type=exc_type[:120], message=message[:300],
                                              location=location[:300], sample_path=path, traceback=stack[-8000:]))
            if not created:
                new_user = user is not None and not group.events.filter(user=user).exists()
                ErrorGroup.objects.filter(pk=group.pk).update(
                    count=F('count') + 1, last_seen=now,
                    users_affected=F('users_affected') + (1 if new_user else 0),
                    status=ErrorStatus.OPEN if group.status == ErrorStatus.RESOLVED else group.status)   # it came back
            elif user is not None:
                ErrorGroup.objects.filter(pk=group.pk).update(users_affected=1)
            ev = ErrorEvent.objects.create(
                group=group, user=user, user_label=(user.username if user else 'anonymous')[:150],
                role=getattr(user, 'role', '') if user else '', method=(request.method if request is not None else '')[:8],
                path=path, status_code=status, ip=_ip(request) if request is not None else None,
                user_agent=(request.META.get('HTTP_USER_AGENT', '')[:200] if request is not None else ''), note=note[:500])
        audit('system.error', request=request, actor=user, reference=ev.reference, type=exc_type or source, path=path)
        return ev.reference
    except Exception:  # pragma: no cover
        log.exception('could not record error')
        return ''


def track(request, kind, label='', status=200, ms=0, count=0):
    """One activity row. Skipped when the browser sends Do-Not-Track / Global Privacy Control."""
    try:
        if request.META.get('HTTP_DNT') == '1' or request.META.get('HTTP_SEC_GPC') == '1':
            return
        sk = request.session.session_key if hasattr(request, 'session') else None
        ActivityEvent.objects.create(
            user=_user(request), session=hashlib.sha1((sk or _ip(request) or '').encode()).hexdigest()[:12],
            kind=kind, path=request.path[:200], label=label[:200], device=_device(request.META.get('HTTP_USER_AGENT')),
            status_code=status, ms=ms, count=count)
    except Exception:  # pragma: no cover
        log.exception('could not record activity')
