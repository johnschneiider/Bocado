from django.urls import path

from menus.views import (
    DailyMenuCreateView,
    DailyMenuDeleteView,
    DailyMenuDetailView,
    DailyMenuItemCreateView,
    DailyMenuListView,
    DailyMenuToggleVisibilityView,
    DailyMenuUpdateView,
)

app_name = "menus"

urlpatterns = [
    path("", DailyMenuListView.as_view(), name="list"),
    path("new/", DailyMenuCreateView.as_view(), name="new"),
    path("<uuid:pk>/", DailyMenuDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", DailyMenuUpdateView.as_view(), name="edit"),
    path("<uuid:pk>/delete/", DailyMenuDeleteView.as_view(), name="delete"),
    path("<uuid:menu_id>/items/add/", DailyMenuItemCreateView.as_view(), name="add_item"),
    path("<uuid:pk>/toggle-visibility/", DailyMenuToggleVisibilityView.as_view(), name="toggle_visibility"),
]

