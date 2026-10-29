from django.test import TestCase
from django.urls import reverse

from .models import Role, User
from .staffnames import build_identity, domain_part, name_part, temp_password


class StaffIdentityTests(TestCase):
    def test_platform_identity(self):
        u, e = build_identity('Jane', 'Kamau', 'ceo', 'nyota.market', lambda *_: False)
        self.assertEqual((u, e), ('jane.kamau.ceo', 'jane.kamau.ceo@nyota.market'))

    def test_collision_adds_number(self):
        taken = {'jane.kamau.ceo'}
        u, _ = build_identity('Jane', 'Kamau', 'ceo', 'x.com', lambda un, em: un in taken)
        self.assertEqual(u, 'jane.kamau.ceo2')

    def test_accents_and_spaces(self):
        self.assertEqual(name_part("O'Brien-Müller"), 'obrienmuller')
        self.assertEqual(domain_part('Kilimo Fresh Hub'), 'kilimo-fresh-hub')

    def test_temp_password_strength(self):
        for _ in range(20):
            p = temp_password()
            self.assertTrue(any(c.isdigit() for c in p) and any(c.isupper() for c in p) and any(c.islower() for c in p))


class PortalDoorTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('c', 'c@example.com', 'Pass12345!x', role=Role.CUSTOMER, email_verified=True)
        self.admin = User.objects.create_user('a.admin', 'a.admin@nyota.market', 'Pass12345!x', role=Role.ADMIN, email_verified=True)

    def test_customer_cannot_use_staff_door(self):
        r = self.client.post(reverse('accounts:staff_login'), {'username': 'c@example.com', 'password': 'Pass12345!x'})
        self.assertEqual(r.status_code, 200)          # form re-rendered with an error, not logged in
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_can_use_staff_door(self):
        r = self.client.post(reverse('accounts:staff_login'), {'username': 'a.admin', 'password': 'Pass12345!x'})
        self.assertEqual(r.status_code, 302)

    def test_customer_blocked_from_admin_portal(self):
        self.client.force_login(self.customer)
        r = self.client.get(reverse('portals:admin_home'))
        self.assertEqual(r.status_code, 302)
