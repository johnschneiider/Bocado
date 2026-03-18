from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimeStampedUUIDModel


class MenuStatus(models.TextChoices):
    OPEN = "OPEN", "Abierto"
    CLOSED = "CLOSED", "Cerrado"


class Category(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="menu_categories"
    )
    name = models.CharField(max_length=128)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "name"], name="uniq_category_name_per_restaurant"
            )
        ]
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Item(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="items"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "name"], name="uniq_item_name_per_restaurant"
            )
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DailyMenu(TimeStampedUUIDModel):
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="daily_menus"
    )
    date = models.DateField(db_index=True)
    title = models.CharField(max_length=120, default="Menú del día")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=MenuStatus.choices, default=MenuStatus.OPEN)
    image = models.ImageField(upload_to="menus/%Y/%m/%d/", null=True, blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    visible_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Si está visible, se ocultará automáticamente al pasar esta fecha/hora.",
    )
    max_orders = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Cupo máximo de pedidos para este menú (vacío = sin límite).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "date"], name="uniq_daily_menu_per_restaurant_date"
            )
        ]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.restaurant.name} - {self.date.isoformat()}"


class DailyMenuItem(TimeStampedUUIDModel):
    daily_menu = models.ForeignKey(
        DailyMenu, on_delete=models.CASCADE, related_name="menu_items", db_index=True
    )
    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="daily_menu_entries"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Precio del ítem para este día (permite override del base_price).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["daily_menu", "item"], name="uniq_item_per_daily_menu"
            )
        ]
        ordering = ["item__name"]

    def __str__(self) -> str:
        return f"{self.daily_menu.date.isoformat()} - {self.item.name}"
