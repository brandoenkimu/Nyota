from django.http import HttpResponse
from django.shortcuts import render


def not_found(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def server_error(request):
    ref = getattr(request, 'error_reference', '')
    try:
        return render(request, 'errors/500.html', {'reference': ref}, status=500)
    except Exception:       # even the error page must never fail
        return HttpResponse(f'Something went wrong. Reference {ref}', status=500)
