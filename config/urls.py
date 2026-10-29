from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('payments/', include('payments.urls')),
    path('', include('accounts.urls')),
    path('', include('orders.urls')),
    path('', include('chat.urls')),
    path('', include('portals.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'core.views_errors.not_found'
handler500 = 'core.views_errors.server_error'
