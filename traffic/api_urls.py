from django.urls import path

from .views import (
    api_traffic_current,
    api_traffic_history,
    api_traffic_stats,
    api_videos,
    process_video,
    stream_feed,
)

urlpatterns = [
    path("videos/", api_videos, name="api-videos"),
    path("videos/<int:video_id>/process/", process_video, name="api-video-process"),
    path("videos/<int:video_id>/stream/", stream_feed, name="api-video-stream"),
    path("traffic/current/", api_traffic_current, name="api-traffic-current"),
    path("traffic/history/", api_traffic_history, name="api-traffic-history"),
    path("traffic/stats/", api_traffic_stats, name="api-traffic-stats"),
]
