from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimeStampedUUIDModel


class DebtStatus(models.TextChoices):
    OPEN = "OPEN", "Abierta"
    SETTLED = "SETTLED", "Saldada"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Contado"
    TRANSFER = "TRANSFER", "Transferencia"


class Customer(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="customers"
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    document_id = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = "".join(ch for ch in self.phone.strip() if ch.isdigit())
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "full_name"], name="uniq_customer_name_per_restaurant"
            )
        ]
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class Debt(TimeStampedUUIDModel):
    """
    One debt per credit order (MVP).
    """

    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="debts", db_index=True
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="debts", db_index=True)
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="credit_debt"
    )

    status = models.CharField(max_length=16, choices=DebtStatus.choices, default=DebtStatus.OPEN, db_index=True)
    amount_original = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return f"Debt {self.id} - {self.customer.full_name}"


class Payment(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="payments"
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments")
    debt = models.ForeignKey(
        Debt, on_delete=models.PROTECT, related_name="payments", null=True, blank=True
    )

    method = models.CharField(max_length=16, choices=PaymentMethod.choices)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    reference = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField()

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"Payment {self.id} - {self.customer.full_name}"
