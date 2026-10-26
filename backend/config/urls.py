from django.contrib import admin
from django.urls import include, path

from monitoring.views import DashboardView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("monitoring.urls")),
    path("", DashboardView.as_view(), name="dashboard"),
]
