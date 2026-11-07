from django.contrib import admin

from .models import HeroSlide, Notification, SiteSetting

admin.site.register(HeroSlide)
admin.site.register(Notification)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    """Keys the public site already reads, filled in here once they're ready -- nothing above needs
    a code change or a redeploy to pick these up:
      play_store_url, app_store_url   -- mobile app links; buttons show "Coming soon" until set
      contact_email, contact_phone, whatsapp_url, support_hours
      facebook_url, instagram_url, twitter_url, linkedin_url
    """
    list_display = ('key', 'value')
    search_fields = ('key', 'value')
    ordering = ('key',)
