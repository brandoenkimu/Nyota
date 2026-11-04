from django.contrib import admin

from .models import SellerVerification, VerificationDocument


class DocInline(admin.TabularInline):
    model = VerificationDocument
    extra = 0
    readonly_fields = ['kind', 'file', 'original_name', 'size', 'status', 'uploaded_at']
    can_delete = False


@admin.register(SellerVerification)
class SellerVerificationAdmin(admin.ModelAdmin):
    list_display = ['shop', 'status', 'business_type', 'submitted_at', 'admin_reviewer', 'decided_by']
    list_filter = ['status', 'business_type']
    readonly_fields = ['status', 'submitted_at', 'admin_reviewer', 'admin_reviewed_at', 'decided_by', 'decided_at',
                       'policy_accepted_at', 'policy_version']   # decisions are made in the review desk, so they are audited
    inlines = [DocInline]
