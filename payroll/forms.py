import datetime as dt

from django import forms

from accounts.forms import BootstrapMixin

from .models import JobCategory, PayGrade, PayProfile


class GradeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PayGrade
        fields = ['name', 'rank', 'base_salary']


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = JobCategory
        fields = ['name', 'allowance_percent', 'description']


class ProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PayProfile
        fields = ['grade', 'category', 'employment_type', 'hourly_rate', 'fixed_allowance', 'apply_statutory',
                  'pay_phone', 'bank_details', 'kra_pin', 'active']

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].queryset = PayGrade.objects.filter(shop=shop)
        self.fields['category'].queryset = JobCategory.objects.filter(shop=shop)


class RunForm(BootstrapMixin, forms.Form):
    month = forms.DateField(widget=forms.DateInput(attrs={'type': 'month'}, format='%Y-%m'), input_formats=['%Y-%m'],
                            label='Month to pay', initial=lambda: (dt.date.today().replace(day=1) - dt.timedelta(days=1)))
