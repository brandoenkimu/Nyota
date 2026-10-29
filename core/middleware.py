from django.conf import settings

RESERVED = {'www', 'app', 'admin', 'api', 'static', 'media', 'staff', 'seller'}


class ShopSubdomainMiddleware:
    """Every seller gets a site of their own:  https://<shop-slug>.<ROOT_DOMAIN>/
    Active only when ROOT_DOMAIN is configured (needs wildcard DNS, see README)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        root = settings.ROOT_DOMAIN
        if root:
            host = request.get_host().split(':')[0].lower()
            if host.endswith('.' + root):
                sub = host[: -(len(root) + 1)]
                if sub and '.' not in sub and sub not in RESERVED and request.path_info == '/':
                    request.path_info = f'/shop/{sub}/'
        return self.get_response(request)


class MembersOnlyMiddleware:
    """Members-only mode (settings.MEMBERS_ONLY, on by default): visitors who are not signed in can only
    reach the sign-in, sign-up, password-recovery and OAuth pages. Everything else (home page, products,
    shops, cart, checkout, payments) sends them to the right login page, and AJAX calls such as
    "add to cart" get a JSON 401 that the page turns into the same redirect.

    Server-to-server callbacks (M-Pesa, Stripe) and the health check stay open because the payment
    providers cannot sign in."""

    PUBLIC_PREFIXES = (
        '/static/', '/favicon.ico', '/login/', '/seller/login/', '/staff/login/', '/signup/', '/seller/signup/',
        '/verify-email/', '/password/reset/', '/oauth/', '/terms/', '/privacy/', '/django-admin/',
        '/payments/mpesa/callback/', '/payments/stripe/webhook/', '/api/health/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _login_name(path):
        if path.startswith('/seller/'):
            return 'accounts:seller_login'
        if path.startswith('/staff/'):
            return 'accounts:staff_login'
        return 'accounts:login'

    def __call__(self, request):
        if not settings.MEMBERS_ONLY or request.user.is_authenticated:
            return self.get_response(request)
        path = request.path_info
        if path.startswith(self.PUBLIC_PREFIXES):
            return self.get_response(request)
        from django.http import JsonResponse
        from django.shortcuts import redirect
        from django.urls import reverse
        login_url = reverse(self._login_name(path))
        if path.startswith('/api/'):
            if request.headers.get('Authorization'):          # token clients are checked by the API itself
                return self.get_response(request)
            return JsonResponse({'detail': 'Authentication required.'}, status=401)
        target = login_url if path == '/' else f'{login_url}?next={request.get_full_path()}'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method != 'GET':
            return JsonResponse({'ok': False, 'login': target, 'message': 'Please sign in or create an account first.'},
                               status=401)
        from django.contrib import messages
        messages.info(request, 'Please sign in or create a free account to continue.')
        return redirect(target)
