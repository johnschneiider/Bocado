from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from menus.models import DailyMenu


@transaction.atomic
def set_menu_visibility(*, menu: DailyMenu, enabled: bool) -> DailyMenu:
    """
    - Si se deshabilita: queda oculto (y se borra su expiración).
    - Si se habilita:
        - Si el menú es del día actual: queda visible hasta el inicio del siguiente día (00:00 local).
        - Si es de otro día (menú viejo): se reactiva por 24h desde ahora.
    """
    enabled = bool(enabled)
    if not enabled:
        menu.is_visible = False
        menu.visible_until = None
        menu.save(update_fields=["is_visible", "visible_until", "updated_at"])
        return menu

    now = timezone.now()
    today = timezone.localdate()
    if menu.date == today:
        tz = timezone.get_current_timezone()
        next_midnight_naive = datetime.combine(today + timedelta(days=1), time.min)
        next_midnight = timezone.make_aware(next_midnight_naive, tz)
        menu.visible_until = next_midnight
    else:
        menu.visible_until = now + timedelta(hours=24)

    menu.is_visible = True
    menu.save(update_fields=["is_visible", "visible_until", "updated_at"])
    return menu


def is_menu_effectively_visible(*, menu: DailyMenu) -> bool:
    if not menu.is_visible:
        return False
    if menu.visible_until is None:
        return True
    return menu.visible_until > timezone.now()

