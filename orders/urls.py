from django.urls import path

from orders.views import (
    OrderCancelView,
    OrderConfirmView,
    OrderDetailView,
    OrderListView,
    OrderToggleDeliveredView,
)

app_name = "orders"

urlpatterns = [
    path("", OrderListView.as_view(), name="list"),
    path("<uuid:pk>/", OrderDetailView.as_view(), name="detail"),
    path("<uuid:pk>/confirm/", OrderConfirmView.as_view(), name="confirm"),
    path("<uuid:pk>/cancel/", OrderCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/toggle-delivered/", OrderToggleDeliveredView.as_view(), name="toggle_delivered"),
]

