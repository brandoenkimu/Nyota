"""Sign-in lockout: after N failures for the same account+IP the pair is blocked for a while."""
from django.conf import settings
from django.core.cache import cache


def _key(ident: str, ip: str) -> str:
    return f'loginfail:{(ident or "").strip().lower()}:{ip or "-"}'


def client_ip(request) -> str:
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR', '')) or ''


def is_locked(ident, ip) -> bool:
    return cache.get(_key(ident, ip), 0) >= settings.LOGIN_MAX_FAILURES


def register_failure(ident, ip) -> int:
    key = _key(ident, ip)
    count = cache.get(key, 0) + 1
    cache.set(key, count, settings.LOGIN_LOCKOUT_SECONDS)
    return count


def clear(ident, ip) -> None:
    cache.delete(_key(ident, ip))
