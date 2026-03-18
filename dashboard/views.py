from __future__ import annotations

from datetime import date
from django.core.cache import cache
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView

from dashboard.services import get_charts, get_kpis
from restaurants.mixins import RestaurantRequiredMixin


class DashboardView(LoginRequiredMixin, RestaurantRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        start = parse_date(self.request.GET.get("start", "")) or date.today()
        end = parse_date(self.request.GET.get("end", "")) or date.today()
        if end < start:
            start, end = end, start

        ctx["restaurant"] = self.restaurant
        ctx["start"] = start
        ctx["end"] = end
        
        # Cache KPIs and charts for 5 minutes
        cache_key_kpis = f"kpi:{self.restaurant.id}:{start}:{end}"
        cache_key_charts = f"charts:{self.restaurant.id}:{start}:{end}"
        
        kpis = cache.get(cache_key_kpis)
        if kpis is None:
            kpis = get_kpis(restaurant=self.restaurant, start_date=start, end_date=end)
            cache.set(cache_key_kpis, kpis, 300)
            
        charts = cache.get(cache_key_charts)
        if charts is None:
            charts = get_charts(restaurant=self.restaurant, start_date=start, end_date=end)
            cache.set(cache_key_charts, charts, 300)
        
        ctx["kpis"] = kpis
        ctx["charts"] = charts
        return ctx
