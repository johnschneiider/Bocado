from __future__ import annotations

from django.db import models
from django.utils import timezone

from menus.models import DailyMenu


def get_active_menu_for_restaurant(*, restaurant) -> DailyMenu | None:
    """
    Devuelve el menú "activo" (visible para clientes) aunque sea de otra fecha.

    Un menú es activo si:
    - is_visible=True, y
    - visible_until es NULL (compatibilidad) o visible_until > ahora
    """
    now = timezone.now()
    return (
        DailyMenu.objects.filter(restaurant=restaurant, is_visible=True)
        .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
        # Prefer the last one the negocio "habilitó" (updated_at se actualiza al cambiar visibilidad)
        .order_by("-updated_at", "-visible_until", "-created_at")
        .first()
    )


def get_active_menus_for_restaurant(*, restaurant):
    """
    Devuelve TODOS los menús activos (visibles) para clientes.
    """
    now = timezone.now()
    return (
        DailyMenu.objects.filter(restaurant=restaurant, is_visible=True)
        .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
        .order_by("-updated_at", "-visible_until", "-created_at")
    )

