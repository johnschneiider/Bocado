from django import forms

from credits.models import Customer, Debt, Payment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["full_name", "phone", "email", "document_id", "notes", "is_active"]


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["debt", "method", "amount", "reference", "paid_at"]

        widgets = {
            "paid_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # HTML datetime-local -> "YYYY-MM-DDTHH:MM"
        self.fields["paid_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

