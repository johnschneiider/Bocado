from django.urls import path

from credits.portal_views import (
    CustomerPortalHomeView,
    CustomerPortalLogoutView,
    CustomerPortalMenuAvailabilityView,
    CustomerPortalOrderCreateView,
    CustomerPortalProfileView,
)

app_name = "customer_portal"

urlpatterns = [
    path("", CustomerPortalHomeView.as_view(), name="home"),
    path("perfil/", CustomerPortalProfileView.as_view(), name="profile"),
    path("order/", CustomerPortalOrderCreateView.as_view(), name="order"),
    path("menu/<uuid:menu_id>/availability/", CustomerPortalMenuAvailabilityView.as_view(), name="menu_availability"),
    path("logout/", CustomerPortalLogoutView.as_view(), name="logout"),
]

