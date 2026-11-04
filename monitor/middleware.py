import time

from .service import SKIP_PREFIXES, log_error, track


class MonitorMiddleware:
    """Records page views (HTML GETs) and turns every unhandled exception into a ticketed error with a
    reference the member can quote to support."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.monotonic()
        response = self.get_response(request)
        try:
            p = request.path
            if (request.method == 'GET' and not p.startswith(SKIP_PREFIXES) and response.status_code < 500
                    and 'text/html' in response.get('Content-Type', '') and request.headers.get('X-Requested-With') != 'XMLHttpRequest'):
                track(request, 'view', status=response.status_code, ms=int((time.monotonic() - t0) * 1000))
        except Exception:
            pass
        return response

    def process_exception(self, request, exception):
        request.error_reference = log_error(request, exc=exception)
        return None            # let Django render the 500 page as usual
