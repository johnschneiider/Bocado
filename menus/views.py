from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from menus.forms import DailyMenuForm, DailyMenuItemForm
from menus.models import DailyMenu, DailyMenuItem, Item, MenuStatus
from menus.services import set_menu_visibility
from restaurants.mixins import RestaurantRequiredMixin


class DailyMenuListView(LoginRequiredMixin, RestaurantRequiredMixin, ListView):
    template_name = "menus/daily_menu_list.html"
    model = DailyMenu
    context_object_name = "menus"

    def get_queryset(self):
        return DailyMenu.objects.filter(restaurant=self.restaurant).order_by("-date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["now"] = timezone.now()
        return ctx


class DailyMenuCreateView(LoginRequiredMixin, RestaurantRequiredMixin, CreateView):
    template_name = "menus/daily_menu_form.html"
    form_class = DailyMenuForm

    def dispatch(self, request, *args, **kwargs):
        """
        Regla de negocio: 1 menú por día por restaurante (UniqueConstraint).
        Si ya existe el de hoy, en vez de permitir "crear" otro, enviamos a editar.
        """
        today = timezone.localdate()
        existing = DailyMenu.objects.filter(restaurant=self.restaurant, date=today).only("id").first()
        if existing is not None and request.method.upper() == "GET":
            messages.info(request, "Ya existe un menú para hoy. Puedes editarlo aquí.")
            return redirect("menus:edit", pk=existing.id)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.restaurant = self.restaurant
        form.instance.date = timezone.localdate()
        form.instance.status = MenuStatus.OPEN
        # Visible por defecto hasta el inicio del siguiente día (00:00 local)
        tz = timezone.get_current_timezone()
        next_midnight_naive = datetime.combine(form.instance.date + timedelta(days=1), time.min)
        form.instance.visible_until = timezone.make_aware(next_midnight_naive, tz)
        # Prevent 500 on duplicate (restaurant, date)
        existing = DailyMenu.objects.filter(
            restaurant=self.restaurant, date=form.instance.date
        ).only("id").first()
        if existing is not None:
            messages.warning(
                self.request,
                "Ya existe un menú para hoy. No se puede crear otro; edita el existente.",
            )
            return redirect("menus:edit", pk=existing.id)

        try:
            return super().form_valid(form)
        except IntegrityError:
            # Concurrencia: si alguien lo creó justo ahora, redirigir a editar.
            existing = DailyMenu.objects.filter(
                restaurant=self.restaurant, date=form.instance.date
            ).only("id").first()
            if existing is not None:
                messages.warning(
                    self.request,
                    "Este menú ya fue creado para hoy. Te llevamos a editarlo.",
                )
                return redirect("menus:edit", pk=existing.id)
            raise

    def get_success_url(self):
        return reverse("menus:detail", kwargs={"pk": self.object.pk})


class DailyMenuDetailView(LoginRequiredMixin, RestaurantRequiredMixin, DetailView):
    template_name = "menus/daily_menu_detail.html"
    model = DailyMenu
    context_object_name = "menu"

    def get_queryset(self):
        return DailyMenu.objects.filter(restaurant=self.restaurant)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Read-only preview: provide items for visualization only
        ctx["menu_items"] = (
            DailyMenuItem.objects.select_related("item")
            .filter(daily_menu=self.object)
            .exclude(item__name__icontains="jugo")
            .order_by("item__name")
        )
        return ctx


class DailyMenuUpdateView(LoginRequiredMixin, RestaurantRequiredMixin, UpdateView):
    template_name = "menus/daily_menu_form.html"
    model = DailyMenu
    form_class = DailyMenuForm

    def get_queryset(self):
        return DailyMenu.objects.filter(restaurant=self.restaurant)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        menu = self.object
        ctx["menu_items"] = (
            DailyMenuItem.objects.select_related("item")
            .filter(daily_menu=menu)
            .exclude(item__name__icontains="jugo")
            .order_by("item__name")
        )
        form = DailyMenuItemForm()
        form.fields["item"].queryset = Item.objects.filter(
            restaurant=self.restaurant, is_active=True
        ).exclude(name__icontains="jugo").order_by("name")
        ctx["add_item_form"] = form
        return ctx

    def form_valid(self, form):
        # Do not change date/status automatically on update.
        form.instance.restaurant = self.restaurant
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("menus:detail", kwargs={"pk": self.object.pk})


class DailyMenuDeleteView(LoginRequiredMixin, RestaurantRequiredMixin, DeleteView):
    template_name = "menus/daily_menu_confirm_delete.html"
    model = DailyMenu

    def get_queryset(self):
        return DailyMenu.objects.filter(restaurant=self.restaurant)

    def get_success_url(self):
        return reverse("menus:list")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "No se puede eliminar este menú porque ya tiene pedidos asociados.",
            )
            return redirect("menus:detail", pk=self.object.pk)


class DailyMenuItemCreateView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, menu_id):
        menu = DailyMenu.objects.filter(restaurant=self.restaurant, id=menu_id).first()
        if menu is None:
            raise Http404("Menú no encontrado.")

        form = DailyMenuItemForm(request.POST)
        form.fields["item"].queryset = Item.objects.filter(
            restaurant=self.restaurant, is_active=True
        ).exclude(
            name__icontains="jugo"
        )
        if form.is_valid():
            obj = form.save(commit=False)
            obj.daily_menu = menu
            obj.save()
        return redirect("menus:edit", pk=menu.id)


class DailyMenuToggleVisibilityView(LoginRequiredMixin, RestaurantRequiredMixin, View):
    def post(self, request, pk):
        menu = DailyMenu.objects.filter(restaurant=self.restaurant, id=pk).first()
        if menu is None:
            raise Http404("Menú no encontrado.")

        enabled = request.POST.get("enabled") in ("1", "true", "True", "on", "yes")
        set_menu_visibility(menu=menu, enabled=enabled)
        # Return partial for HTMX
        return self._render_row(request, menu=menu)

    def _render_row(self, request, *, menu: DailyMenu):
        from django.template.loader import render_to_string
        from django.http import HttpResponse

        html = render_to_string(
            "menus/_daily_menu_row.html",
            {"m": menu, "now": timezone.now()},
            request=request,
        )
        return HttpResponse(html)
