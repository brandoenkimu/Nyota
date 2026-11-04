from django import forms

from accounts.forms import BootstrapMixin

from .models import DocKind, SellerVerification

MAX_DOC = 5 * 1024 * 1024
ALLOWED = ('.pdf', '.jpg', '.jpeg', '.png')
MAGIC = {b'%PDF': '.pdf', b'\xff\xd8\xff': '.jpg', b'\x89PNG': '.png'}


class DetailsForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SellerVerification
        fields = ['business_type', 'legal_name', 'id_number', 'kra_pin', 'business_reg_no', 'business_address']

    def clean_kra_pin(self):
        v = self.cleaned_data['kra_pin'].strip().upper()
        if v and not (len(v) == 11 and v[0] in 'AP' and v[-1].isalpha() and v[1:-1].isdigit()):
            raise forms.ValidationError('A KRA PIN looks like A123456789Z.')
        return v


class DocumentForm(BootstrapMixin, forms.Form):
    kind = forms.ChoiceField(choices=DocKind.choices)
    file = forms.FileField(help_text='PDF, JPG or PNG, up to 5 MB.')

    def clean_file(self):
        f = self.cleaned_data['file']
        name = f.name.lower()
        if not name.endswith(ALLOWED):
            raise forms.ValidationError('Upload a PDF, JPG or PNG file.')
        if f.size > MAX_DOC:
            raise forms.ValidationError('That file is larger than 5 MB.')
        head = f.read(8)
        f.seek(0)
        ext = '.' + name.rsplit('.', 1)[-1]
        ok = any(head.startswith(sig) and (ext == e or (e == '.jpg' and ext == '.jpeg')) for sig, e in MAGIC.items())
        if not ok:
            raise forms.ValidationError('The file content does not match its type. Please upload the original file.')
        return f
