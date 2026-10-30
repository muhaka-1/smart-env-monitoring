from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("sensors/", views.SensorListView.as_view(), name="sensors"),
    path("readings/", views.ReadingListCreateView.as_view(), name="readings"),
    path("readings/latest/", views.LatestReadingView.as_view(), name="readings-latest"),
]
