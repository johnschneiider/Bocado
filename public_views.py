from __future__ import annotations

from datetime import date

from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.services import normalize_phone_digits, get_or_create_customer_user, create_customer_otp
from restaurants.models import Restaurant
from menus.models import DailyMenu, DailyMenuItem
from menus.ratelimit import rate_limit
from orders.models import PaymentMethod
from orders.services import OrderLineInput, OrderServiceError, create_order
from credits.models import Customer


class CustomerLoginView(View):
    """
    Vista de login/registro para clientes.
    Los teléfonos nuevos se registran como clientes, no como admins.
    """
    template_name = "public/customer_login.html"

    def get(self, request):
        # If already logged in as customer, redirect to home
        if request.session.get("customer_id"):
            return redirect('home')
        return render(request, self.template_name)

    def post(self, request):
        phone = (request.POST.get("phone") or "").strip()
        digits = normalize_phone_digits(phone)
        if not digits:
            return render(request, self.template_name, {"error": "Ingresa un teléfono válido"}, status=400)
        
        # Create or get customer user
        user = get_or_create_customer_user(phone_digits=digits)
        if user is None:
            # Phone belongs to an admin account
            return render(request, self.template_name, {"error": "Este teléfono ya está registrado como negocio. Usa la opción de login para negocios."}, status=400)
        
        # Generate OTP code
        code = create_customer_otp(phone=digits)
        
        # Store phone in session for verification step
        request.session['pending_phone'] = digits
        
        # Show the verification page with the code visible
        return render(request, "public/customer_verify.html", {
            "phone": digits,
            "code": code,  # Show code in development (would be SMS in production)
        })


class CustomerVerifyView(View):
    """
    Vista para verificar el código OTP del cliente.
    """
    template_name = "public/customer_verify.html"

    def get(self, request):
        phone = request.session.get('pending_phone')
        if not phone:
            return redirect('customer_login')
        
        # In a real app, we'd generate a new code here
        # For now, we'll show the form to enter the code
        return render(request, self.template_name, {"phone": phone})

    def post(self, request):
        from accounts.services import get_or_create_customer_user, verify_customer_phone_direct
        
        phone = request.session.get('pending_phone')
        if not phone:
            return redirect('customer_login')
        
        code = request.POST.get("code", "").strip()
        if not code:
            return render(request, self.template_name, {"phone": phone, "error": "Ingresa el código de verificación"}, status=400)
        
        # Verify the OTP code
        is_valid = verify_customer_phone_direct(phone=phone, code=code)
        if not is_valid:
            return render(request, self.template_name, {"phone": phone, "error": "Código incorrecto o expirado"}, status=400)
        
        # Get or create customer user
        user = get_or_create_customer_user(phone_digits=phone)
        if user is None:
            return render(request, self.template_name, {"phone": phone, "error": "Error al crear usuario"}, status=400)
        
        # Mark profile as verified
        from accounts.models import UserProfile
        profile = UserProfile.objects.filter(user=user).first()
        if profile:
            profile.is_phone_verified = True
            profile.save(update_fields=["is_phone_verified"])
        
        # Store customer in session
        request.session['customer_id'] = str(user.id)
        request.session['customer_phone'] = phone
        
        # Clear pending phone
        request.session.pop('pending_phone', None)
        
        return redirect('home')


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
        
        # Get all categories
        from restaurants.models import Category
        categories = Category.objects.all().order_by('order')
        
        # Get featured restaurants (top rated, limit 4)
        featured_restaurants = Restaurant.objects.filter(
            status='ACTIVE',
            is_featured=True,
            id__in=today_menu_filter
        ).order_by('-rating')[:4]
        
        # Get all restaurants for grid
        all_restaurants = Restaurant.objects.filter(
            status='ACTIVE',
            id__in=today_menu_filter
        ).order_by('-rating')
        
        # Check if user is logged in as customer
        is_customer_logged_in = bool(request.session.get('customer_id'))
        
        return render(request, self.template_name, {
            'categories': categories,
            'featured_restaurants': featured_restaurants,
            'all_restaurants': all_restaurants,
            'is_customer_logged_in': is_customer_logged_in,
            'city': 'Cali',  # Ciudad por defecto según el peticion.txt
        })


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
        ).prefetch_related('menu_items__item').order_by('title')
        
        # Get active menus (visible and with items)
        active_menus = menus.filter(menu_items__isnull=False).distinct()
        
        return render(request, self.template_name, {
            'restaurant': restaurant,
            'menus': menus,
            'active_menus': active_menus,
            'today': today,
        })


class CategoryListView(View):
    template_name = "public/category_detail.html"
    
    def get(self, request, category_slug):
        from restaurants.models import Category
        from django.shortcuts import get_object_or_404
        
        category = get_object_or_404(Category, slug=category_slug)
        
        # Get all active restaurants with visible menus in this category
        today_menu_filter = DailyMenu.objects.filter(
            is_visible=True
        ).values_list('restaurant_id', flat=True)
        
        restaurants = Restaurant.objects.filter(
            status='ACTIVE',
            category=category,
            id__in=today_menu_filter
        ).order_by('-rating')
        
        return render(request, self.template_name, {
            'category': category,
            'restaurants': restaurants,
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

