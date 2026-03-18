from __future__ import annotations

from django.contrib.auth.backends import ModelBackend

from accounts.services import verify_phone_otp


class PhoneOTPBackend(ModelBackend):
    """
    Auth backend for phone + OTP (no passwords).
    """

    def authenticate(self, request, phone: str | None = None, code: str | None = None, **kwargs):
        if phone is None or code is None:
            return None
        return verify_phone_otp(phone=phone, code=code)

