from __future__ import annotations

from datetime import date

from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.services import normalize_phone_digits
from restaurants.models import Restaurant
from menus.models import DailyMenu, DailyMenuItem
from menus.ratelimit import rate_limit
from orders.models import PaymentMethod
from orders.services import OrderLineInput, OrderServiceError, create_order
from credits.models import Customer


class RootPreAuthView(View):
    template_name = "public/home.html"

    def get(self, request):
        return redirect('home')


class PublicHomeView(View):
    template_name = "public/home.html"

    def get(self, request):
        # Get all active restaurants with visible menus
        today_menu_filter = DailyMenu.objects.filter(
            is_visible=True
        ).values_list('restaurant_id', flat=True)
        
        restaurants = Restaurant.objects.filter(
            status='ACTIVE',
            id__in=today_menu_filter
        ).annotate(
            menu_count=Count('menus', filter=Q(menus__is_visible=True))
        )
        
        return render(request, self.template_name, {'restaurants': restaurants})


class PublicRestaurantDetailView(View):
    template_name = "public/restaurant_detail.html"

    def get(self, request, restaurant_id):
        from django.shortcuts import get_object_or_404
        
        restaurant = get_object_or_404(Restaurant, id=restaurant_id, status='ACTIVE')
        
        # Get today's visible menus
        today = timezone.now().date()
        menus = DailyMenu.objects.filter(
            restaurant=restaurant,
            date=today,
            is_visible=True
        ).prefetch_related('items__item').order_by('title')
        
        # Get active menus (visible and with items)
        active_menus = menus.filter(items__isnull=False).distinct()
        
        return render(request, self.template_name, {
            'restaurant': restaurant,
            'menus': menus,
            'active_menus': active_menus,
            'today': today,
        })


class PublicRestaurantOrderView(View):
    template_name = "public/restaurant_order.html"

    @rate_limit(max_requests=5, window_seconds=60)
    def get(self, request, restaurant_id):
        restaurant = Restaurant.objects.filter(id=restaurant_id, status="ACTIVE").first()
        if restaurant is None:
            raise Http404("Restaurante no encontrado.")
        
        # Get today's menu
        today = timezone.now().date()
        menu = DailyMenu.objects.filter(
            restaurant=restaurant,
            date=today,
            is_visible=True
        ).first()
        
        if menu is None:
            raise Http404("No hay menú disponible para hoy.")
        
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

    @rate_limit(max_requests=5, window_seconds=60)
    def post(self, request, restaurant_id):
        restaurant = Restaurant.objects.filter(id=restaurant_id, status="ACTIVE").first()
        if restaurant is None:
            raise Http404("Restaurante no encontrado.")

        now = timezone.now()
        today = now.date()
        menu = (
            DailyMenu.objects.filter(restaurant=restaurant, date=today, is_visible=True)
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
                    "public/order_success.html",
                    {
                        "restaurant": restaurant,
                        "menu": menu,
                        "error": "Para crédito, debes ingresar nombre y teléfono.",
                    },
                    status=400,
                )

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
                "public/order_success.html",
                {"restaurant": restaurant, "menu": menu, "error": str(e)},
                status=400,
            )

        return render(
            request,
            "public/order_success.html",
            {"restaurant": restaurant, "menu": menu, "order": order},
        )

