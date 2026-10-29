web: python manage.py migrate --noinput && daphne -b 0.0.0.0 -p $PORT config.asgi:application
worker: celery -A config worker -B -l info
