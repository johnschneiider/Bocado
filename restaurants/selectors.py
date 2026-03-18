from __future__ import annotations

from accounts.models import RestaurantMembership
from restaurants.models import Restaurant


def get_restaurant_for_user(*, user) -> Restaurant | None:
    membership = (
        RestaurantMembership.objects.filter(user=user, is_active=True)
        .select_related("restaurant")
        .first()
    )
    return membership.restaurant if membership else None

