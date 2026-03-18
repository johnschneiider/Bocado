from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, View
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.db.models.functions import Coalesce

from credits.forms import CustomerForm, PaymentForm
from credits.models import Customer, Debt, DebtStatus, Payment
from credits.services import get_customer_outstanding_balance, register_payment, settle_customer_debts
from orders.models import Order, OrderStatus
from restaurants.mixins import RestaurantRequiredMixin


class CustomerListView(LoginRequiredMixin, RestaurantRequiredMixin, ListView):
    template_name = "credits/customer_list.html"
    model = Customer
    context_object_name = "customers"

    def get_queryset(self):
        status = (self.request.GET.get("status") or "due").strip().lower()
        diff = ExpressionWrapper(
            F("debts__amount_original") - F("debts__amount_paid"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        outstanding_expr = Coalesce(
            Sum(
                Case(
                    When(debts__status=DebtStatus.OPEN, then=diff),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(Decimal("0.00")),
        )

        qs = (
            Customer.objects.filter(restaurant=self.restaurant, is_active=True)
            .annotate(outstanding=outstanding_expr)
            .order_by("full_name")
        )

        if status == "paid":
            qs = qs.filter(outstanding__lte=Decimal("0.00"))
        elif status == "all":
            pass
        else:  # due (default)
            qs = qs.filter(outstanding__gt=Decimal("0.00"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status = (self.request.GET.get("status") or "due").strip().lower()
        ctx["status_filter"] = status if status in ("due", "paid", "all") else "due"
        return ctx


class CustomerCreateView(LoginRequiredMixin, RestaurantRequiredMixin, CreateView):
    template_name = "credits/customer_form.html"
    form_class = CustomerForm

    def form_valid(self, form):
        form.instance.restaurant = self.restaurant
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("credits:customers_detail", kwargs={"pk": self.object.pk})


class CustomerDetailView(LoginRequiredMixin, RestaurantRequiredMixin, DetailView):
    template_name = "credits/customer_detail.html"
    model = Customer
    context_object_name = "customer"

    def get_queryset(self):
        return Customer.objects.filter(restaurant=self.restaurant)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        customer = self.object
        ctx["outstanding"] = get_customer_outstanding_balance(customer=customer)
        ctx["debts"] = Debt.objects.filter(customer=customer).order_by("-opened_at")
        ctx["payments"] = Payment.objects.filter(customer=customer).order_by("-paid_at")

        form = PaymentForm()
        form.fields["debt"].queryset = Debt.objects.filter(
            customer=customer, status=DebtStatus.OPEN
        ).order_by("-opened_at")
        ctx["payment_form"] = form
        return ctx


class PaymentCreateView(LoginRequiredMixin, RestaurantRequiredMixin, CreateView):
    template_name = "credits/payment_form.html"
    form_class = PaymentForm

    def dispatch(self, request, *args, **kwargs):
        self.customer = Customer.objects.filter(
            restaurant=self.restaurant, id=kwargs.get("pk")
        ).first()
        if self.customer is None:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["debt"].queryset = Debt.objects.filter(
            customer=self.customer, status=DebtStatus.OPEN
        ).order_by("-opened_at")
        return form

    def form_valid(self, form):
        register_payment(
            restaurant=self.restaurant,
            customer=self.customer,
            debt=form.cleaned_data["debt"],
            amount=form.cleaned_data["amount"],
            method=form.cleaned_data["method"],
            reference=form.cleaned_data.get("reference", ""),
            paid_at=form.cleaned_data.get("paid_at"),
        )
        return redirect("credits:customers_detail", pk=self.customer.id)


class CustomerMarkPaidView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, pk):
        customer = Customer.objects.filter(restaurant=self.restaurant, id=pk, is_active=True).first()
        if customer is None:
            raise Http404()

        settle_customer_debts(restaurant=self.restaurant, customer=customer)

        # Re-fetch annotated outstanding for row rendering
        diff = ExpressionWrapper(
            F("debts__amount_original") - F("debts__amount_paid"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        outstanding_expr = Coalesce(
            Sum(
                Case(
                    When(debts__status=DebtStatus.OPEN, then=diff),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            Value(Decimal("0.00")),
        )
        c = (
            Customer.objects.filter(restaurant=self.restaurant, id=pk)
            .annotate(outstanding=outstanding_expr)
            .first()
        )
        return self._render_row(request, customer=c or customer)

    def _render_row(self, request, *, customer: Customer):
        from django.http import HttpResponse
        from django.template.loader import render_to_string

        html = render_to_string("credits/_customer_row.html", {"c": customer}, request=request)
        return HttpResponse(html)


class CustomerOrdersModalView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def get(self, request, pk):
        customer = Customer.objects.filter(restaurant=self.restaurant, id=pk).first()
        if customer is None:
            raise Http404()

        orders = (
            Order.objects.filter(restaurant=self.restaurant, customer=customer)
            .exclude(status=OrderStatus.CANCELLED)
            .select_related("menu")
            .order_by("-created_at")[:200]
        )

        return render(
            request,
            "credits/_customer_orders_modal.html",
            {"customer": customer, "orders": orders},
        )
