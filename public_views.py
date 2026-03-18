from __future__ import annotations

from django.shortcuts import redirect, render
from django.views import View

from accounts.services import normalize_phone_digits


class RootPreAuthView(View):
    template_name = "public/preauth.html"

    def get(self, request):
        # If already authenticated as admin, go to dashboard
        if request.user.is_authenticated:
            return redirect("/dashboard/")
        # If already preauthed as customer, go to customer portal
        if request.session.get("customer_id"):
            return redirect("/cliente/")
        return render(request, self.template_name)

    def post(self, request):
        phone = (request.POST.get("phone") or "").strip()
        digits = normalize_phone_digits(phone)
        if not digits:
            return render(request, self.template_name, status=400)

        # Always treat as admin login, redirect to accounts login endpoint
        return redirect(f"/accounts/login/?next=/dashboard/")

