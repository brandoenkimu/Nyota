from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, Attendance, SocialAccount, StaffProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'is_active', 'email_verified', 'last_login')
    list_filter = ('role', 'is_active', 'email_verified', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Nyota', {'fields': ('role', 'phone', 'avatar', 'bio', 'email_verified', 'must_change_password', 'theme', 'accent')}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (('Nyota', {'fields': ('email', 'role')}),)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_title', 'employee_no', 'department', 'hired_on')
    search_fields = ('user__email', 'employee_no', 'job_title')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'clock_in', 'clock_out', 'late')
    list_filter = ('late', 'date')


admin.site.register(Address)
admin.site.register(SocialAccount)
