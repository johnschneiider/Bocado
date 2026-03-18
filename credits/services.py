from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from credits.models import Customer, Debt, DebtStatus, Payment
from credits.models import PaymentMethod as CreditPaymentMethod
from restaurants.models import Restaurant


class CreditServiceError(Exception):
    pass


def get_customer_outstanding_balance(*, customer: Customer) -> Decimal:
    """
    Returns the customer's pending amount (sum of open debts remaining).
    """
    qs = Debt.objects.filter(customer=customer, status=DebtStatus.OPEN)
    total = Decimal("0.00")
    for d in qs.only("amount_original", "amount_paid"):
        total += (d.amount_original - d.amount_paid)
    return total.quantize(Decimal("0.01"))


@transaction.atomic
def register_payment(
    *,
    restaurant: Restaurant,
    customer: Customer,
    debt: Debt,
    amount: Decimal,
    method: str,
    reference: str = "",
    paid_at=None,
) -> Payment:
    """
    MVP payment flow: 1 payment -> 1 debt (partial payments supported).
    """
    if customer.restaurant_id != restaurant.id or debt.restaurant_id != restaurant.id:
        raise CreditServiceError("El cliente/deuda no pertenece a este restaurante.")

    if debt.customer_id != customer.id:
        raise CreditServiceError("La deuda no pertenece al cliente.")

    if debt.status != DebtStatus.OPEN:
        raise CreditServiceError("La deuda ya está saldada.")

    if amount <= 0:
        raise CreditServiceError("El monto debe ser mayor a 0.")

    if paid_at is None:
        paid_at = timezone.now()

    payment = Payment.objects.create(
        restaurant=restaurant,
        customer=customer,
        debt=debt,
        method=method,
        amount=amount,
        reference=reference.strip(),
        paid_at=paid_at,
    )

    debt.amount_paid = (debt.amount_paid + amount).quantize(Decimal("0.01"))
    if debt.amount_paid >= debt.amount_original:
        debt.amount_paid = debt.amount_original
        debt.status = DebtStatus.SETTLED
        debt.settled_at = timezone.now()

    debt.save(update_fields=["amount_paid", "status", "settled_at"])
    return payment


@transaction.atomic
def settle_customer_debts(*, restaurant: Restaurant, customer: Customer) -> None:
    """
    Marca como pagadas todas las deudas abiertas del cliente (crea pagos por el faltante).
    """
    if customer.restaurant_id != restaurant.id:
        raise CreditServiceError("El cliente no pertenece a este restaurante.")

    open_debts = (
        Debt.objects.select_for_update()
        .filter(restaurant=restaurant, customer=customer, status=DebtStatus.OPEN)
        .only("id", "amount_original", "amount_paid")
        .order_by("opened_at")
    )
    for d in open_debts:
        remaining = (d.amount_original - d.amount_paid).quantize(Decimal("0.01"))
        if remaining <= 0:
            continue
        register_payment(
            restaurant=restaurant,
            customer=customer,
            debt=d,
            amount=remaining,
            method=CreditPaymentMethod.CASH,
            reference="Marcado como pagado",
        )

