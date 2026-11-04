"""All state changes of a seller verification go through here so each one is audited and notified."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from audit.service import record
from core.notify import notify_many, notify
from shops.models import ShopStatus

from .models import POLICY_VERSION, DocStatus, SellerVerification, Status

User = get_user_model()


class VerificationError(Exception):
    pass


def get_or_create_for(shop):
    v, _ = SellerVerification.objects.get_or_create(shop=shop, defaults={'legal_name': shop.owner.get_full_name()})
    return v


def reviewers():
    return User.objects.filter(role__in=['admin', 'ceo'], is_active=True)


@transaction.atomic
def submit(v, accepted_policy, request=None):
    if not v.editable:
        raise VerificationError('This application is already with our reviewers.')
    if not accepted_policy:
        raise VerificationError('Please accept the Seller Verification & Anti-Fraud Policy.')
    if not v.details_complete():
        raise VerificationError('Please complete all your details first.')
    missing = v.missing_kinds()
    if missing:
        from .models import DocKind
        names = ', '.join(dict(DocKind.choices)[k].split(':')[0] for k in missing)
        raise VerificationError(f'Documents still missing: {names}.')
    v.documents.filter(status=DocStatus.REJECTED).delete()
    v.documents.exclude(status=DocStatus.ACCEPTED).update(status=DocStatus.PENDING, note='')
    v.status = Status.SUBMITTED
    v.submitted_at = timezone.now()
    v.policy_accepted_at = timezone.now()
    v.policy_version = POLICY_VERSION
    v.note = ''
    v.admin_reviewer = None
    v.save()
    notify_many(list(reviewers()), f'Verification submitted: {v.shop.name}', 'A seller is waiting for document review.',
                '/staff/verifications/')
    record('verification.submitted', target=v, request=request, shop=v.shop.name)
    return v


@transaction.atomic
def review_document(doc, reviewer, accept, note='', request=None):
    doc.status = DocStatus.ACCEPTED if accept else DocStatus.REJECTED
    doc.note = note[:300]
    doc.reviewed_by = reviewer
    doc.save(update_fields=['status', 'note', 'reviewed_by'])
    record('verification.document_reviewed', target=doc.verification, request=request, actor=reviewer,
           kind=doc.kind, accepted=accept, note=note[:100])


@transaction.atomic
def request_info(v, reviewer, note, request=None):
    if v.status not in (Status.SUBMITTED, Status.ADMIN_REVIEWED):
        raise VerificationError('This application is not waiting for review.')
    if not note.strip():
        raise VerificationError('Tell the seller what is missing or unclear.')
    v.status, v.note = Status.NEEDS_INFO, note.strip()
    v.save()
    notify(v.shop.owner, 'More information needed for verification', note[:200], '/seller/verification/')
    record('verification.info_requested', target=v, request=request, actor=reviewer, note=note[:150])


@transaction.atomic
def admin_check(v, reviewer, note='', request=None):
    """Administrator confirms the documents are genuine: it then goes to the CEO for the final decision."""
    if v.status != Status.SUBMITTED:
        raise VerificationError('Only a newly submitted application can be passed to the CEO.')
    if not v.all_docs_accepted():
        raise VerificationError('Accept every required document first (or send it back for more information).')
    v.status, v.admin_reviewer, v.admin_reviewed_at = Status.ADMIN_REVIEWED, reviewer, timezone.now()
    if note:
        v.note = note
    v.save()
    notify_many(list(User.objects.filter(role='ceo', is_active=True)),
                f'Final approval needed: {v.shop.name}', f'Checked by {reviewer.display_name}.', '/staff/verifications/')
    record('verification.admin_checked', target=v, request=request, actor=reviewer)


@transaction.atomic
def approve(v, ceo, note='', request=None):
    """Only the CEO gives final approval (two-person rule: an administrator can check, never approve)."""
    if ceo.role != 'ceo':
        raise VerificationError('Only the CEO can give final approval.')
    if v.status not in (Status.SUBMITTED, Status.ADMIN_REVIEWED):
        raise VerificationError('This application is not waiting for a decision.')
    if not v.all_docs_accepted():
        raise VerificationError('Every required document must be accepted before approval.')
    v.status, v.decided_by, v.decided_at, v.note = Status.APPROVED, ceo, timezone.now(), note
    v.save()
    shop = v.shop
    shop.is_verified = True
    if shop.status != ShopStatus.SUSPENDED:
        shop.status = ShopStatus.ACTIVE
    shop.save(update_fields=['is_verified', 'status'])
    notify(shop.owner, 'You are verified!', 'Your shop is live with the Verified seller badge.', '/seller/')
    record('verification.approved', target=v, request=request, actor=ceo, shop=shop.name)


@transaction.atomic
def reject(v, reviewer, note, request=None):
    if v.status not in (Status.SUBMITTED, Status.ADMIN_REVIEWED, Status.NEEDS_INFO):
        raise VerificationError('This application is not waiting for a decision.')
    if not note.strip():
        raise VerificationError('Give the seller a reason.')
    v.status, v.decided_by, v.decided_at, v.note = Status.REJECTED, reviewer, timezone.now(), note.strip()
    v.save()
    shop = v.shop
    shop.is_verified = False
    shop.save(update_fields=['is_verified'])
    notify(shop.owner, 'Verification was not approved', note[:200], '/seller/verification/')
    record('verification.rejected', target=v, request=request, actor=reviewer, note=note[:150])
