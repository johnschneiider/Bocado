from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import RestaurantMembership, RestaurantMembershipRole, UserProfile, UserRole
from credits.models import Customer
from credits.services import register_payment
from menus.models import Category, DailyMenu, DailyMenuItem, Item, MenuStatus
from orders.models import Order
from orders.models import PaymentMethod
from orders.services import OrderLineInput, create_order
from restaurants.models import Restaurant, RestaurantLocation


class Command(BaseCommand):
    help = "Seeds demo data for Aladdin (SQLite friendly)."

    def handle(self, *args, **options):
        User = get_user_model()

        restaurant, _ = Restaurant.objects.get_or_create(
            name="Restaurante Demo",
            defaults={"status": "ACTIVE", "phone": "+573000000000", "email": "demo@aladdin.local"},
        )
        RestaurantLocation.objects.get_or_create(
            restaurant=restaurant,
            is_primary=True,
            defaults={"name": "Sede Principal", "city": "Bogotá", "country": "CO"},
        )

        demo_admin, created = User.objects.get_or_create(username="demo_admin")
        if created:
            demo_admin.set_unusable_password()
            demo_admin.is_staff = True
            demo_admin.save()

        profile, profile_created = UserProfile.objects.get_or_create(
            user=demo_admin, defaults={"role": UserRole.RESTAURANT_ADMIN, "phone": "3117451274"}
        )
        # Ensure the phone matches the configured admin phone.
        if not profile_created and profile.phone != "3117451274":
            profile.phone = "3117451274"
            profile.save(update_fields=["phone"])

        RestaurantMembership.objects.get_or_create(
            user=demo_admin,
            restaurant=restaurant,
            defaults={"role": RestaurantMembershipRole.ADMIN, "is_active": True},
        )

        customer, _ = Customer.objects.get_or_create(
            restaurant=restaurant,
            full_name="Cliente Crédito",
            defaults={"phone": "+573111111111", "email": "cliente@demo.local", "address": "Calle 123 # 45-67"},
        )

        category, _ = Category.objects.get_or_create(restaurant=restaurant, name="Almuerzos")
        item1, _ = Item.objects.get_or_create(
            restaurant=restaurant,
            name="Bandeja",
            defaults={"category": category, "base_price": Decimal("18000.00"), "is_active": True},
        )
        item2, _ = Item.objects.get_or_create(
            restaurant=restaurant,
            name="Sopa",
            defaults={"category": category, "base_price": Decimal("5000.00"), "is_active": True},
        )
        # Si existía un ítem "Jugo", desactívalo para este MVP.
        Item.objects.filter(restaurant=restaurant, name__icontains="jugo").update(is_active=False)

        today = timezone.localdate()
        menu, _ = DailyMenu.objects.get_or_create(
            restaurant=restaurant,
            date=today,
            defaults={"status": MenuStatus.OPEN, "max_orders": 50, "is_visible": True},
        )
        # Ensure visibility window (auto-hide next day)
        if menu.visible_until is None or menu.date != today:
            tz = timezone.get_current_timezone()
            next_midnight_naive = datetime.combine(menu.date + timedelta(days=1), time.min)
            menu.visible_until = timezone.make_aware(next_midnight_naive, tz)
            menu.is_visible = True
            menu.save(update_fields=["visible_until", "is_visible"])
        # Make seed idempotent even if orders already exist
        if menu.max_orders is not None and menu.max_orders < 5000:
            menu.max_orders = 5000
            menu.save(update_fields=["max_orders"])
        mi1, _ = DailyMenuItem.objects.get_or_create(
            daily_menu=menu,
            item=item1,
            defaults={"price": Decimal("18000.00")},
        )
        mi2, _ = DailyMenuItem.objects.get_or_create(
            daily_menu=menu,
            item=item2,
            defaults={"price": Decimal("5000.00")},
        )
        # Limpieza: si el menú ya tenía "Jugo Natural", no lo usamos en el portal (se excluye en queries)

        # Create orders only once
        if not Order.objects.filter(restaurant=restaurant, menu=menu).exists():
            # Create 1 cash order (guest)
            create_order(
                restaurant=restaurant,
                menu=menu,
                payment_method=PaymentMethod.CASH,
                customer_name="Cliente Contado",
                customer_phone="+573222222222",
                customer_address="Cra 10 # 20-30",
                lines=[
                    OrderLineInput(daily_menu_item_id=str(mi1.id), quantity=1),
                    OrderLineInput(daily_menu_item_id=str(mi2.id), quantity=1),
                ],
                is_full_menu=True,
            )

            # Create 1 credit order (linked customer) + partial payment
            credit_order = create_order(
                restaurant=restaurant,
                menu=menu,
                payment_method=PaymentMethod.CREDIT,
                customer=customer,
                customer_name=customer.full_name,
                customer_phone=customer.phone,
                customer_address=customer.address,
                lines=[
                    OrderLineInput(daily_menu_item_id=str(mi1.id), quantity=2),
                ],
            )
            debt = credit_order.credit_debt
            register_payment(
                restaurant=restaurant,
                customer=customer,
                debt=debt,
                amount=Decimal("10000.00"),
                method="CASH",
                reference="Caja",
                paid_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Login: phone only (no OTP)")
        self.stdout.write("Admin phone: 3117451274")
        self.stdout.write(f"Restaurant ID: {restaurant.id}")
        self.stdout.write(f"Public menu URL: /m/{restaurant.id}/{date.today().isoformat()}/")

