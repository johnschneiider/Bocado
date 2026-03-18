from decimal import Decimal

from django.test import TestCase

from menus.models import DailyMenu, DailyMenuItem, Item, MenuStatus
from restaurants.models import Restaurant


class DailyMenuModelTest(TestCase):
    def test_create_daily_menu(self):
        restaurant = Restaurant.objects.create(name="Test Restaurant")
        menu = DailyMenu.objects.create(
            restaurant=restaurant,
            date="2026-03-18",
            title="Menu del Dia",
            status=MenuStatus.OPEN,
        )

        self.assertIsNotNone(menu.id)
        self.assertEqual(menu.status, MenuStatus.OPEN)
        self.assertEqual(menu.restaurant, restaurant)

    def test_daily_menu_with_max_orders(self):
        restaurant = Restaurant.objects.create(name="Test Restaurant")
        menu = DailyMenu.objects.create(
            restaurant=restaurant,
            date="2026-03-18",
            max_orders=10,
        )

        self.assertEqual(menu.max_orders, 10)


class DailyMenuItemModelTest(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Test Restaurant")
        self.menu = DailyMenu.objects.create(
            restaurant=self.restaurant,
            date="2026-03-18",
        )
        self.item = Item.objects.create(
            restaurant=self.restaurant,
            name="Test Item",
            base_price=Decimal("10.00"),
        )

    def test_create_daily_menu_item(self):
        menu_item = DailyMenuItem.objects.create(
            daily_menu=self.menu,
            item=self.item,
            price=Decimal("15.00"),
        )

        self.assertIsNotNone(menu_item.id)
        self.assertEqual(menu_item.price, Decimal("15.00"))
        self.assertEqual(menu_item.daily_menu, self.menu)
        self.assertEqual(menu_item.item, self.item)

    def test_menu_item_inherits_item_name(self):
        menu_item = DailyMenuItem.objects.create(
            daily_menu=self.menu,
            item=self.item,
            price=Decimal("12.00"),
        )

        self.assertEqual(str(menu_item), f"{self.menu.date.isoformat()} - Test Item")
