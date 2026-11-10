from django.urls import path

from . import views
from .message_views import MessageListAPI

urlpatterns = [
    path("messages/", MessageListAPI.as_view(), name="messages-api"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("sensors/", views.SensorListView.as_view(), name="sensors"),
    path("readings/", views.ReadingListCreateView.as_view(), name="readings"),
    path("readings/latest/", views.LatestReadingView.as_view(), name="readings-latest"),
    path("reports/history.pdf", views.history_pdf, name="history-pdf"),
]
