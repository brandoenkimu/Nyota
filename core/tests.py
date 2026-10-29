from django.test import TestCase, override_settings
from django.urls import reverse

from core import art


@override_settings(MEMBERS_ONLY=False)
class PublicPagesTests(TestCase):
    def test_home_loads(self):
        self.assertEqual(self.client.get(reverse('core:home')).status_code, 200)

    def test_listing_pages_load(self):
        for name in ('core:products', 'core:shops', 'core:track', 'core:about', 'accounts:login',
                     'accounts:seller_login', 'accounts:staff_login', 'accounts:signup', 'accounts:seller_signup',
                     'accounts:password_reset', 'orders:cart'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get('/definitely-not-here/').status_code, 404)

    def test_health(self):
        self.assertEqual(self.client.get('/api/health/').status_code, 200)


class ArtTests(TestCase):
    def test_svg_is_wellformed(self):
        import xml.dom.minidom as md
        for slug in art.ART_CATEGORY_SLUGS:
            md.parseString(art.product_svg('Test <&> item', slug, '7'))
        md.parseString(art.brand_logo_svg('full'))
        md.parseString(art.brand_logo_svg('mark'))


class MembersOnlyTests(TestCase):
    def test_visitor_is_sent_to_login(self):
        for path in ('/', '/products/', '/shops/', '/cart/', '/checkout/', '/p/anything/'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn('/login/', r['Location'])

    def test_login_signup_and_reset_stay_open(self):
        for path in ('/login/', '/seller/login/', '/staff/login/', '/signup/', '/seller/signup/', '/password/reset/'):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_ajax_add_to_cart_gets_json_401(self):
        r = self.client.post('/cart/add/1/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 401)
        self.assertIn('login', r.json())

    def test_payment_webhooks_are_not_blocked(self):
        r = self.client.post('/payments/stripe/webhook/', data='{}', content_type='application/json')
        self.assertNotEqual(r.status_code, 302)

    def test_member_can_see_home(self):
        from accounts.models import User
        User.objects.create_user('m', 'm@example.com', 'Pass12345!x', email_verified=True)
        self.client.login(username='m@example.com', password='Pass12345!x')
        self.assertEqual(self.client.get('/').status_code, 200)
