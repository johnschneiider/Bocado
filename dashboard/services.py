from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce

from credits.models import Debt, DebtStatus
from orders.models import Order, OrderStatus, PaymentMethod
from restaurants.models import Restaurant


@dataclass(frozen=True)
class DashboardKpis:
    total_orders: int
    total_sold: Decimal
    total_credit_sales: Decimal
    debt_pending: Decimal


def get_kpis(*, restaurant: Restaurant, start_date: date, end_date: date) -> DashboardKpis:
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    orders_qs = Order.objects.filter(
        restaurant=restaurant, created_at__gte=start_dt, created_at__lte=end_dt
    ).exclude(status=OrderStatus.CANCELLED)

    total_orders = orders_qs.count()
    total_sold = orders_qs.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    total_credit_sales = (
        orders_qs.filter(payment_method=PaymentMethod.CREDIT).aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )

    debt_pending = (
        Debt.objects.filter(restaurant=restaurant, status=DebtStatus.OPEN)
        .aggregate(total=Sum(F("amount_original") - F("amount_paid")))["total"]
        or Decimal("0.00")
    )

    return DashboardKpis(
        total_orders=total_orders,
        total_sold=total_sold.quantize(Decimal("0.01")),
        total_credit_sales=total_credit_sales.quantize(Decimal("0.01")),
        debt_pending=debt_pending.quantize(Decimal("0.01")),
    )


SPANISH_MONTHS_ABBR = [
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]


def _money_int(d: Decimal | None) -> int:
    if not d:
        return 0
    try:
        return int(d.quantize(Decimal("1")))
    except Exception:
        return int(d)


def get_charts(*, restaurant: Restaurant, start_date: date, end_date: date) -> dict:
    """
    Datos para gráficos (sin depender de librerías JS):
    - ventas últimos 30 días (diario)
    - ventas últimos 12 meses (mensual)
    - ventas por día de la semana (torta)
    - top menús vendidos (barras)
    - top clientes (barras)
    """
    # Base queryset: solo ventas válidas en el rango seleccionado
    orders = (
        Order.objects.filter(restaurant=restaurant, created_at__date__gte=start_date, created_at__date__lte=end_date)
        .exclude(status=OrderStatus.CANCELLED)
        .select_related("menu", "customer")
    )

    # 1) Ventas por día (rango)
    day_labels: list[str] = []
    day_values: list[int] = []
    daily_map: dict[date, int] = {}
    daily_rows = (
        orders.values("created_at__date").annotate(money=Sum("total"))
    )
    for r in daily_rows:
        d = r["created_at__date"]
        daily_map[d] = _money_int(r["money"])
    span_days = max((end_date - start_date).days, 0) + 1
    for i in range(span_days):
        d = start_date + timedelta(days=i)
        day_labels.append(d.strftime("%d-%m"))
        day_values.append(int(daily_map.get(d, 0)))

    # 1b) Ventas por mes (rango)
    month_labels: list[str] = []
    month_values: list[int] = []
    first_month = date(start_date.year, start_date.month, 1)
    last_month = date(end_date.year, end_date.month, 1)
    months: list[date] = []
    cur = first_month
    while cur <= last_month:
        months.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    month_map: dict[tuple[int, int], int] = {}
    month_rows = (
        orders.values("created_at__year", "created_at__month").annotate(money=Sum("total"))
    )
    for r in month_rows:
        key = (int(r["created_at__year"]), int(r["created_at__month"]))
        month_map[key] = _money_int(r["money"])
    for m in months:
        key = (m.year, m.month)
        month_labels.append(f"{SPANISH_MONTHS_ABBR[m.month-1]}-{str(m.year)[2:]}")
        month_values.append(int(month_map.get(key, 0)))

    # 2) Ventas por día de la semana (rango)
    weekday_labels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    weekday_values = [0, 0, 0, 0, 0, 0, 0]
    for i in range(span_days):
        d = start_date + timedelta(days=i)
        wd = d.weekday()  # Mon=0
        weekday_values[wd] += int(daily_map.get(d, 0))

    # 3) Top menús más vendidos (por cantidad de pedidos)
    top_menus_rows = (
        orders.values("menu_id", "menu__title", "menu__date")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:8]
    )
    top_menu_labels: list[str] = []
    top_menu_values: list[int] = []
    for r in top_menus_rows:
        title = r.get("menu__title") or "Menú"
        d = r.get("menu__date")
        label = f"{title} {d.strftime('%d-%m')}" if d else title
        top_menu_labels.append(label)
        top_menu_values.append(int(r["cnt"]))

    # 4) Top clientes que más compran (por total gastado)
    top_customer_rows = (
        orders.annotate(customer_label=Coalesce("customer__full_name", "customer_name"))
        .exclude(customer_label="")
        .values("customer_label")
        .annotate(money=Sum("total"))
        .order_by("-money")[:5]
    )
    top_customer_labels: list[str] = []
    top_customer_values: list[int] = []
    for r in top_customer_rows:
        top_customer_labels.append(str(r["customer_label"]))
        top_customer_values.append(_money_int(r["money"]))

    return {
        "sales_daily_30": {"labels": day_labels, "values": day_values},
        "sales_monthly_12": {"labels": month_labels, "values": month_values},
        "sales_weekday": {"labels": weekday_labels, "values": weekday_values},
        "top_menus": {"labels": top_menu_labels, "values": top_menu_values},
        "top_customers": {"labels": top_customer_labels, "values": top_customer_values},
    }

