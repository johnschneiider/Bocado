from decimal import Decimal

from django.test import TestCase

from menus.models import DailyMenu, DailyMenuItem, Item, MenuStatus
from orders.models import Order, OrderItem, OrderStatus, PaymentMethod
from orders.services import OrderLineInput, OrderServiceError, cancel_order, confirm_order, create_order
from restaurants.models import Restaurant


class OrderModelTest(TestCase):
    def test_create_order_model(self):
        restaurant = Restaurant.objects.create(name="Test Restaurant")
        menu = DailyMenu.objects.create(
            restaurant=restaurant,
            date="2026-03-18",
            status=MenuStatus.OPEN,
        )

        order = Order.objects.create(
            restaurant=restaurant,
            menu=menu,
            payment_method=PaymentMethod.CASH,
            customer_name="John Doe",
            customer_phone="1234567890",
        )

        self.assertIsNotNone(order.id)
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(order.restaurant, restaurant)
        self.assertEqual(order.menu, menu)


class CreateOrderServiceTest(TestCase):
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

    def test_create_order_success(self):
        lines = [OrderLineInput(daily_menu_item_id=str(self.menu_item.id), quantity=2)]
        order = create_order(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
            lines=lines,
            customer_name="John Doe",
        )

        self.assertIsNotNone(order.id)
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(order.total, Decimal("20.00"))
        self.assertEqual(order.items.count(), 1)

    def test_create_order_requires_items(self):
        with self.assertRaises(OrderServiceError) as ctx:
            create_order(
                restaurant=self.restaurant,
                menu=self.menu,
                payment_method=PaymentMethod.CASH,
                lines=[],
            )
        self.assertIn("al menos 1 ítem", str(ctx.exception))

    def test_create_order_requires_open_menu(self):
        self.menu.status = MenuStatus.CLOSED
        self.menu.save()

        lines = [OrderLineInput(daily_menu_item_id=str(self.menu_item.id), quantity=1)]
        with self.assertRaises(OrderServiceError) as ctx:
            create_order(
                restaurant=self.restaurant,
                menu=self.menu,
                payment_method=PaymentMethod.CASH,
                lines=lines,
            )
        self.assertIn("cerrado", str(ctx.exception))


class ConfirmOrderServiceTest(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Test Restaurant")
        self.menu = DailyMenu.objects.create(
            restaurant=self.restaurant,
            date="2026-03-18",
            status=MenuStatus.OPEN,
        )
        self.order = Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
        )

    def test_confirm_order(self):
        order = confirm_order(order=self.order)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertIsNotNone(order.confirmed_at)

    def test_confirm_non_pending_order_returns_unchanged(self):
        self.order.status = OrderStatus.CONFIRMED
        self.order.save()

        order = confirm_order(order=self.order)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)


class CancelOrderServiceTest(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name="Test Restaurant")
        self.menu = DailyMenu.objects.create(
            restaurant=self.restaurant,
            date="2026-03-18",
            status=MenuStatus.OPEN,
        )
        self.order = Order.objects.create(
            restaurant=self.restaurant,
            menu=self.menu,
            payment_method=PaymentMethod.CASH,
        )

    def test_cancel_order(self):
        order = cancel_order(order=self.order)
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertIsNotNone(order.cancelled_at)

    def test_cancel_already_cancelled_returns_unchanged(self):
        self.order.status = OrderStatus.CANCELLED
        self.order.save()

        order = cancel_order(order=self.order)
        self.assertEqual(order.status, OrderStatus.CANCELLED)
