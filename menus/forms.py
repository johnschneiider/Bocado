from django import forms

from menus.models import DailyMenu, DailyMenuItem

class DailyMenuForm(forms.ModelForm):
    """
    Create form:
    - date NO se muestra; se setea automáticamente en la vista (hoy)
    - status NO se muestra; por defecto queda OPEN (acepta pedidos)
    """

    class Meta:
        model = DailyMenu
        fields = ["title", "description", "image", "max_orders"]
        widgets = {
            "max_orders": forms.NumberInput(attrs={"min": 0, "placeholder": "Ej: 50"}),
        }


class DailyMenuItemForm(forms.ModelForm):
    class Meta:
        model = DailyMenuItem
        fields = ["item", "price"]

