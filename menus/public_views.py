from __future__ import annotations

from datetime import date

from django.http import Http404, JsonResponse
from django.db import models
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from credits.models import Customer
from menus.models import DailyMenu, DailyMenuItem, MenuStatus
from menus.ratelimit import rate_limit
from orders.models import PaymentMethod
from orders.services import OrderLineInput, OrderServiceError, create_order
from restaurants.models import Restaurant


class PublicMenuView(View):
    template_name = "menus/public_menu.html"

    @rate_limit(max_requests=30, window_seconds=60)
    def get(self, request, restaurant_id, menu_date):
        d = parse_date(menu_date)
        if d is None:
            raise Http404("Fecha inválida.")

        restaurant = Restaurant.objects.filter(id=restaurant_id, status="ACTIVE").first()
        if restaurant is None:
            raise Http404("Restaurante no encontrado.")

        now = timezone.now()
        menu = (
            DailyMenu.objects.filter(restaurant=restaurant, date=d, is_visible=True)
            .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
            .first()
        )
        if menu is None:
            raise Http404("Menú no encontrado.")

        items = (
            DailyMenuItem.objects.select_related("item")
            .filter(daily_menu=menu)
            .exclude(item__name__icontains="jugo")
            .order_by("item__name")
        )

        return render(
            request,
            self.template_name,
            {"restaurant": restaurant, "menu": menu, "items": items},
        )


class PublicOrderCreateView(View):
    @rate_limit(max_requests=5, window_seconds=60)
    def post(self, request, restaurant_id, menu_date):
        d = parse_date(menu_date)
        if d is None:
            raise Http404("Fecha inválida.")

        restaurant = Restaurant.objects.filter(id=restaurant_id, status="ACTIVE").first()
        if restaurant is None:
            raise Http404("Restaurante no encontrado.")

        now = timezone.now()
        menu = (
            DailyMenu.objects.filter(restaurant=restaurant, date=d, is_visible=True)
            .filter(models.Q(visible_until__isnull=True) | models.Q(visible_until__gt=now))
            .first()
        )
        if menu is None:
            raise Http404("Menú no encontrado.")

        payment_method = request.POST.get("payment_method") or PaymentMethod.CASH
        customer_name = (request.POST.get("customer_name") or "").strip()
        customer_phone = (request.POST.get("customer_phone") or "").strip()
        customer_address = (request.POST.get("customer_address") or "").strip()
        transfer_reference = (request.POST.get("transfer_reference") or "").strip()

        menu_items = list(
            DailyMenuItem.objects.select_related("item")
            .filter(daily_menu=menu)
            .exclude(item__name__icontains="jugo")
            .order_by("item__name")
        )
        lines: list[OrderLineInput] = []
        for mi in menu_items:
            qty_raw = request.POST.get(f"qty_{mi.id}", "0").strip() or "0"
            try:
                qty = int(qty_raw)
            except ValueError:
                qty = 0
            if qty > 0:
                lines.append(OrderLineInput(daily_menu_item_id=str(mi.id), quantity=qty))

        customer = None
        if payment_method == PaymentMethod.CREDIT:
            if not customer_name or not customer_phone:
                return render(
                    request,
                    "menus/public_order_success.html",
                    {
                        "restaurant": restaurant,
                        "menu": menu,
                        "error": "Para crédito, debes ingresar nombre y teléfono.",
                    },
                    status=400,
                )

            # Avoid UNIQUE(restaurant, full_name) conflicts:
            # Prefer match by phone, fallback to match by name, then create.
            customer = Customer.objects.filter(restaurant=restaurant, phone=customer_phone).first()
            if customer is None:
                customer = Customer.objects.filter(restaurant=restaurant, full_name=customer_name).first()
                if customer is not None and not customer.phone:
                    customer.phone = customer_phone
                    customer.save(update_fields=["phone"])
            if customer is None:
                customer = Customer.objects.create(
                    restaurant=restaurant, full_name=customer_name, phone=customer_phone
                )

        try:
            order = create_order(
                restaurant=restaurant,
                menu=menu,
                payment_method=payment_method,
                customer=customer,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                transfer_reference=transfer_reference,
                lines=lines,
            )
        except OrderServiceError as e:
            return render(
                request,
                "menus/public_order_success.html",
                {"restaurant": restaurant, "menu": menu, "error": str(e)},
                status=400,
            )

        return render(
            request,
            "menus/public_order_success.html",
            {"restaurant": restaurant, "menu": menu, "order": order},
        )

