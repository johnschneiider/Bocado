from django.urls import path

from menus.public_views import PublicMenuView, PublicOrderCreateView

app_name = "public_menus"

urlpatterns = [
    path("<uuid:restaurant_id>/<str:menu_date>/", PublicMenuView.as_view(), name="menu"),
    path("<uuid:restaurant_id>/<str:menu_date>/order/", PublicOrderCreateView.as_view(), name="order"),
]

