from django.contrib import admin

from .models import JobCategory, PayGrade, PayProfile, PayrollRun, Payslip

admin.site.register([JobCategory, PayGrade, PayProfile])


class SlipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    fields = ['user', 'gross', 'net']
    readonly_fields = ['user', 'gross', 'net']
    can_delete = False


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'status', 'created_by', 'approved_by', 'paid_at']
    inlines = [SlipInline]
