from django.apps import AppConfig


class MonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitor'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        def on_login(sender, request, user, **kw):
            from .service import track
            if request is not None:
                track(request, 'login', label=user.role)
        user_logged_in.connect(on_login, dispatch_uid='monitor_login')
