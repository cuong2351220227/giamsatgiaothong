from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from traffic.views import dashboard, media_file

urlpatterns = [
    path("", dashboard, name="home"),
    path("media/<path:path>", media_file, name="media-file"),
    path("admin/", admin.site.urls),
    path("traffic/", include("traffic.urls")),
    path("api/", include("traffic.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
