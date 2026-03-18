from django import forms

from credits.models import Customer


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["full_name", "address"]

