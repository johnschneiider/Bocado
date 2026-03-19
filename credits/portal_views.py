from __future__ import annotations

from django.db import models
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.utils import timezone

from credits.models import Customer
from credits.portal_forms import CustomerProfileForm
from credits.portal_services import clear_customer_session, is_customer_profile_complete
from credits.services import get_customer_outstanding_balance
from menus.models import DailyMenu, DailyMenuItem, MenuStatus
from menus.selectors import get_active_menus_for_restaurant
from orders.models import Order, OrderStatus
from orders.models import PaymentMethod
from orders.services import OrderLineInput, OrderServiceError, create_order


class CustomerPortalHomeView(View):
    template_name = "credits/portal_home.html"

    def get(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return redirect("/accounts/login/")

        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if customer is None:
            clear_customer_session(request)
            return redirect("/accounts/login/")

        menus = list(get_active_menus_for_restaurant(restaurant=customer.restaurant))
        menu_items_by_menu_id: dict[str, list[DailyMenuItem]] = {}
        if menus:
            all_items = (
                DailyMenuItem.objects.select_related("item")
                .filter(daily_menu__in=menus)
                .exclude(item__name__icontains="jugo")
                .order_by("daily_menu_id", "item__name")
            )
            for mi in all_items:
                key = str(mi.daily_menu_id)
                menu_items_by_menu_id.setdefault(key, []).append(mi)

        menu_cards: list[tuple[DailyMenu, list[DailyMenuItem]]] = [
            (m, menu_items_by_menu_id.get(str(m.id), [])) for m in menus
        ]

        orders = (
            Order.objects.filter(customer=customer)
            .prefetch_related("items")
            .select_related("menu", "credit_debt")
            .order_by("-created_at")[:30]
        )

        ctx = {
            "customer": customer,
            "menu_cards": menu_cards,
            "is_profile_complete": is_customer_profile_complete(customer=customer),
            "outstanding": get_customer_outstanding_balance(customer=customer),
            "orders": orders,
        }
        return render(request, self.template_name, ctx)


class CustomerPortalProfileView(View):
    template_name = "credits/portal_profile.html"

    def get(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return redirect("/accounts/login/")
        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if customer is None:
            clear_customer_session(request)
            return redirect("/accounts/login/")
        form = CustomerProfileForm(instance=customer)
        return render(request, self.template_name, {"customer": customer, "form": form})

    def post(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return redirect("/accounts/login/")
        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if customer is None:
            clear_customer_session(request)
            return redirect("/accounts/login/")

        form = CustomerProfileForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect("/cliente/")
        return render(request, self.template_name, {"customer": customer, "form": form}, status=400)


class CustomerPortalOrderCreateView(View):
    def post(self, request):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return redirect("/accounts/login/")

        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if customer is None:
            clear_customer_session(request)
            return redirect("/accounts/login/")

        if not is_customer_profile_complete(customer=customer):
            return redirect("/cliente/perfil/")

        menu_id = (request.POST.get("menu_id") or "").strip()
        if not menu_id:
            return redirect("/cliente/")

        now = timezone.now()
        menu = (
            DailyMenu.objects.filter(restaurant=customer.restaurant, id=menu_id, is_visible=True)
            .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
            .first()
        )
        if menu is None or menu.status != MenuStatus.OPEN:
            return redirect("/cliente/")

        # Enforce cupo on the server side too (urgency + correctness)
        if menu.max_orders is not None:
            active_orders_count = (
                Order.objects.filter(restaurant=customer.restaurant, menu=menu)
                .exclude(status=OrderStatus.CANCELLED)
                .count()
            )
            remaining = int(menu.max_orders) - int(active_orders_count)
            if remaining <= 0:
                messages.warning(request, "Este menú se agotó.")
                return redirect("/cliente/")

        items = list(
            DailyMenuItem.objects.select_related("item")
            .filter(daily_menu=menu)
            .exclude(item__name__icontains="jugo")
            .order_by("item__name")
        )
        if not items:
            return redirect("/cliente/")

        # Menú: bandeja siempre. Sopa opcional si se activa "menú completo".
        def _norm(s: str) -> str:
            return (s or "").strip().casefold()

        bandeja = next((mi for mi in items if "bandeja" in _norm(mi.item.name)), None) or items[0]
        sopa = next(
            (mi for mi in items if ("sopa" in _norm(mi.item.name) or "caldo" in _norm(mi.item.name))),
            None,
        )
        if sopa is None:
            # Fallback: segundo ítem distinto a bandeja
            sopa = next((mi for mi in items if mi.id != bandeja.id), None)

        payment_method = request.POST.get("payment_method") or PaymentMethod.CASH
        transfer_reference = (request.POST.get("transfer_reference") or "").strip()
        customer_note = (request.POST.get("customer_note") or "").strip()
        # Address comes from the profile (required). Ignore any POST override.
        customer_address = customer.address

        is_full_menu = request.POST.get("is_full_menu") in ("1", "true", "True", "on", "yes")
        lines: list[OrderLineInput] = [OrderLineInput(daily_menu_item_id=str(bandeja.id), quantity=1)]
        if is_full_menu and sopa is not None:
            lines.append(OrderLineInput(daily_menu_item_id=str(sopa.id), quantity=1))

        try:
            create_order(
                restaurant=customer.restaurant,
                menu=menu,
                payment_method=payment_method,
                customer=customer,
                customer_name=customer.full_name,
                customer_phone=customer.phone,
                customer_address=customer_address,
                transfer_reference=transfer_reference,
                customer_note=customer_note,
                lines=lines,
                is_full_menu=is_full_menu,
            )
        except OrderServiceError as e:
            msg = str(e) or ""
            if "Cupo del menú" in msg or "Cupo" in msg:
                messages.warning(request, "Este menú se agotó.")
            else:
                messages.error(request, "No se pudo crear el pedido. Intenta de nuevo.")
            return redirect("/cliente/")

        messages.success(request, "Pedido realizado con éxito.")
        return redirect("/cliente/")


class CustomerPortalMenuAvailabilityView(View):
    template_name = "credits/_menu_availability.html"

    def get(self, request, menu_id):
        customer_id = request.session.get("customer_id")
        if not customer_id:
            return redirect("/accounts/login/")

        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
        if customer is None:
            clear_customer_session(request)
            return redirect("/accounts/login/")

        now = timezone.now()
        menu = (
            DailyMenu.objects.filter(restaurant=customer.restaurant, id=menu_id, is_visible=True)
            .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
            .first()
        )
        if menu is None:
            # If the menu is no longer active, show "Agotado" to avoid empty UI.
            class _MenuStub:
                id = menu_id
                max_orders = 0

            return render(
                request,
                self.template_name,
                {"menu": _MenuStub(), "remaining": 0, "is_low": False, "is_sold_out": True},
            )

        if menu.max_orders is None:
            return render(
                request,
                self.template_name,
                {"menu": menu, "remaining": None, "is_low": False, "is_sold_out": False},
            )

        active_orders_count = (
            Order.objects.filter(restaurant=customer.restaurant, menu=menu)
            .exclude(status=OrderStatus.CANCELLED)
            .count()
        )
        remaining = max(int(menu.max_orders) - int(active_orders_count), 0)
        is_sold_out = remaining <= 0
        is_low = (not is_sold_out) and remaining <= 5
        return render(
            request,
            self.template_name,
            {"menu": menu, "remaining": remaining, "is_low": is_low, "is_sold_out": is_sold_out},
        )


class CustomerPortalLogoutView(View):
    def post(self, request):
        clear_customer_session(request)
        return redirect("home")

