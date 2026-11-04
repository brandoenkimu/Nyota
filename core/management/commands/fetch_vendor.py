"""python manage.py fetch_vendor

Downloads Bootstrap, Leaflet and Chart.js into static/vendor/ so pages never wait on a CDN
(a slow or blocked CDN is the usual reason a page takes ages to appear after login).
Run it once on your machine; templates use the local copy automatically when it exists."""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

B = 'https://cdnjs.cloudflare.com/ajax/libs/'
FILES = {
    'bootstrap/bootstrap.min.css': B + 'bootstrap/5.3.3/css/bootstrap.min.css',
    'bootstrap/bootstrap.bundle.min.js': B + 'bootstrap/5.3.3/js/bootstrap.bundle.min.js',
    'leaflet/leaflet.css': B + 'leaflet/1.9.4/leaflet.css',
    'leaflet/leaflet.js': B + 'leaflet/1.9.4/leaflet.js',
    'chart/chart.umd.min.js': B + 'Chart.js/4.4.1/chart.umd.min.js',
}
for img in ('marker-icon.png', 'marker-icon-2x.png', 'marker-shadow.png', 'layers.png', 'layers-2x.png'):
    FILES['leaflet/images/' + img] = B + 'leaflet/1.9.4/images/' + img


class Command(BaseCommand):
    help = 'Download third-party CSS/JS into static/vendor for fast, CDN-free page loads.'

    def handle(self, *args, **o):
        root = settings.BASE_DIR / 'static' / 'vendor'
        bad = 0
        for rel, url in FILES.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                path.write_bytes(r.content)
                self.stdout.write(f'ok   {rel}')
            except Exception as exc:
                bad += 1
                self.stdout.write(self.style.WARNING(f'FAIL {rel}: {exc}'))
        self.stdout.write(self.style.SUCCESS('Done.') if not bad else self.style.WARNING(f'{bad} file(s) failed; the CDN is used for those.'))
