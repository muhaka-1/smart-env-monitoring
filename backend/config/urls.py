from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from monitoring import accounts
from monitoring.message_views import MessageListView
from monitoring.error_report_views import error_report
from monitoring.views import DashboardView

urlpatterns = [
    path("reports/errors/", error_report, name="error-report"),
    path("messages/", MessageListView.as_view(), name="message-list"),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include(accounts.urlpatterns)),
    path("api/", include("monitoring.urls")),
    path("", DashboardView.as_view(), name="dashboard"),
]
