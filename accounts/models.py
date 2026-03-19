from django.conf import settings
from django.db import models

from common.models import TimeStampedUUIDModel


class UserRole(models.TextChoices):
    SAAS_ADMIN = "SAAS_ADMIN", "Administrador SaaS"
    RESTAURANT_ADMIN = "RESTAURANT_ADMIN", "Administrador del restaurante"
    CUSTOMER = "CUSTOMER", "Cliente"


class UserProfile(TimeStampedUUIDModel):
    """
    Extends Django Auth User.

    Notes:
    - Customers do NOT login in the MVP (they are modeled in `credits.Customer`).
    - Phone fields are included to enable future OTP flows.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=32, choices=UserRole.choices)
    phone = models.CharField(max_length=32, blank=True)
    is_phone_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.phone:
            # store digits only (ex: 3117451274 or 573117451274)
            self.phone = "".join(ch for ch in self.phone.strip() if ch.isdigit())
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class RestaurantMembershipRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"


class RestaurantMembership(TimeStampedUUIDModel):
    """
    Links a Django user to a Restaurant tenant.

    A single user can manage multiple restaurants (future-proof),
    while the SaaS Admin isn't required to have memberships.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="restaurant_memberships"
    )
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=RestaurantMembershipRole.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "restaurant"], name="uniq_user_restaurant_membership"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.restaurant.name} ({self.role})"


class PhoneOTP(TimeStampedUUIDModel):
    """
    One-time password for phone login (admins only).
    Stored hashed (best-effort) and expires quickly.
    """

    phone = models.CharField(max_length=32, db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "expires_at"]),
        ]

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None
