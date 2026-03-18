from datetime import date
from decimal import Decimal

from django.test import TestCase

from credits.models import Customer, Debt, DebtStatus
from dashboard.services import DashboardKpis, get_charts, get_kpis
from menus.models import DailyMenu, DailyMenuItem, Item, MenuStatus
from orders.models import Order, OrderStatus, PaymentMethod
from restaurants.models import Restaurant


class GetKpisServiceTest(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Test Restaurant")
        self.menu = DailyMenu.objects.create(
            restaurant=self.restaurant,
            date="2026-03-18",
            status=MenuStatus.OPEN,
        )
        self.item = Item.objects.create(
            restaurant=self.restaurant,
            name="Test Item",
            base_price=Decimal("10.00"),
        )
        self.menu_item = DailyMenuItem.objects.create(
            daily_menu=self.menu,
            item=self.item,
            price=Decimal("10.00"),
        )
        self.customer = Customer.objects.create(
            restaurant=self.restaurant,
            full_name="Test Customer",
        )

    def test_get_kpis_empty(self):
        kpis = get_kpis(
            restaurant=self.restaurant,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertIsInstance(kpis, DashboardKpis)
        self.assertEqual(kpis.total_orders, 0)
        self.assertEqual(kpis.total_sold, Decimal("0.00"))

    def test_get_kpis_with_orders(self):
        Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
            total=Decimal("100.00"),
        )
        Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CREDIT,
            total=Decimal("50.00"),
        )

        kpis = get_kpis(
            restaurant=self.restaurant,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertEqual(kpis.total_orders, 2)
        self.assertEqual(kpis.total_sold, Decimal("150.00"))
        self.assertEqual(kpis.total_credit_sales, Decimal("50.00"))

    def test_get_kpis_excludes_cancelled_orders(self):
        Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
            total=Decimal("100.00"),
        )
        Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
            total=Decimal("50.00"),
            status=OrderStatus.CANCELLED,
        )

        kpis = get_kpis(
            restaurant=self.restaurant,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertEqual(kpis.total_orders, 1)
        self.assertEqual(kpis.total_sold, Decimal("100.00"))


class GetChartsServiceTest(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Test Restaurant")
        self.menu = DailyMenu.objects.create(
            restaurant=self.restaurant,
            date="2026-03-18",
            status=MenuStatus.OPEN,
        )
        self.item = Item.objects.create(
            restaurant=self.restaurant,
            name="Test Item",
            base_price=Decimal("10.00"),
        )
        self.menu_item = DailyMenuItem.objects.create(
            daily_menu=self.menu,
            item=self.item,
            price=Decimal("10.00"),
        )

    def test_get_charts_empty(self):
        charts = get_charts(
            restaurant=self.restaurant,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertIn("sales_daily_30", charts)
        self.assertIn("sales_monthly_12", charts)
        self.assertIn("sales_weekday", charts)
        self.assertIn("top_menus", charts)
        self.assertIn("top_customers", charts)

    def test_get_charts_structure(self):
        charts = get_charts(
            restaurant=self.restaurant,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertIn("labels", charts["sales_daily_30"])
        self.assertIn("values", charts["sales_daily_30"])
        self.assertIn("labels", charts["sales_weekday"])
        self.assertIn("values", charts["sales_weekday"])
