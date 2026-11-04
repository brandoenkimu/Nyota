import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .service import log_error


@csrf_exempt          # it only writes a rate-limited log line, and anonymous login pages must be able to report too
@require_POST
def client_error(request):
    """Browsers report JavaScript errors here (see static/js/app.js)."""
    from django.core.cache import cache
    key = f'clierr:{request.META.get("REMOTE_ADDR")}'
    n = cache.get(key, 0)
    if n >= 20:                                     # at most 20 per minute per address: never a flood
        return JsonResponse({'ok': False}, status=429)
    cache.set(key, n + 1, 60)
    try:
        d = json.loads(request.body or b'{}')
    except ValueError:
        d = {}
    ref = log_error(request, source='browser', exc_type='JavaScript', message=str(d.get('message', ''))[:300],
                    location=str(d.get('source', ''))[:300], stack=str(d.get('stack', ''))[:4000], status=0,
                    note=f'page: {str(d.get("page", ""))[:200]}')
    return JsonResponse({'ok': True, 'reference': ref})
