from django.db import models

from common.models import TimeStampedUUIDModel


class Category(models.Model):
    """
    Categorías de comida para el catálogo de restaurantes.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, blank=True)  # Font Awesome icon name
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'name']
    
    def __str__(self) -> str:
        return self.name


class RestaurantStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Activo"
    SUSPENDED = "SUSPENDED", "Suspendido"


class Restaurant(TimeStampedUUIDModel):
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    tax_id = models.CharField(max_length=64, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=16, choices=RestaurantStatus.choices, default=RestaurantStatus.ACTIVE
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="restaurants"
    )
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.5)
    image_url = models.URLField(max_length=500, blank=True)
    is_featured = models.BooleanField(default=False, help_text="Mostrar en sección destacada")

    def __str__(self) -> str:
        return self.name


class RestaurantLocation(TimeStampedUUIDModel):
    """
    Prepared for multiple branches/locations per restaurant (future).
    """

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(max_length=255, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128, blank=True)
    region = models.CharField(max_length=128, blank=True)
    country = models.CharField(max_length=2, default="CO")
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_location_per_restaurant",
            )
        ]

    def __str__(self) -> str:
        label = self.name or "Main location"
        return f"{self.restaurant.name} - {label}"
