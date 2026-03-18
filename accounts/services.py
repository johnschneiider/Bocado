from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import PhoneOTP, UserProfile, UserRole


class OTPServiceError(Exception):
    pass


def normalize_phone_digits(phone: str) -> str:
    phone = (phone or "").strip()
    return "".join(ch for ch in phone if ch.isdigit())


def _hash_code(*, phone: str, code: str) -> str:
    """
    Best-effort hash for OTP validation.
    Uses SECRET_KEY as salt (works on SQLite/Postgres).
    """
    msg = f"{normalize_phone_digits(phone)}:{code}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _generate_code() -> str:
    # 6 digits
    return f"{secrets.randbelow(1_000_000):06d}"


def get_admin_user_by_phone(*, phone: str, create_if_not_exists: bool = True):
    digits = normalize_phone_digits(phone)
    if not digits:
        return None
    # Small dataset in MVP: filter in Python to be robust across formats (+57, spaces, etc.)
    qs = UserProfile.objects.select_related("user").filter(
        role__in=[UserRole.SAAS_ADMIN, UserRole.RESTAURANT_ADMIN]
    )
    for p in qs.only("phone", "user__id", "user__username"):
        if normalize_phone_digits(p.phone) == digits:
            return p.user
    # Auto-create admin user and profile if doesn't exist
    if create_if_not_exists:
        return get_or_create_admin_user(phone_digits=digits)
    return None


@transaction.atomic
def get_or_create_admin_user(*, phone_digits: str):
    from django.contrib.auth import get_user_model
    from accounts.models import RestaurantMembership
    from restaurants.models import Restaurant, RestaurantLocation

    User = get_user_model()
    profile = UserProfile.objects.filter(phone=phone_digits).select_related("user").first()
    if profile:
        return profile.user
    
    # Create user and profile
    user = User.objects.create_user(username=f"admin_{phone_digits}")
    profile = UserProfile.objects.create(
        user=user,
        role=UserRole.RESTAURANT_ADMIN,
        phone=phone_digits,
        is_phone_verified=True,
    )
    
    # Create a default restaurant for this admin
    restaurant = Restaurant.objects.create(
        name=f"Restaurante {phone_digits[-4:]}",  # Use last 4 digits as name
        phone=phone_digits,
    )
    
    # Create a default location for the restaurant
    RestaurantLocation.objects.create(
        restaurant=restaurant,
        name="Principal",
        address_line1="Dirección por defecto",
        is_primary=True,
    )
    
    # Assign restaurant to user
    RestaurantMembership.objects.create(
        user=user,
        restaurant=restaurant,
        is_active=True,
    )
    
    return user


@transaction.atomic
def create_phone_otp(*, phone: str, ttl_minutes: int = 5) -> str:
    """
    Creates a new OTP for a phone number.
    In MVP, delivery is a stub (prints to console via view).
    """
    user = get_admin_user_by_phone(phone=phone)
    # Do not leak whether phone exists
    if user is None:
        # Still return a fake code (not stored) to keep timing consistent
        return _generate_code()

    code = _generate_code()
    now = timezone.now()
    PhoneOTP.objects.create(
        phone=normalize_phone_digits(phone),
        code_hash=_hash_code(phone=phone, code=code),
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    return code


@transaction.atomic
def verify_phone_otp(*, phone: str, code: str, max_attempts: int = 5):
    phone = normalize_phone_digits(phone)
    code = (code or "").strip()
    if not phone or not code:
        return None

    user = get_admin_user_by_phone(phone=phone)
    if user is None:
        return None

    now = timezone.now()
    otp = (
        PhoneOTP.objects.select_for_update()
        .filter(phone=phone, consumed_at__isnull=True, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        return None

    if otp.attempts >= max_attempts:
        return None

    otp.attempts += 1
    expected = otp.code_hash
    got = _hash_code(phone=phone, code=code)
    if hmac.compare_digest(expected, got):
        otp.consumed_at = now
        otp.save(update_fields=["attempts", "consumed_at"])
        return user

    otp.save(update_fields=["attempts"])
    return None

