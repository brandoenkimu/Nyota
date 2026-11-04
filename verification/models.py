from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone

POLICY_VERSION = '2026-10'


def private_storage():
    """Verification documents live OUTSIDE the public media folder; they are only served through a
    permission-checked view."""
    return FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT))


def doc_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'verification/shop{instance.verification.shop_id}/{instance.kind}-{timezone.now():%Y%m%d%H%M%S}.{ext}'


class Status(models.TextChoices):
    DRAFT = 'draft', 'Not submitted'
    SUBMITTED = 'submitted', 'Submitted: waiting for an administrator'
    NEEDS_INFO = 'needs_info', 'More information needed'
    ADMIN_REVIEWED = 'admin_reviewed', 'Checked by an administrator: waiting for the CEO'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class BusinessType(models.TextChoices):
    INDIVIDUAL = 'individual', 'Individual / sole trader'
    COMPANY = 'company', 'Registered business or company'


class DocKind(models.TextChoices):
    ID_FRONT = 'id_front', 'National ID / passport: front'
    ID_BACK = 'id_back', 'National ID: back'
    SELFIE = 'selfie', 'Selfie holding your ID'
    KRA_PIN = 'kra_pin', 'KRA PIN certificate'
    ADDRESS = 'address', 'Proof of business address (utility bill, lease)'
    BUSINESS_REG = 'business_reg', 'Business registration / certificate of incorporation'
    PERMIT = 'permit', 'Business permit or trade licence'
    OTHER = 'other', 'Other supporting document'


class DocStatus(models.TextChoices):
    PENDING = 'pending', 'Waiting for review'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'


class SellerVerification(models.Model):
    shop = models.OneToOneField('shops.Shop', on_delete=models.CASCADE, related_name='verification')
    business_type = models.CharField(max_length=12, choices=BusinessType.choices, default=BusinessType.INDIVIDUAL)
    legal_name = models.CharField('Full legal name (or registered business name)', max_length=160, blank=True)
    id_number = models.CharField('National ID / passport number', max_length=40, blank=True)
    kra_pin = models.CharField('KRA PIN', max_length=20, blank=True)
    business_reg_no = models.CharField('Business registration number', max_length=60, blank=True)
    business_address = models.CharField('Business address', max_length=200, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    policy_accepted_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=20, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    admin_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name='verifications_checked')
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='verifications_decided')
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField('Reviewer note shown to the seller', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Verification of {self.shop}'

    @property
    def editable(self):
        return self.status in (Status.DRAFT, Status.NEEDS_INFO, Status.REJECTED)

    @property
    def required_kinds(self):
        kinds = [DocKind.ID_FRONT, DocKind.ID_BACK, DocKind.SELFIE, DocKind.KRA_PIN, DocKind.ADDRESS]
        if self.business_type == BusinessType.COMPANY:
            kinds.append(DocKind.BUSINESS_REG)
        return kinds

    def missing_kinds(self):
        have = set(self.documents.exclude(status=DocStatus.REJECTED).values_list('kind', flat=True))
        return [k for k in self.required_kinds if k not in have]

    def details_complete(self):
        need = [self.legal_name, self.id_number, self.kra_pin, self.business_address]
        if self.business_type == BusinessType.COMPANY:
            need.append(self.business_reg_no)
        return all(x.strip() for x in need)

    def all_docs_accepted(self):
        docs = self.documents.exclude(status=DocStatus.REJECTED)
        have = set(docs.filter(status=DocStatus.ACCEPTED).values_list('kind', flat=True))
        return all(k in have for k in self.required_kinds)


class VerificationDocument(models.Model):
    verification = models.ForeignKey(SellerVerification, on_delete=models.CASCADE, related_name='documents')
    kind = models.CharField(max_length=14, choices=DocKind.choices)
    file = models.FileField(upload_to=doc_path, storage=private_storage)
    original_name = models.CharField(max_length=200, blank=True)
    size = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=DocStatus.choices, default=DocStatus.PENDING)
    note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kind', '-uploaded_at']

    @property
    def is_image(self):
        return self.file.name.lower().endswith(('.jpg', '.jpeg', '.png'))
