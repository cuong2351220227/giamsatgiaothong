from django.contrib import admin

from .models import TrafficSnapshot, TrafficStatus, VehicleDetection, Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "file_path", "duration", "created_at")
    search_fields = ("title", "file_path")


@admin.register(VehicleDetection)
class VehicleDetectionAdmin(admin.ModelAdmin):
    list_display = ("video", "vehicle_type", "confidence", "detected_at")
    list_filter = ("vehicle_type",)


@admin.register(TrafficSnapshot)
class TrafficSnapshotAdmin(admin.ModelAdmin):
    list_display = ("video", "total_vehicles", "density", "captured_at")


@admin.register(TrafficStatus)
class TrafficStatusAdmin(admin.ModelAdmin):
    list_display = ("video", "status", "vehicle_count", "captured_at")
    list_filter = ("status",)
