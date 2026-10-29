"""python manage.py fetch_product_images [--dry-run] [--force] [--limit N]

Looks each product up on Wikimedia Commons (free-licensed photos) and stores the best match in
Product.image_url. Run this on YOUR machine (it needs internet access).

Honest limits: Commons is a general photo library, not a product catalogue. Generic items
(football, honey, kettle, laptop) match well; brand-new or local items may not. Anything without a
confident match keeps its generated artwork, so a card is never empty, and is listed at the end so
you can upload the real photo from the seller portal. Photos remain under their own licences:
check attribution requirements before commercial use."""
import re
import time

import requests
from django.core.management.base import BaseCommand

from catalog.models import Product

API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'NyotaMarketplace/1.0 (demo image fetcher; contact: admin@nyota.market)'}
OK_TYPES = ('image/jpeg', 'image/png')
STOP = {'the', 'and', 'for', 'with', 'set', 'pro', 'size', 'pc', 'pcs', 'new', 'a', 'of', 'by'}


def tokens(text):
    return {t for t in re.findall(r'[a-z0-9]+', text.lower()) if len(t) > 2 and t not in STOP}


def search(query):
    params = {'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrlimit': 8,
              'gsrsearch': f'{query} filetype:bitmap', 'prop': 'imageinfo', 'iiprop': 'url|mime|size', 'iiurlwidth': 640}
    r = requests.get(API, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    pages = (r.json().get('query') or {}).get('pages') or {}
    out = []
    for p in pages.values():
        info = (p.get('imageinfo') or [{}])[0]
        if info.get('mime') in OK_TYPES and info.get('thumburl') and info.get('width', 0) >= 400:
            out.append((p['title'], info['thumburl'], p.get('index', 99)))
    return sorted(out, key=lambda x: x[2])


class Command(BaseCommand):
    help = 'Fetch matching photos from Wikimedia Commons for products without a real image.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true', help='also replace existing image_url values')
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **o):
        qs = Product.objects.select_related('category', 'shop')
        if not o['force']:
            qs = qs.filter(image='', image_url='')
        if o['limit']:
            qs = qs[:o['limit']]
        missed = []
        for p in qs:
            want = tokens(p.name) | tokens(p.brand)
            category_word = p.category.name.replace('&', ' ').replace("'", '')
            best = None
            for q in (f'{p.brand} {p.name}', p.name, f'{p.name.split(" ")[-1]} {category_word}'):
                try:
                    results = search(q)
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'  network problem for "{q}": {exc}'))
                    results = []
                for title, url, _ in results:
                    if want & tokens(title):
                        best = (title, url)
                        break
                time.sleep(.6)
                if best:
                    break
            if best:
                self.stdout.write(f'OK    {p.name[:38]:38} <- {best[0][:60]}')
                if not o['dry_run']:
                    Product.objects.filter(pk=p.pk).update(image_url=best[1])
            else:
                missed.append(p)
                self.stdout.write(self.style.WARNING(f'MISS  {p.name}'))
        self.stdout.write(self.style.SUCCESS(f'\nDone. {len(missed)} product(s) keep generated artwork:'))
        for p in missed:
            self.stdout.write(f'   - {p.name}  ({p.shop.name})')
