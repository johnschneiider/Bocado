from django.urls import path

from credits.views import (
    CustomerCreateView,
    CustomerDetailView,
    CustomerListView,
    CustomerMarkPaidView,
    CustomerOrdersModalView,
    PaymentCreateView,
)

app_name = "credits"

urlpatterns = [
    path("customers/", CustomerListView.as_view(), name="customers_list"),
    path("customers/new/", CustomerCreateView.as_view(), name="customers_new"),
    path("customers/<uuid:pk>/", CustomerDetailView.as_view(), name="customers_detail"),
    path("customers/<uuid:pk>/mark-paid/", CustomerMarkPaidView.as_view(), name="customers_mark_paid"),
    path("customers/<uuid:pk>/orders-modal/", CustomerOrdersModalView.as_view(), name="customers_orders_modal"),
    path("customers/<uuid:pk>/payments/new/", PaymentCreateView.as_view(), name="payments_new"),
]

