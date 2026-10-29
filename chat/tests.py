from django.test import TestCase

from accounts.models import Role, User
from shops.models import Shop, ShopMember, ShopStatus

from . import services
from .models import ConversationKind


class ChatRulesTests(TestCase):
    def setUp(self):
        mk = lambda n, role, **kw: User.objects.create_user(n, f'{n}@example.com', 'Pass12345!x', role=role, **kw)
        self.owner = mk('owner', Role.SELLER_OWNER)
        self.shop = Shop.objects.create(owner=self.owner, name='Shop A', status=ShopStatus.ACTIVE)
        self.staff = mk('staff', Role.SELLER_STAFF)
        ShopMember.objects.create(shop=self.shop, user=self.staff, role='cashier')
        self.c1, self.c2 = mk('c1', Role.CUSTOMER), mk('c2', Role.CUSTOMER)
        self.admin = mk('adm', Role.ADMIN)

    def test_team_chat_is_private_to_the_shop(self):
        team = services.start_team_chat(self.shop)
        self.assertEqual(team.kind, ConversationKind.TEAM)
        self.assertTrue(services.can_access(self.owner, team))
        self.assertTrue(services.can_access(self.staff, team))
        self.assertFalse(services.can_access(self.c1, team))

    def test_staff_with_chat_permission_see_customer_chats(self):
        conv = services.start_shop_chat(self.c1, self.shop)
        self.assertTrue(services.can_access(self.staff, conv))          # cashier has the chat permission
        self.assertFalse(services.can_access(self.c2, conv))

    def test_customers_can_message_each_other_until_blocked(self):
        self.assertTrue(services.can_message(self.c1, self.c2))
        from .models import Block
        Block.objects.create(blocker=self.c2, blocked=self.c1)
        self.assertFalse(services.can_message(self.c1, self.c2))
        self.assertTrue(services.can_message(self.c1, self.admin))      # support/admin cannot be blocked out

    def test_customer_cannot_message_shop_staff_directly(self):
        self.assertFalse(services.can_message(self.c1, self.staff))

    def test_staff_can_message_owner(self):
        self.assertTrue(services.can_message(self.staff, self.owner))
