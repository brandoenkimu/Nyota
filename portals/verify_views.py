"""Seller verification: the seller's upload page and the administrator / CEO review desk."""
import mimetypes

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from audit.service import record
from core.utils import paginate
from verification import services
from verification.forms import DetailsForm, DocumentForm
from verification.models import DocKind, DocStatus, SellerVerification, Status, VerificationDocument

from .common import badge, link, listing, role_required, show

REVIEW = ('admin', 'ceo')


# ------------------------------------------------------------------ seller
@role_required('seller_owner')
def seller_verification(request):
    shop = request.user.shop
    v = services.get_or_create_for(shop)
    posting_details = request.method == 'POST' and request.POST.get('action') in ('save', 'submit')
    # Only bind the details form to POST data when ITS form was the one submitted — otherwise, submitting the
    # document-upload form (a separate <form> on the same page) made this form show "required" on every field,
    # since none of its fields are present in that POST body.
    details = DetailsForm(request.POST if posting_details else None, instance=v, prefix='d') if v.editable else None
    docform = DocumentForm(prefix='u')
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if not v.editable and action != 'noop':
                raise services.VerificationError('Your application is locked while it is being reviewed.')
            if action == 'save' and details.is_valid():
                details.save()
                record('verification.details_saved', target=v, request=request)
                messages.success(request, 'Details saved.')
                return redirect('portals:seller_verification')
            if action == 'upload':
                docform = DocumentForm(request.POST, request.FILES, prefix='u')
                if docform.is_valid():
                    f, kind = docform.cleaned_data['file'], docform.cleaned_data['kind']
                    if kind != DocKind.OTHER:
                        v.documents.filter(kind=kind).exclude(status=DocStatus.ACCEPTED).delete()
                    VerificationDocument.objects.create(verification=v, kind=kind, file=f, original_name=f.name[:200],
                                                        size=f.size)
                    record('verification.document_uploaded', target=v, request=request, kind=kind)
                    messages.success(request, 'Document uploaded.')
                    return redirect('portals:seller_verification')
            if action == 'submit':
                if details is not None and details.is_valid():
                    details.save()
                services.submit(v, bool(request.POST.get('accept_policy')), request)
                messages.success(request, 'Submitted. An administrator and then the CEO will review your documents.')
                return redirect('portals:seller_verification')
        except services.VerificationError as exc:
            messages.error(request, str(exc))
    docs = list(v.documents.all())
    names = dict(DocKind.choices)
    missing = [names[k] for k in v.missing_kinds()]
    return show(request, 'portal/verification.html', {
        'v': v, 'details': details, 'docform': docform, 'docs': docs, 'missing': missing,
        'steps': [('Submitted', Status.SUBMITTED), ('Checked by an administrator', Status.ADMIN_REVIEWED),
                  ('Approved by the CEO', Status.APPROVED)],
        'shop': shop}, 'Seller verification')


@role_required('seller_owner')
@require_POST
def seller_doc_delete(request, pk):
    doc = get_object_or_404(VerificationDocument, pk=pk, verification__shop=request.user.shop)
    if doc.verification.editable and doc.status != DocStatus.ACCEPTED:
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Document removed.')
    return redirect('portals:seller_verification')


# --------------------------------------------------------------- file access
@role_required('seller_owner', 'admin', 'ceo')
def document_file(request, pk):
    doc = get_object_or_404(VerificationDocument.objects.select_related('verification__shop'), pk=pk)
    if request.user.role == 'seller_owner' and doc.verification.shop_id != getattr(request.user.shop, 'pk', None):
        raise Http404
    try:
        fh = doc.file.open('rb')
    except FileNotFoundError:
        raise Http404
    record('verification.document_viewed', target=doc.verification, request=request, kind=doc.kind)
    resp = FileResponse(fh, content_type=mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream')
    resp['Content-Disposition'] = f'inline; filename="{doc.kind}{doc.file.name[doc.file.name.rfind("."):]}"'
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Cache-Control'] = 'private, no-store'
    return resp


# ------------------------------------------------------------ review desk
@role_required(*REVIEW)
def review_list(request):
    status = request.GET.get('status', 'open')
    qs = SellerVerification.objects.select_related('shop__owner')
    if status == 'open':
        qs = qs.filter(status__in=[Status.SUBMITTED, Status.ADMIN_REVIEWED])
    elif status:
        qs = qs.filter(status=status)
    page = paginate(request, qs, 20)
    rows = [{'cells': [link(f'/staff/verifications/{v.pk}/', v.shop.name), v.shop.owner.display_name,
                       v.get_business_type_display(), v.submitted_at.strftime('%d %b %H:%M') if v.submitted_at else '-',
                       badge(v.status, v.get_status_display())], 'url': f'/staff/verifications/{v.pk}/'}
            for v in page.object_list]
    filters = [{'name': 'status', 'label': 'Show', 'type': 'select', 'value': status,
                'options': [('open', 'Waiting for review'), ('', 'Everything')] + list(Status.choices)}]
    sub = ('Administrators check the documents; the CEO gives the final approval.'
           if request.user.role == 'admin' else 'You give the final approval after an administrator has checked.')
    return listing(request, 'Seller verification', ['Shop', 'Owner', 'Type', 'Submitted', 'Status'], rows, page, filters,
                   empty='Nothing is waiting for review.', subtitle=sub)


@role_required(*REVIEW)
def review_detail(request, pk):
    v = get_object_or_404(SellerVerification.objects.select_related('shop__owner', 'admin_reviewer', 'decided_by'), pk=pk)
    if request.method == 'POST':
        action, note = request.POST.get('action', ''), request.POST.get('note', '')
        try:
            if action in ('accept_doc', 'reject_doc'):
                doc = get_object_or_404(VerificationDocument, pk=request.POST.get('doc'), verification=v)
                if action == 'reject_doc' and not note.strip():
                    raise services.VerificationError('Say why the document is rejected.')
                services.review_document(doc, request.user, action == 'accept_doc', note, request)
            elif action == 'info':
                services.request_info(v, request.user, note, request)
                messages.success(request, 'Sent back to the seller.')
            elif action == 'check':
                services.admin_check(v, request.user, note, request)
                messages.success(request, 'Passed to the CEO for final approval.')
            elif action == 'approve':
                services.approve(v, request.user, note, request)
                messages.success(request, 'Approved. The shop is live and verified.')
            elif action == 'reject':
                services.reject(v, request.user, note, request)
                messages.success(request, 'Rejected. The seller was told why.')
        except services.VerificationError as exc:
            messages.error(request, str(exc))
        return redirect('portals:verification_detail', pk=pk)
    return show(request, 'portal/verification_review.html', {
        'v': v, 'docs': v.documents.all(), 'missing': v.missing_kinds(), 'is_ceo': request.user.role == 'ceo',
        'can_decide': v.status in (Status.SUBMITTED, Status.ADMIN_REVIEWED)}, f'Verify {v.shop.name}')
