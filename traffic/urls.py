from django.urls import path

from .views import current, dashboard, history, healthcheck, process_video, stats, videos

app_name = "traffic"

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("health/", healthcheck, name="health"),
    path("videos/", videos, name="videos"),
    path("current/", current, name="current"),
    path("history/", history, name="history"),
    path("stats/", stats, name="stats"),
    path("process/", process_video, name="process"),
]
