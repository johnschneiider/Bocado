from datetime import datetime, time, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, View

from orders.models import Order, OrderItem, OrderStatus
from orders.services import cancel_order, confirm_order, set_delivered
from restaurants.mixins import RestaurantRequiredMixin


class OrderListView(LoginRequiredMixin, RestaurantRequiredMixin, ListView):
    template_name = "orders/order_list.html"
    model = Order
    context_object_name = "orders"

    def get_queryset(self):
        selected_date = self._get_selected_date()
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(selected_date, time.min), tz)
        end = start + timedelta(days=1)
        return (
            Order.objects.select_related("menu", "customer")
            .prefetch_related("items")
            .filter(restaurant=self.restaurant)
            .filter(created_at__gte=start, created_at__lt=end)
            .order_by("-created_at")
        )

    def _get_selected_date(self):
        raw = (self.request.GET.get("date") or "").strip()
        d = parse_date(raw) if raw else None
        return d or timezone.localdate()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selected_date = self._get_selected_date()
        ctx["selected_date"] = selected_date
        ctx["today"] = timezone.localdate()
        ctx["prev_date"] = selected_date - timedelta(days=1)
        ctx["next_date"] = selected_date + timedelta(days=1)

        # KPI para el negocio: conteos del día (sin cancelados)
        base_qs = self.object_list.exclude(status=OrderStatus.CANCELLED)
        kpis = base_qs.aggregate(
            orders_count=Count("id"),
            with_soup_count=Count("id", filter=Q(is_full_menu=True)),
            money=Sum("total"),
        )
        total = int(kpis.get("orders_count") or 0)
        with_soup = int(kpis.get("with_soup_count") or 0)
        ctx["kpi_total_bandejas"] = total
        ctx["kpi_bandeja_con_sopa"] = with_soup
        ctx["kpi_solo_bandeja"] = max(total - with_soup, 0)
        ctx["kpi_total_money"] = kpis.get("money") or 0
        return ctx


class OrderDetailView(LoginRequiredMixin, RestaurantRequiredMixin, DetailView):
    template_name = "orders/order_detail.html"
    model = Order
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.filter(restaurant=self.restaurant).select_related("menu", "customer")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = (
            OrderItem.objects.select_related("daily_menu_item", "daily_menu_item__item")
            .filter(order=self.object)
            .order_by("created_at")
        )
        return ctx


class OrderConfirmView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, pk):
        order = Order.objects.filter(restaurant=self.restaurant, id=pk).first()
        if order is None:
            raise Http404()
        confirm_order(order=order)
        return redirect("orders:detail", pk=pk)


class OrderCancelView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, pk):
        order = Order.objects.filter(restaurant=self.restaurant, id=pk).first()
        if order is None:
            raise Http404()
        cancel_order(order=order)
        return redirect("orders:detail", pk=pk)


class OrderToggleDeliveredView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, pk):
        order = Order.objects.filter(restaurant=self.restaurant, id=pk).first()
        if order is None:
            raise Http404()

        delivered = request.POST.get("delivered") in ("1", "true", "True", "on", "yes")
        set_delivered(order=order, delivered=delivered)
        return self._render_toggle(request, order=order)

    def _render_toggle(self, request, *, order: Order):
        from django.http import HttpResponse
        from django.template.loader import render_to_string

        html = render_to_string("orders/_delivered_toggle.html", {"o": order}, request=request)
        return HttpResponse(html)
