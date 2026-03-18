from __future__ import annotations

from credits.models import Customer
from restaurants.models import Restaurant


def set_customer_session(request, *, customer: Customer) -> None:
    request.session["customer_id"] = str(customer.id)
    request.session["customer_phone"] = customer.phone


def clear_customer_session(request) -> None:
    request.session.pop("customer_id", None)
    request.session.pop("customer_phone", None)


def get_or_create_customer_by_phone(*, phone_digits: str) -> Customer:
    """
    Minimal MVP:
    - If customer exists (any restaurant), reuse the most recently updated.
    - Else create in the first ACTIVE restaurant (fallback to first restaurant).
    """
    phone_digits = "".join(ch for ch in (phone_digits or "") if ch.isdigit())
    if not phone_digits:
        raise ValueError("phone_digits required")

    # Keep this portable: compare in Python (small dataset in MVP)
    customers = list(Customer.objects.exclude(phone="").only("id", "phone", "restaurant_id", "updated_at"))
    matches = [c for c in customers if "".join(ch for ch in c.phone if ch.isdigit()) == phone_digits]
    if matches:
        matches.sort(key=lambda c: c.updated_at, reverse=True)
        return matches[0]

    restaurant = Restaurant.objects.filter(status="ACTIVE").order_by("created_at").first()
    if restaurant is None:
        restaurant = Restaurant.objects.order_by("created_at").first()
    if restaurant is None:
        raise ValueError("No restaurants exist to attach a customer.")

    return Customer.objects.create(
        restaurant=restaurant,
        full_name=f"Cliente {phone_digits}",
        phone=phone_digits,
        is_active=True,
    )


def is_customer_profile_complete(*, customer: Customer) -> bool:
    # “Completamente autenticado” para el cliente = nombre real + dirección.
    if not (customer.full_name or "").strip():
        return False
    if not (customer.address or "").strip():
        return False
    # Evita el placeholder inicial "Cliente <tel>"
    digits = "".join(ch for ch in (customer.phone or "") if ch.isdigit())
    if customer.full_name.strip() == f"Cliente {digits}":
        return False
    return True

