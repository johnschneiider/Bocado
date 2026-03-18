from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter(name="money")
def money(value):
    """
    Formatea un monto con:
    - puntos de miles
    - sin decimales

    Ej: 15000.00 -> "15.000"
    """
    if value is None or value == "":
        return ""

    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        try:
            i = int(value)
        except Exception:
            return str(value)
        return f"{i:,}".replace(",", ".")

    # Redondeo al entero más cercano (0 decimales)
    d0 = d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    i = int(d0)
    return f"{i:,}".replace(",", ".")

