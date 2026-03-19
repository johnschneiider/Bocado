"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from public_views import (
    RootPreAuthView, 
    PublicHomeView, 
    PublicRestaurantDetailView, 
    PublicRestaurantOrderView,
    CustomerLoginView,
    CustomerVerifyView,
    CategoryListView,
)

urlpatterns = [
    # Vistas públicas tipo Didifood
    path("", PublicHomeView.as_view(), name="home"),
    path("r/<uuid:restaurant_id>/", PublicRestaurantDetailView.as_view(), name="public_restaurant_detail"),
    path("r/<uuid:restaurant_id>/order/", PublicRestaurantOrderView.as_view(), name="public_restaurant_order"),
    
    # Vistas de login cliente
    path("login/", CustomerLoginView.as_view(), name="customer_login"),
    path("verify/", CustomerVerifyView.as_view(), name="customer_verify"),
    
    # Vistas de categorías
    path("categorias/<slug:category_slug>/", CategoryListView.as_view(), name="category_detail"),
    
    path("cliente/logout/", include("credits.portal_urls")),
    
    # Vistas de negocio (admin)
    path("dashboard/", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("menus/", include("menus.urls")),
    
    # Vistas públicas existentes (mantener compatibilidad)
    path("m/", include("menus.public_urls")),
    
    path("orders/", include("orders.urls")),
    path("credits/", include("credits.urls")),
    path("cliente/", include("credits.portal_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
