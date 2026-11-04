from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User

from .models import ErrorEvent, ErrorGroup
from .service import log_error


class ErrorTracking(TestCase):
    def test_same_error_is_one_ticket_with_two_occurrences(self):
        u = User.objects.create_user('c', 'c@x.com', 'pw-12345-xyz')

        class Req:
            path, method, user = '/cart/update/7/', 'POST', u
            META = {'HTTP_USER_AGENT': 'test', 'REMOTE_ADDR': '1.2.3.4'}
        refs = []
        for _ in range(2):
            try:
                int('x')
            except ValueError as exc:
                refs.append(log_error(Req(), exc=exc))
        self.assertEqual(ErrorGroup.objects.count(), 1)
        self.assertEqual(ErrorGroup.objects.first().count, 2)
        self.assertEqual(ErrorEvent.objects.count(), 2)
        self.assertTrue(all(r.startswith('NY-') for r in refs))

    def test_browser_error_endpoint(self):
        r = self.client.post(reverse('monitor:client_error'), data='{"message":"boom","source":"app.js:1"}', content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ErrorGroup.objects.filter(source='browser').count(), 1)

    def test_only_fixers_open_the_tracker(self):
        cust = User.objects.create_user('cu', 'cu@x.com', 'pw-12345-xyz', role=Role.CUSTOMER)
        self.client.force_login(cust)
        self.assertEqual(self.client.get(reverse('portals:error_list')).status_code, 302)
        sup = User.objects.create_user('su', 'su@x.com', 'pw-12345-xyz', role=Role.SUPPORT)
        self.client.force_login(sup)
        self.assertEqual(self.client.get(reverse('portals:error_list')).status_code, 200)
