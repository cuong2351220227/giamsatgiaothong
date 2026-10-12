from django.contrib import admin
from django.urls import include, path

from traffic.views import dashboard

urlpatterns = [
    path("", dashboard, name="home"),
    path("admin/", admin.site.urls),
    path("traffic/", include("traffic.urls")),
    path("api/", include("traffic.api_urls")),
]
