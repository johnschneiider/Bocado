from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from accounts.services import get_admin_user_by_phone, normalize_phone_digits, get_or_create_customer_user


@method_decorator(never_cache, name="dispatch")
class PhoneLoginStartView(View):
    template_name = "accounts/phone_login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        from accounts.models import UserProfile, UserRole
        
        phone = (request.POST.get("phone") or "").strip()
        digits = normalize_phone_digits(phone)
        if not digits:
            messages.error(request, "Ingresa un teléfono válido.")
            return render(request, self.template_name, status=400)

        # Ensure any customer session is cleared
        request.session.pop("customer_id", None)
        request.session.pop("customer_phone", None)

        # Check if user exists with this phone
        profile = UserProfile.objects.filter(phone=digits).select_related("user").first()
        
        if profile is None:
            # New phone - create as customer and redirect to customer portal
            user = get_or_create_customer_user(phone_digits=digits)
            if user:
                # Log in and redirect to customer portal
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                request.session['customer_id'] = str(user.id)
                request.session['customer_phone'] = digits
                return redirect('home')
        
        elif profile.role in [UserRole.SAAS_ADMIN, UserRole.RESTAURANT_ADMIN]:
            # Existing admin - allow login to dashboard
            login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(request.GET.get("next") or "/dashboard/")
        
        elif profile.role == UserRole.CUSTOMER:
            # Existing customer - redirect to customer portal
            login(request, profile.user, backend="django.contrib.auth.backends.ModelBackend")
            request.session['customer_id'] = str(profile.user.id)
            request.session['customer_phone'] = digits
            return redirect('home')
        
        messages.error(request, "No se pudo iniciar sesión. Intente de nuevo.")
        return render(request, self.template_name, status=400)


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
