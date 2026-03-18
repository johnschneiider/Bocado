from __future__ import annotations

from django.http import Http404

from restaurants.selectors import get_restaurant_for_user


class RestaurantRequiredMixin:
    """
    Attaches `self.restaurant` based on the logged in user's membership.
    """

    restaurant = None

    def dispatch(self, request, *args, **kwargs):
        self.restaurant = get_restaurant_for_user(user=request.user)
        if self.restaurant is None:
            raise Http404("No tienes un restaurante asignado.")
        return super().dispatch(request, *args, **kwargs)

