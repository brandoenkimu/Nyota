"""Session cart. {product_id: quantity}. Prices are always read fresh from the database."""
from decimal import Decimal

from catalog.models import Product
from shops.models import ShopStatus

MAX_QTY = 50


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.data = self.session.setdefault('cart', {})

    def _save(self):
        self.session['cart'] = self.data
        self.session.modified = True

    def add(self, product_id, qty=1):
        key = str(product_id)
        self.data[key] = min(MAX_QTY, int(self.data.get(key, 0)) + max(1, int(qty)))
        self._save()

    def set(self, product_id, qty):
        key = str(product_id)
        qty = int(qty)
        if qty <= 0:
            self.data.pop(key, None)
        else:
            self.data[key] = min(MAX_QTY, qty)
        self._save()

    def remove(self, product_id):
        self.data.pop(str(product_id), None)
        self._save()

    def clear(self):
        self.data.clear()
        self.session.pop('coupon', None)
        self._save()

    def __len__(self):
        return sum(int(q) for q in self.data.values())

    def lines(self):
        ids = [int(k) for k in self.data]
        products = (Product.objects.filter(pk__in=ids, is_active=True, shop__status=ShopStatus.ACTIVE)
                    .select_related('shop', 'category'))
        out = []
        for p in products:
            wanted = int(self.data.get(str(p.pk), 0))
            out.append({'product': p, 'qty': wanted, 'wanted': wanted, 'ok': p.stock >= wanted > 0,
                        'line_total': p.price * wanted})
        # drop anything that vanished from the catalogue
        known = {str(line['product'].pk) for line in out}
        for key in list(self.data):
            if key not in known:
                self.data.pop(key)
        self._save()
        return sorted(out, key=lambda x: (x['product'].shop_id, x['product'].name))

    def groups(self, coupon=None):
        """Lines grouped per shop with shipping and (optional) coupon applied per shop."""
        groups = {}
        for line in self.lines():
            shop = line['product'].shop
            g = groups.setdefault(shop.pk, {'shop': shop, 'lines': [], 'subtotal': Decimal('0')})
            g['lines'].append(line)
            g['subtotal'] += line['line_total']
        total_sub = sum((g['subtotal'] for g in groups.values()), Decimal('0'))
        percent = Decimal(coupon.percent) if coupon and coupon.is_valid_for(total_sub) else Decimal('0')
        out, shipping, discount = [], Decimal('0'), Decimal('0')
        for g in groups.values():
            shop = g['shop']
            free = shop.free_shipping_over is not None and g['subtotal'] >= shop.free_shipping_over
            g['shipping'] = Decimal('0') if free else shop.shipping_fee
            g['discount'] = (g['subtotal'] * percent / Decimal(100)).quantize(Decimal('0.01'))
            g['total'] = g['subtotal'] + g['shipping'] - g['discount']
            shipping += g['shipping']
            discount += g['discount']
            out.append(g)
        return {'groups': out, 'subtotal': total_sub, 'shipping': shipping, 'discount': discount,
                'total': total_sub + shipping - discount, 'percent': percent,
                'ok': bool(out) and all(line['ok'] for g in out for line in g['lines'])}
