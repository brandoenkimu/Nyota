"""python manage.py seed_demo [--reset]  ->  a realistic demo marketplace to explore every portal.

Creates platform staff (one per position), six shops with owners and team members, ~48 products,
customers, ~90 days of orders with tracking, payments and reviews, chats, coupons and hero slides,
then builds the data warehouse. Every demo account uses the password printed at the end."""
import random
import datetime as dt
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.forms import StaffCreateForm
from accounts.models import Address, Attendance, Role, User
from analytics import etl
from catalog.models import Category, Product, Review
from chat import services as chat
from core.models import HeroSlide
from orders.models import (Coupon, Order, OrderItem, Payout, ShopOrder, ShopOrderStatus, TrackingEvent, split_commission)
from payments.models import Payment, PaymentState
from shops.models import Shop, ShopStatus

PASSWORD = 'Nyota@2026!'
rnd = random.Random(42)

CATEGORIES = [('Phones & Tablets', 'phones'), ('Computers', 'computers'), ('Audio', 'audio'), ("Men's Fashion", 'mens-fashion'),
              ("Women's Fashion", 'womens-fashion'), ('Footwear', 'footwear'), ('Bags', 'bags'), ('Home Decor', 'home-decor'),
              ('Kitchen', 'kitchen'), ('Beauty', 'beauty'), ('Groceries', 'groceries'), ('Sports', 'sports'),
              ('Books', 'books'), ('Toys', 'toys'), ('Jewelry', 'jewelry')]

# shop name, tagline, city, county, lat, lng, colour, owner (first, last), category slugs
SHOPS = [
    ('Savanna Tech', 'Phones, laptops and audio you can trust', 'Nairobi', 'Nairobi', -1.2833, 36.8219, '#0ea5e9', ('Brian', 'Otieno'), ['phones', 'computers', 'audio']),
    ('Kilimo Fresh Hub', 'Farm-fresh groceries, delivered the same day', 'Nakuru', 'Nakuru', -0.3031, 36.0800, '#10b981', ('Grace', 'Wanjiru'), ['groceries', 'kitchen']),
    ('Mombasa Threads', 'Coastal fashion for every season', 'Mombasa', 'Mombasa', -4.0435, 39.6682, '#f43f5e', ('Amina', 'Hassan'), ['mens-fashion', 'womens-fashion', 'footwear']),
    ('Lakeside Living', 'Home decor with a Kisumu soul', 'Kisumu', 'Kisumu', -0.0917, 34.7680, '#f5b324', ('Peter', 'Odhiambo'), ['home-decor', 'kitchen', 'bags']),
    ('Rift Sports & Play', 'Gear for athletes and little adventurers', 'Eldoret', 'Uasin Gishu', 0.5143, 35.2698, '#fb7c2c', ('Kevin', 'Kiprop'), ['sports', 'toys', 'books']),
    ('Mt Kenya Glow', 'Beauty, jewelry and thoughtful gifts', 'Nyeri', 'Nyeri', -0.4201, 36.9476, '#d946ef', ('Faith', 'Njeri'), ['beauty', 'jewelry', 'bags']),
]

PRODUCTS = {  # slug: [(name, brand, price, was)]
    'phones': [('Galaxy A55 128GB', 'Samsung', 48999, 54999), ('Redmi Note 13 Pro', 'Xiaomi', 34999, None), ('iPhone 13 (Refurbished)', 'Apple', 62000, 69999), ('Tecno Spark 20', 'Tecno', 17999, 19999)],
    'computers': [('ThinkPad E14 Core i5', 'Lenovo', 89999, 99999), ('HP 15 Laptop 8GB/512GB', 'HP', 64999, None), ('Wireless Mouse and Keyboard Combo', 'Logitech', 3499, 4299)],
    'audio': [('Bluetooth Earbuds Pro', 'Oraimo', 2999, 3999), ('Over-ear Studio Headphones', 'Sony', 12999, None), ('Portable Party Speaker', 'JBL', 8999, 10999)],
    'mens-fashion': [('Linen Short-sleeve Shirt', 'Kenzo Cut', 2499, 2999), ('Slim Fit Chinos', 'Urban Co', 3299, None)],
    'womens-fashion': [('Kitenge Wrap Dress', 'Mama Africa', 4200, 4800), ('Ankara Print Maxi Skirt', 'Zuri', 2800, None), ('Cotton Kaftan', 'Swahili Style', 3600, None)],
    'footwear': [('Leather Sandals', 'Akala', 1999, 2499), ('Canvas Sneakers', 'Vans-style', 3999, None), ('Running Shoes', 'Nimbus', 6999, 8499)],
    'bags': [('Sisal Basket Bag', 'Kiondo Kenya', 2200, None), ('Laptop Backpack 15.6"', 'Urban Co', 3499, 3999), ('Leather Tote', 'Zuri', 5600, None)],
    'home-decor': [('Hand-woven Wall Hanging', 'Lake Crafts', 2800, None), ('Soapstone Vase', 'Kisii Art', 1800, 2200), ('Scented Candle Set', 'Glow', 1500, None)],
    'kitchen': [('Non-stick Cookware Set 7pc', 'Tefal-style', 7999, 9499), ('Electric Kettle 1.7L', 'Ramtons', 2599, None), ('Wooden Chopping Board', 'Lake Crafts', 1200, None)],
    'beauty': [('Shea Butter Body Cream', 'Mt Kenya Glow', 899, None), ('Argan Hair Oil 100ml', 'Pure', 1299, 1599), ('Vitamin C Face Serum', 'Dermacare', 1999, None)],
    'groceries': [('Kenyan AA Coffee Beans 500g', 'Kilimo Fresh', 950, None), ('Organic Honey 1kg', 'Kilimo Fresh', 1100, 1300), ('Fresh Avocado Box (12)', 'Kilimo Fresh', 800, None), ('Rift Valley Tea 1kg', 'Kilimo Fresh', 650, None)],
    'sports': [('Football Size 5', 'Rift Sports', 1800, 2200), ('Yoga Mat 6mm', 'Rift Sports', 1600, None), ('Adjustable Dumbbell Set 20kg', 'Rift Sports', 6500, 7500)],
    'books': [('Weep Not, Child (Paperback)', 'Ngugi wa Thiong\'o', 850, None), ('Atomic Habits', 'James Clear', 1500, 1800)],
    'toys': [('Wooden Building Blocks 100pc', 'Play Africa', 1900, None), ('Remote Control Car', 'Speedy', 3200, 3800)],
    'jewelry': [('Maasai Beaded Necklace', 'Mt Kenya Glow', 1800, None), ('Sterling Silver Hoops', 'Mt Kenya Glow', 3500, 4200), ('Beaded Bracelet Set', 'Mt Kenya Glow', 900, None)],
}

CUSTOMERS = [('Wanjiku', 'Kamau', 'Nairobi', -1.2921, 36.8219), ('Otieno', 'Ochieng', 'Kisumu', -0.1022, 34.7617), ('Aisha', 'Mohammed', 'Mombasa', -4.0547, 39.6636),
             ('Joseph', 'Mutua', 'Machakos', -1.5177, 37.2634), ('Lilian', 'Chebet', 'Eldoret', 0.5204, 35.2699), ('Samuel', 'Kariuki', 'Thika', -1.0332, 37.0693),
             ('Mercy', 'Akinyi', 'Nairobi', -1.2634, 36.8007), ('Daniel', 'Maina', 'Nakuru', -0.2833, 36.0667), ('Esther', 'Wairimu', 'Nyeri', -0.4167, 36.95),
             ('Hassan', 'Ali', 'Mombasa', -4.0600, 39.6700), ('Beatrice', 'Naliaka', 'Kakamega', 0.2827, 34.7519), ('Collins', 'Rotich', 'Kericho', -0.3689, 35.2863)]

REVIEWS = [(5, 'Excellent!', 'Exactly as described and arrived fast. Will order again.'), (5, 'Love it', 'Great quality and the seller was very helpful.'),
           (4, 'Good value', 'Nice product, packaging could be better.'), (4, 'Happy', 'Works well and delivery was on time.'),
           (3, 'Okay', 'Decent, but it took longer than expected to arrive.'), (2, 'Disappointed', 'Not quite what the photos showed.'),
           (5, 'Superb service', 'The seller answered all my questions on chat. Brilliant.')]

STEPS = {
    'confirmed': ('Order confirmed', 'The seller has accepted your order.'),
    'packed': ('Packed', 'Your items are packed and ready for pickup.'),
    'shipped': ('Shipped', 'Your parcel is on its way.'),
    'out_for_delivery': ('Out for delivery', 'The courier is heading to your address.'),
    'delivered': ('Delivered', 'Delivered to the customer. Enjoy!'),
}
FLOW = ['pending', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']


class Command(BaseCommand):
    help = 'Create demo data. Use --reset to wipe previous demo accounts first.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='delete existing demo shops, products, orders and users first')
        parser.add_argument('--orders', type=int, default=220)

    @transaction.atomic
    def handle(self, *args, **opts):
        if Shop.objects.exists() and not opts['reset']:
            self.stdout.write(self.style.WARNING('Data already exists. Re-run with --reset to rebuild the demo.'))
            return
        if opts['reset']:
            self._wipe()
        admin = self._platform_staff()
        shops = self._shops(admin)
        products = self._products(shops)
        customers = self._customers()
        self._coupons_and_slides()
        self._orders(opts['orders'], shops, products, customers)
        self._chats(shops, customers, admin)
        self._attendance()
        self._payouts(shops)
        rows = etl.run_etl()
        self.stdout.write(self.style.SUCCESS(f'Warehouse built ({rows} fact rows).'))
        self._summary(shops)

    # ------------------------------------------------------------ helpers
    def _wipe(self):
        for model in (Review, Payment, TrackingEvent, OrderItem, ShopOrder, Order, Payout, Product, Shop, Coupon, HeroSlide):
            model.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def _staff(self, shop, first, last, position, creator, personal):
        form = StaffCreateForm({'first_name': first, 'last_name': last, 'position': position, 'personal_email': personal}, shop=shop)
        assert form.is_valid(), form.errors
        user, _ = form.save(creator)
        user.set_password(PASSWORD)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        return user

    def _platform_staff(self):
        admin = None
        for first, last, pos in [('Wanjiru', 'Mwangi', 'admin'), ('Ian', 'Njoroge', 'analyst'), ('Dorcas', 'Mutiso', 'developer'),
                                 ('Jane', 'Kamau', 'ceo'), ('Moses', 'Barasa', 'support')]:
            u = self._staff(None, first, last, pos, admin, f'{first.lower()}.{last.lower()}@example.com')
            admin = admin or u
        return admin

    def _shops(self, admin):
        cats = {slug: Category.objects.get_or_create(slug=slug, defaults={'name': name, 'sort': i})[0] for i, (name, slug) in enumerate(CATEGORIES)}
        self.cats = cats
        shops = []
        for name, tag, city, county, lat, lng, colour, (first, last), slugs in SHOPS:
            email = f'{first.lower()}.{last.lower()}@example.com'
            owner = User.objects.create_user(username=f'{first.lower()}.{last.lower()}', email=email, password=PASSWORD, first_name=first,
                                             last_name=last, role=Role.SELLER_OWNER, phone='0712' + str(rnd.randint(100000, 999999)), email_verified=True)
            shop = Shop.objects.create(owner=owner, name=name, tagline=tag, about=f'{name} has served {city} since 2019. We source carefully, ship fast and answer every message.',
                                       brand_color=colour, city=city, county=county, lat=Decimal(str(lat)), lng=Decimal(str(lng)), address=f'{rnd.randint(2, 90)} Kenyatta Avenue, {city}',
                                       phone=owner.phone, contact_email=email, whatsapp='254' + owner.phone[1:], instagram=name.lower().replace(' ', '').replace('&', 'and'),
                                       opening_hours='Mon-Fri 08:00-18:00\nSat 09:00-16:00\nSun Closed', status=ShopStatus.ACTIVE, is_verified=rnd.random() > .3,
                                       shipping_fee=Decimal(rnd.choice([200, 250, 300])), free_shipping_over=Decimal(rnd.choice([5000, 8000, None]) or 0) or None,
                                       return_policy='Returns accepted within 7 days if the item is unused and in its original packaging.')
            shop.demo_cats = slugs
            self._staff(shop, 'Peter' if rnd.random() > .5 else 'Mary', rnd.choice(['Kimani', 'Achieng', 'Mutai', 'Wekesa']), 'manager', owner, f'staff.{shop.slug}@example.com')
            self._staff(shop, 'Lucy', rnd.choice(['Njuguna', 'Adhiambo', 'Sang']), 'cashier', owner, f'cashier.{shop.slug}@example.com')
            shops.append(shop)
        return shops

    def _products(self, shops):
        out = []
        for shop in shops:
            for slug in shop.demo_cats:
                for name, brand, price, was in PRODUCTS[slug]:
                    if rnd.random() < .25 and len(out) > 20:
                        continue
                    p = Product.objects.create(shop=shop, category=self.cats[slug], name=name, brand=brand, sku=f'{slug[:3].upper()}-{rnd.randint(1000, 9999)}',
                                               description=f'{name} by {brand}. Sold and shipped by {shop.name}.\n\nA quality pick from our {self.cats[slug].name.lower()} range, checked before dispatch.',
                                               tags=f'{slug},{brand.lower()}', price=Decimal(price), compare_at_price=Decimal(was) if was else None,
                                               cost_price=(Decimal(price) * Decimal('0.68')).quantize(Decimal('1')), stock=rnd.randint(4, 60), is_featured=rnd.random() < .25)
                    out.append(p)
        return out

    def _customers(self):
        out = []
        for first, last, city, lat, lng in CUSTOMERS:
            u = User.objects.create_user(username=f'{first.lower()}.{last.lower()}', email=f'{first.lower()}.{last.lower()}@example.com', password=PASSWORD,
                                         first_name=first, last_name=last, role=Role.CUSTOMER, phone='07' + str(rnd.randint(10000000, 99999999)), email_verified=True)
            Address.objects.create(user=u, label='Home', full_name=u.display_name, phone=u.phone, line1=f'{rnd.randint(1, 200)} {rnd.choice(["Moi", "Kenyatta", "Tom Mboya", "Uhuru"])} Road',
                                   city=city, county=city, lat=Decimal(str(lat)), lng=Decimal(str(lng)), is_default=True)
            out.append(u)
        return out

    def _coupons_and_slides(self):
        Coupon.objects.create(code='WELCOME10', percent=10, min_total=Decimal('1000'))
        Coupon.objects.create(code='NYOTA15', percent=15, min_total=Decimal('5000'), usage_limit=100)
        for i, (k, t, s, c, u) in enumerate([('Every shop is a star', 'Discover a galaxy of local sellers', 'Phones, fashion, home, food and more.', 'Start exploring', '/products/'),
                                              ('Open your own sky', 'Launch your shop in minutes', 'Your page, your team, live analytics.', 'Become a seller', '/seller/signup/'),
                                              ('Track every step', 'From packed to delivered', 'Follow every parcel on the map.', 'Browse shops', '/shops/')]):
            HeroSlide.objects.create(kicker=k, title=t, subtitle=s, cta_label=c, cta_url=u, art_variant=i, sort=i)

    def _orders(self, n, shops, products, customers):
        now = timezone.now()
        by_shop = {}
        for p in products:
            by_shop.setdefault(p.shop_id, []).append(p)
        for _ in range(n):
            customer = rnd.choice(customers)
            age = int(rnd.betavariate(1.2, 1.6) * 90)
            placed = now - timedelta(days=age, hours=rnd.randint(0, 20), minutes=rnd.randint(0, 59))
            picked = rnd.sample(shops, k=1 if rnd.random() < .8 else 2)
            addr = customer.addresses.first()
            method = rnd.choices(['mpesa', 'stripe', 'cod'], [.6, .2, .2])[0]
            order = Order.objects.create(customer=customer, payment_method=method, ship_name=addr.full_name, ship_phone=addr.phone, ship_line1=addr.line1,
                                         ship_city=addr.city, ship_county=addr.county, ship_lat=addr.lat, ship_lng=addr.lng, placed_at=placed)
            sub_total = ship_total = Decimal('0')
            for shop in picked:
                items = rnd.sample(by_shop[shop.pk], k=min(len(by_shop[shop.pk]), rnd.randint(1, 3)))
                sub = Decimal('0')
                so = ShopOrder.objects.create(order=order, shop=shop, created_at=placed)
                for p in items:
                    q = rnd.randint(1, 3)
                    OrderItem.objects.create(shop_order=so, product=p, name=p.name, sku=p.sku, unit_price=p.price, unit_cost=p.cost_price, quantity=q)
                    sub += p.price * q
                    Product.objects.filter(pk=p.pk).update(sold=p.sold + q)
                ship = shop.shipping_fee if not (shop.free_shipping_over and sub >= shop.free_shipping_over) else Decimal('0')
                pct = shop.commission_percent
                comm, earn = split_commission(sub, pct)
                target = self._target_status(age)
                so.subtotal, so.shipping_fee, so.commission_percent, so.commission_amount, so.seller_earnings = sub, ship, pct, comm, earn
                so.status = target
                so.courier = rnd.choice(['Sendy', 'G4S Courier', 'Wells Fargo', 'Fargo Courier'])
                so.tracking_number = f'TRK{rnd.randint(10000000, 99999999)}'
                so.expected_delivery = (placed + timedelta(days=rnd.randint(2, 5))).date()
                so.save()
                self._events(so, placed, target, shop, order)
                sub_total += sub
                ship_total += ship
            order.subtotal, order.shipping_total, order.total = sub_total, ship_total, sub_total + ship_total
            states = set(order.shop_orders.values_list('status', flat=True))
            paid = (method != 'cod' and 'cancelled' not in states) or states == {'delivered'}
            order.payment_status = 'paid' if paid else ('failed' if 'cancelled' in states and method != 'cod' else 'unpaid')
            order.paid_at = placed + timedelta(minutes=3) if paid else None
            order.save()
            order.refresh_status()
            Payment.objects.create(order=order, method=method, amount=order.total, phone=order.ship_phone, simulated=True,
                                   state=PaymentState.SUCCEEDED if paid else PaymentState.FAILED if method != 'cod' else PaymentState.INITIATED,
                                   receipt=f'SIM{rnd.randint(10000000, 99999999)}' if paid and method != 'cod' else '', created_at=placed)
            for so in order.shop_orders.all():
                if so.status == 'delivered' and rnd.random() < .55:
                    item = so.items.first()
                    if item and item.product and not Review.objects.filter(product=item.product, user=customer).exists():
                        r, t, b = rnd.choice(REVIEWS)
                        Review.objects.create(product=item.product, user=customer, rating=r, title=t, body=b, sentiment=(r - 3) / 2,
                                              seller_reply='Thank you for shopping with us!' if rnd.random() < .3 else '')
        from django.db.models import Avg, Count
        for p in Product.objects.all():
            agg = p.reviews.aggregate(a=Avg('rating'), n=Count('id'))
            Product.objects.filter(pk=p.pk).update(rating_avg=round(agg['a'] or 0, 2), rating_count=agg['n'])
        for s in Shop.objects.all():
            agg = Review.objects.filter(product__shop=s).aggregate(a=Avg('rating'), n=Count('id'))
            Shop.objects.filter(pk=s.pk).update(rating_avg=round(agg['a'] or 0, 2), rating_count=agg['n'])

    @staticmethod
    def _target_status(age):
        if age > 8:
            return rnd.choices(['delivered', 'cancelled', 'returned'], [.9, .07, .03])[0]
        if age > 4:
            return rnd.choice(['delivered', 'out_for_delivery', 'shipped'])
        if age > 1:
            return rnd.choice(['confirmed', 'packed', 'shipped'])
        return rnd.choice(['pending', 'confirmed'])

    @staticmethod
    def _events(so, placed, target, shop, order):
        t = placed
        TrackingEvent.objects.create(shop_order=so, status='pending', title='Order received', detail='We received your order.', occurred_at=t)
        if target in ('cancelled', 'returned'):
            TrackingEvent.objects.create(shop_order=so, status=target, title=target.capitalize(), detail='This order was ' + target + '.', occurred_at=t + timedelta(hours=6))
            return
        for step in FLOW[1:FLOW.index(target) + 1]:
            t += timedelta(hours=rnd.randint(3, 20))
            title, detail = STEPS[step]
            lat = lng = None
            label = shop.city
            if step in ('shipped', 'out_for_delivery'):
                frac = .4 if step == 'shipped' else .85
                lat = float(shop.lat) + (float(order.ship_lat) - float(shop.lat)) * frac
                lng = float(shop.lng) + (float(order.ship_lng) - float(shop.lng)) * frac
                label = 'In transit' if step == 'shipped' else order.ship_city
            elif step == 'delivered':
                lat, lng, label = order.ship_lat, order.ship_lng, order.ship_city
            TrackingEvent.objects.create(shop_order=so, status=step, title=title, detail=detail, location_label=label,
                                         lat=Decimal(str(round(float(lat), 6))) if lat is not None else None,
                                         lng=Decimal(str(round(float(lng), 6))) if lng is not None else None, occurred_at=t)
            if step == 'shipped':
                so.shipped_at = t
            if step == 'delivered':
                so.delivered_at = t
        so.save(update_fields=['shipped_at', 'delivered_at'])

    def _chats(self, shops, customers, admin):
        for shop in shops[:4]:
            for c in customers[:2]:
                conv = chat.start_shop_chat(c, shop)
                chat.send_message(c, conv, 'Hi! Is this still available, and can you deliver today?')
                chat.send_message(shop.owner, conv, f'Hello {c.first_name}! Yes it is. Place your order and we will dispatch right away.')
                m = chat.send_message(c, conv, 'Great, thank you 🙏')
                try:
                    chat.toggle_reaction(shop.owner, m.pk, '👍')
                except Exception:
                    pass
        conv = chat.start_support_chat(customers[2])
        chat.send_message(customers[2], conv, 'Hello, I need help changing my delivery address.')

    def _attendance(self):
        today = timezone.localdate()
        for u in User.objects.exclude(role=Role.CUSTOMER):
            for d in range(10):
                day = today - timedelta(days=d)
                if day.weekday() >= 5 or rnd.random() < .1:
                    continue
                late = rnd.random() < .2
                cin = timezone.make_aware(dt.datetime.combine(day, dt.time.min)) + timedelta(hours=9 if late else 7, minutes=rnd.randint(0, 40))
                Attendance.objects.get_or_create(user=u, date=day, defaults={'clock_in': cin, 'clock_out': cin + timedelta(hours=8, minutes=rnd.randint(0, 50)) if d else None, 'late': late})

    def _payouts(self, shops):
        for s in shops[:3]:
            Payout.objects.create(shop=s, amount=Decimal(rnd.randint(8, 40) * 1000), destination=s.phone, status=rnd.choice(['requested', 'approved', 'paid']),
                                  reference='QJK' + str(rnd.randint(10000, 99999)))

    def _summary(self, shops):
        w = self.stdout.write
        w(self.style.SUCCESS('\nDemo ready. All demo accounts use the password:  ' + PASSWORD))
        w('\nPlatform staff  (sign in at /staff/login/)')
        for u in User.objects.filter(role__in=['admin', 'analyst', 'developer', 'ceo', 'support']).order_by('id'):
            w(f'  {u.get_role_display():14} {u.email}')
        w('\nSellers  (sign in at /seller/login/)')
        for s in shops:
            w(f'  {s.name:22} owner {s.owner.email}')
            for m in s.members.select_related("user"):
                w(f'  {"":22} staff {m.user.email}')
        w('\nCustomers  (sign in at /login/)')
        for u in User.objects.filter(role='customer')[:4]:
            w(f'  {u.email}')
        w('  ...and more. Create your own superuser with: python manage.py createsuperuser')
