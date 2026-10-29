"""Nyota settings. Everything environment-specific comes from environment variables
(or a local .env file that is never committed)."""
import os
from datetime import time
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env(name, default=''):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [x.strip() for x in env(name, default).split(',') if x.strip()]


DEBUG = env_bool('DEBUG', True)
SECRET_KEY = env('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key-change-me-' + 'x' * 30
    else:
        raise RuntimeError('SECRET_KEY must be set when DEBUG is off.')

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1,.localhost')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', '')

# ----------------------------------------------------------------- company
COMPANY_NAME = env('COMPANY_NAME', 'Nyota')
COMPANY_DOMAIN = env('COMPANY_DOMAIN', 'nyota.market')       # staff e-mail identities
ROOT_DOMAIN = env('ROOT_DOMAIN', '')                          # enables shop subdomains, e.g. nyota.market
SITE_URL = env('SITE_URL', 'http://localhost:8000')
CURRENCY = env('CURRENCY', 'KES')
PLATFORM_COMMISSION_PERCENT = float(env('PLATFORM_COMMISSION_PERCENT', '8'))
SHOP_AUTO_APPROVE = env_bool('SHOP_AUTO_APPROVE', DEBUG)
REQUIRE_VERIFIED_EMAIL = env_bool('REQUIRE_VERIFIED_EMAIL', not DEBUG)    # needed before checkout
WORK_START = time(int(env('WORK_START_HOUR', '8')), int(env('WORK_START_MINUTE', '30')))

# ------------------------------------------------------------------ apps
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    'channels',
    'core',
    'accounts',
    'shops',
    'catalog',
    'orders',
    'payments',
    'chat',
    'analytics',
    'audit',
    'portals',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.ShopSubdomainMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'audit.middleware.AuditContextMiddleware',
    'accounts.middleware.AccountStateMiddleware',
    'core.middleware.MembersOnlyMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context.site',
    ]},
}]

# -------------------------------------------------------------- database
DATABASES = {'default': dj_database_url.config(
    default=f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=600)}
IS_POSTGRES = 'postgresql' in DATABASES['default'].get('ENGINE', '')
if IS_POSTGRES:
    INSTALLED_APPS.insert(INSTALLED_APPS.index('django.contrib.humanize') + 1, 'django.contrib.postgres')

# Members-only: visitors must sign in or sign up before they can see the shop, use the cart or pay.
MEMBERS_ONLY = env_bool('MEMBERS_ONLY', True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------- cache / channels
REDIS_URL = env('REDIS_URL', '')
if REDIS_URL:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                                  'CONFIG': {'hosts': [REDIS_URL]}}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# Celery: without Redis, tasks simply run inline (eagerly), so nothing extra to start in development.
CELERY_BROKER_URL = REDIS_URL or 'memory://'
CELERY_RESULT_BACKEND = REDIS_URL or 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TIMEZONE = 'Africa/Nairobi'
CELERY_BEAT_SCHEDULE = {
    'nightly-warehouse-build': {'task': 'analytics.tasks.run_etl_task',
                                'schedule': 60 * 60 * 6},
    'expire-unpaid-orders': {'task': 'orders.tasks.expire_unpaid_orders_task', 'schedule': 60 * 15},
    'low-stock-alerts': {'task': 'catalog.tasks.low_stock_alerts', 'schedule': 60 * 60 * 12},
}

# ----------------------------------------------------------------- auth
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
] if env_bool('USE_ARGON2', False) else [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True

# Social sign-in (customers only). Leave blank to hide the button.
OAUTH = {
    'google': {'client_id': env('GOOGLE_CLIENT_ID'), 'client_secret': env('GOOGLE_CLIENT_SECRET')},
    'github': {'client_id': env('GITHUB_CLIENT_ID'), 'client_secret': env('GITHUB_CLIENT_SECRET')},
    'microsoft': {'client_id': env('MICROSOFT_CLIENT_ID'), 'client_secret': env('MICROSOFT_CLIENT_SECRET')},
}

# --------------------------------------------------------------- payments
MPESA = {
    'env': env('MPESA_ENV', 'sandbox'),                       # sandbox | production
    'consumer_key': env('MPESA_CONSUMER_KEY'),
    'consumer_secret': env('MPESA_CONSUMER_SECRET'),
    'shortcode': env('MPESA_SHORTCODE', '174379'),
    'passkey': env('MPESA_PASSKEY'),
    'callback_url': env('MPESA_CALLBACK_URL'),                # must be a public HTTPS URL
}
STRIPE = {
    'secret_key': env('STRIPE_SECRET_KEY'),
    'webhook_secret': env('STRIPE_WEBHOOK_SECRET'),
}
# With no keys configured, payments run in a clearly labelled demo mode so the whole flow can be tried.
PAYMENTS_SIMULATE = env_bool('PAYMENTS_SIMULATE', not (MPESA['consumer_key'] and STRIPE['secret_key']))

# -------------------------------------------------------------- i18n/time
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------- static/media
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ------------------------------------------------------------------ e-mail
if env('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST')
    EMAIL_PORT = int(env('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'   # prints mail in the terminal
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', f'{COMPANY_NAME} <no-reply@{COMPANY_DOMAIN}>')

# -------------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 24,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle',
                                 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '120/min', 'user': '600/min'},
}

# --------------------------------------------------------------- security
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# OpenStreetMap's tile servers refuse requests that carry no Referer, so send the origin to other sites.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': env('LOG_LEVEL', 'INFO')},
}
