from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import Role, User
from shops.models import Shop, ShopStatus

from . import services
from .models import DocKind, DocStatus, SellerVerification, Status, VerificationDocument

PDF = b'%PDF-1.4 test'


@override_settings(PRIVATE_MEDIA_ROOT='/tmp/nyota-test-private')
class VerificationFlow(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('own', 'own@x.com', 'pw-12345-xyz', role=Role.SELLER_OWNER)
        self.shop = Shop.objects.create(owner=self.owner, name='Test Shop')
        self.admin = User.objects.create_user('adm', 'adm@x.com', 'pw-12345-xyz', role=Role.ADMIN)
        self.ceo = User.objects.create_user('ceo', 'ceo@x.com', 'pw-12345-xyz', role=Role.CEO)
        self.v = services.get_or_create_for(self.shop)
        self.v.legal_name, self.v.id_number, self.v.kra_pin, self.v.business_address = 'Own Er', '12345678', 'A123456789Z', 'Nairobi'
        self.v.save()
        for k in self.v.required_kinds:
            VerificationDocument.objects.create(verification=self.v, kind=k, file=SimpleUploadedFile(f'{k}.pdf', PDF), original_name=f'{k}.pdf')

    def test_submit_needs_policy(self):
        with self.assertRaises(services.VerificationError):
            services.submit(self.v, False)

    def test_two_person_rule(self):
        services.submit(self.v, True)
        for d in self.v.documents.all():
            services.review_document(d, self.admin, True)
        with self.assertRaises(services.VerificationError):
            services.approve(self.v, self.admin)                 # an administrator can never approve
        services.admin_check(self.v, self.admin)
        services.approve(self.v, self.ceo)
        self.shop.refresh_from_db()
        self.assertTrue(self.shop.is_verified)
        self.assertEqual(self.shop.status, ShopStatus.ACTIVE)

    def test_cannot_approve_with_unaccepted_documents(self):
        services.submit(self.v, True)
        with self.assertRaises(services.VerificationError):
            services.approve(self.v, self.ceo)

    def test_reject_keeps_shop_hidden(self):
        services.submit(self.v, True)
        services.reject(self.v, self.admin, 'Blurry ID')
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_verified)
        self.assertEqual(self.v.status, Status.REJECTED)
