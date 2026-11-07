from django import forms
from django.core.exceptions import ValidationError


class BootstrapMixin:
    """Same small helper accounts/forms.py uses: gives every widget the Bootstrap classes so a
    hand-written form still looks right. Kept as a local copy here (instead of importing accounts'
    version) because accounts already imports from core -- importing the other way would be circular."""

    def _style(self):
        for field in self.fields.values():
            w = field.widget
            cls = 'form-select' if isinstance(w, (forms.Select, forms.SelectMultiple)) else 'form-control'
            w.attrs['class'] = (w.attrs.get('class', '') + ' ' + cls).strip()


class ContactForm(BootstrapMixin, forms.Form):
    """The public contact page. No account needed to use it, so it gets its own, independent
    defences: a honeypot field real visitors never see or fill in, and the view layer adds a
    per-IP rate limit on top (see core.views.contact)."""

    TOPICS = [
        ('general', 'General question'),
        ('seller', 'Becoming a seller'),
        ('support', 'Order or account support'),
        ('partnership', 'Partnership or press'),
    ]

    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Your name', 'autocomplete': 'name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}))
    topic = forms.ChoiceField(choices=TOPICS, initial='general')
    message = forms.CharField(max_length=2000,
                               widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'How can we help?'}))
    # Honeypot: a field real browsers never fill in because it's hidden from sighted and screen-reader
    # users alike. A bot that fills in every field on the page trips it and the submission is dropped.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'autocomplete': 'off', 'tabindex': '-1', 'class': 'hp-field', 'aria-hidden': 'true',
    }))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise ValidationError('Spam check failed.')
        return ''
