from .service import set_request


class AuditContextMiddleware:
    """Makes the current request available to signal handlers (login, logout, ...)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_request(request)
        try:
            return self.get_response(request)
        finally:
            set_request(None)
