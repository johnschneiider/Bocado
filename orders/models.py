from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimeStampedUUIDModel


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    CONFIRMED = "CONFIRMED", "Confirmado"
    DELIVERED = "DELIVERED", "Entregado"
    CANCELLED = "CANCELLED", "Cancelado"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Contado"
    CREDIT = "CREDIT", "Crédito"
    TRANSFER = "TRANSFER", "Transferencia"


class Order(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="orders", db_index=True
    )
    menu = models.ForeignKey(
        "menus.DailyMenu", on_delete=models.PROTECT, related_name="orders"
    )

    # Customers don't login in MVP; keep both an optional FK and snapshot fields.
    customer = models.ForeignKey(
        "credits.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)
    customer_address = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=16, choices=OrderStatus.choices, default=OrderStatus.PENDING, db_index=True
    )
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices)

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )

    transfer_reference = models.CharField(max_length=64, blank=True)
    customer_note = models.CharField(
        max_length=255,
        blank=True,
        help_text="Mensaje opcional del cliente para el negocio.",
    )

    # Compra de menú: completo (bandeja + sopa) vs solo bandeja
    is_full_menu = models.BooleanField(
        default=False, help_text="Si el cliente compró el menú completo (bandeja y sopa)."
    )

    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order {self.id}"


class OrderItem(TimeStampedUUIDModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", db_index=True)
    daily_menu_item = models.ForeignKey(
        "menus.DailyMenuItem", on_delete=models.PROTECT, related_name="order_items"
    )

    item_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        default=Decimal("0.00"),
    )

    notes = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.item_name}"
