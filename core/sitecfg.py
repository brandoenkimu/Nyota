"""Thin reader around core.models.SiteSetting (a plain key/value table, already registered in
Django admin). Lets admins fill in things that don't exist on day one -- like the mobile app's
store links -- without a code change or a migration: they add a row in /django-admin/core/sitesetting/
with the matching key, and it appears on the site immediately.

Keys currently read anywhere on the site:
    contact_email, contact_phone, whatsapp_url, support_hours,
    facebook_url, instagram_url, twitter_url, linkedin_url,
    play_store_url, app_store_url
"""
from .models import SiteSetting

_DEFAULTS = {
    'support_hours': 'Mon-Sat, 8:00-18:00 EAT',
}


def site_setting(key, default=None):
    row = SiteSetting.objects.filter(key=key).first()
    if row and row.value:
        return row.value
    return _DEFAULTS.get(key, default if default is not None else '')


def site_settings(*keys):
    rows = {r.key: r.value for r in SiteSetting.objects.filter(key__in=keys)}
    return {k: (rows.get(k) or _DEFAULTS.get(k, '')) for k in keys}
