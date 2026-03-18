from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from django.db import transaction
from django.utils import timezone

from credits.models import Customer, Debt, DebtStatus
from menus.models import DailyMenu, DailyMenuItem, MenuStatus
from orders.models import Order, OrderItem, OrderStatus, PaymentMethod
from restaurants.models import Restaurant


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch.isdigit())


@dataclass(frozen=True)
class OrderLineInput:
    daily_menu_item_id: str
    quantity: int
    notes: str = ""


class OrderServiceError(Exception):
    pass


@transaction.atomic
def create_order(
    *,
    restaurant: Restaurant,
    menu: DailyMenu,
    payment_method: str,
    lines: Sequence[OrderLineInput],
    customer: Customer | None = None,
    customer_name: str = "",
    customer_phone: str = "",
    customer_address: str = "",
    transfer_reference: str = "",
    customer_note: str = "",
    is_full_menu: bool = False,
) -> Order:
    """
    Core business rule:
    - validates menu ownership/status
    - enforces menu max_orders (cupo)
    - snapshots prices/items into OrderItem
    - crea una deuda (por cliente) para control de cobro
    """

    if menu.restaurant_id != restaurant.id:
        raise OrderServiceError("El menú no pertenece a este restaurante.")

    if menu.status != MenuStatus.OPEN:
        raise OrderServiceError("Este menú está cerrado.")

    if not lines:
        raise OrderServiceError("El pedido debe tener al menos 1 ítem.")

    if menu.max_orders is not None:
        active_orders_count = (
            Order.objects.filter(restaurant=restaurant, menu=menu)
            .exclude(status=OrderStatus.CANCELLED)
            .count()
        )
        if active_orders_count >= menu.max_orders:
            raise OrderServiceError("Cupo del menú alcanzado. No se aceptan más pedidos.")

    if payment_method == PaymentMethod.CREDIT and customer is None:
        raise OrderServiceError("Para crédito, debes seleccionar un cliente.")

    # Load and validate DailyMenuItems in one query.
    requested_ids = [str(l.daily_menu_item_id) for l in lines]
    menu_items = list(
        DailyMenuItem.objects.select_related("item")
        .filter(daily_menu=menu, id__in=requested_ids)
    )
    menu_items_by_id = {str(mi.id): mi for mi in menu_items}

    for line in lines:
        if line.quantity <= 0:
            raise OrderServiceError("La cantidad debe ser mayor a 0.")
        mi = menu_items_by_id.get(str(line.daily_menu_item_id))
        if mi is None:
            raise OrderServiceError("Uno o más ítems no pertenecen al menú.")
        # Disponibilidad por ítem removida (se controla a nivel de menú/visibilidad)

    order = Order.objects.create(
        restaurant=restaurant,
        menu=menu,
        customer=customer,
        customer_name=customer_name.strip(),
        customer_phone=normalize_phone(customer_phone),
        customer_address=customer_address.strip(),
        status=OrderStatus.PENDING,
        payment_method=payment_method,
        transfer_reference=transfer_reference.strip(),
        customer_note=(customer_note or "").strip()[:255],
        is_full_menu=bool(is_full_menu),
        subtotal=Decimal("0.00"),
        total=Decimal("0.00"),
    )

    subtotal = Decimal("0.00")
    order_items: list[OrderItem] = []
    for line in lines:
        mi = menu_items_by_id[str(line.daily_menu_item_id)]
        unit_price = mi.price
        line_total = (unit_price * int(line.quantity)).quantize(Decimal("0.01"))
        subtotal += line_total
        order_items.append(
            OrderItem(
                order=order,
                daily_menu_item=mi,
                item_name=mi.item.name,
                unit_price=unit_price,
                quantity=int(line.quantity),
                line_total=line_total,
                notes=line.notes.strip(),
            )
        )

    OrderItem.objects.bulk_create(order_items)

    order.subtotal = subtotal.quantize(Decimal("0.01"))
    order.total = order.subtotal
    order.save(update_fields=["subtotal", "total"])

    # Para el portal de clientes queremos que TODO pedido quede "en deuda" hasta que el negocio lo marque pagado.
    # Por eso, si hay cliente asociado, creamos la deuda independientemente del método de pago.
    if customer is not None:
        Debt.objects.create(
            restaurant=restaurant,
            customer=customer,
            order=order,
            amount_original=order.total,
            amount_paid=Decimal("0.00"),
            status=DebtStatus.OPEN,
        )

    return order


@transaction.atomic
def confirm_order(*, order: Order) -> Order:
    if order.status != OrderStatus.PENDING:
        return order
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at"])
    return order


@transaction.atomic
def cancel_order(*, order: Order) -> Order:
    if order.status == OrderStatus.CANCELLED:
        return order
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_at"])
    return order


@transaction.atomic
def set_delivered(*, order: Order, delivered: bool) -> Order:
    """
    Permite marcar/desmarcar como entregado.
    - delivered=True  -> status=DELIVERED, delivered_at=now
    - delivered=False -> vuelve a CONFIRMED si estaba confirmado, si no a PENDING
    """
    delivered = bool(delivered)
    if order.status == OrderStatus.CANCELLED:
        return order

    if delivered:
        if order.status == OrderStatus.DELIVERED:
            return order
        order.status = OrderStatus.DELIVERED
        order.delivered_at = timezone.now()
        order.save(update_fields=["status", "delivered_at"])
        return order

    # Undeliver
    if order.status != OrderStatus.DELIVERED:
        return order
    order.delivered_at = None
    order.status = OrderStatus.CONFIRMED if order.confirmed_at else OrderStatus.PENDING
    order.save(update_fields=["status", "delivered_at"])
    return order

