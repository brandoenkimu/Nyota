from django import forms

from accounts.forms import BootstrapMixin

from .models import PaymentMethod, ShopOrderStatus


class CheckoutForm(BootstrapMixin, forms.Form):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20, label='Phone (for delivery)')
    line1 = forms.CharField(max_length=200, label='Street, building, landmark')
    city = forms.CharField(max_length=80)
    county = forms.CharField(max_length=80, required=False)
    lat = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    lng = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    notes = forms.CharField(max_length=300, required=False, label='Delivery notes',
                            widget=forms.TextInput(attrs={'placeholder': 'Gate code, best time, ...'}))
    payment_method = forms.ChoiceField(choices=PaymentMethod.choices, widget=forms.RadioSelect,
                                       initial=PaymentMethod.MPESA)
    mpesa_phone = forms.CharField(max_length=20, required=False, label='M-Pesa number')
    save_address = forms.BooleanField(required=False, label='Save this address for next time')


class TrackingUpdateForm(BootstrapMixin, forms.Form):
    """Used by sellers and administrators to move an order along and leave a tracking event."""
    status = forms.ChoiceField(choices=ShopOrderStatus.choices)
    title = forms.CharField(max_length=120, required=False, help_text='Shown on the customer timeline')
    detail = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={'rows': 2}))
    location_label = forms.CharField(max_length=120, required=False, label='Where is the parcel?')
    lat = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    lng = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    courier = forms.CharField(max_length=60, required=False)
    tracking_number = forms.CharField(max_length=60, required=False)
    expected_delivery = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    occurred_at = forms.DateTimeField(required=False, label='Event time (leave empty for now)',
                                      widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
                                      input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'])
