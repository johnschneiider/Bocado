from django.urls import path

from accounts.views import AdminLogoutView, PhoneLoginStartView

app_name = "accounts"

urlpatterns = [
    path("login/", PhoneLoginStartView.as_view(), name="login"),
    path("logout/", AdminLogoutView.as_view(), name="logout"),
]

