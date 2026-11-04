from django.test import TestCase

from accounts.models import Role, User
from accounts.profiles import profile_access


class ProfileRules(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('a', 'a@x.com', 'pw-12345-xyz')
        self.b = User.objects.create_user('b', 'b@x.com', 'pw-12345-xyz')
        self.admin = User.objects.create_user('adm', 'adm@x.com', 'pw-12345-xyz', role=Role.ADMIN)
        self.dev = User.objects.create_user('dev', 'dev@x.com', 'pw-12345-xyz', role=Role.DEVELOPER)

    def test_customer_sees_card_unless_private(self):
        self.assertEqual(profile_access(self.a, self.b), 'card')
        self.b.profile_visibility = 'private'
        self.b.save()
        self.assertIsNone(profile_access(self.a, self.b))

    def test_customer_cannot_see_staff(self):
        self.assertIsNone(profile_access(self.a, self.dev))

    def test_admin_sees_everyone_and_staff_see_colleagues(self):
        self.assertEqual(profile_access(self.admin, self.a), 'full')
        self.assertEqual(profile_access(self.dev, self.admin), 'staff')
        self.assertEqual(profile_access(self.admin, self.dev), 'full')
