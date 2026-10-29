from django.contrib import admin

from .models import HeroSlide, Notification, SiteSetting

admin.site.register(HeroSlide)
admin.site.register(Notification)
admin.site.register(SiteSetting)
