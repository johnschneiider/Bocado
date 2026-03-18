from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from accounts.services import get_admin_user_by_phone, normalize_phone_digits


@method_decorator(never_cache, name="dispatch")
class PhoneLoginStartView(View):
    template_name = "accounts/phone_login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        phone = (request.POST.get("phone") or "").strip()
        digits = normalize_phone_digits(phone)
        if not digits:
            messages.error(request, "Ingresa un teléfono válido.")
            return render(request, self.template_name, status=400)

        # Ensure any customer session is cleared
        request.session.pop("customer_id", None)
        request.session.pop("customer_phone", None)

        # Try admin login first (any phone can be admin)
        user = get_admin_user_by_phone(phone=digits, create_if_not_exists=True)
        if user:
            # Use ModelBackend since we're bypassing OTP for MVP
            from django.contrib.auth.backends import ModelBackend
            login(request, user, backend=ModelBackend)
            return redirect(request.GET.get("next") or "/dashboard/")
        
        messages.error(request, "No se pudo iniciar sesión. Intente de nuevo.")
        return render(request, self.template_name, status=400)


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
