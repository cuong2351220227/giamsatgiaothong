from django.db import models


class Video(models.Model):
    title = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    duration = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class VehicleDetection(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="detections")
    vehicle_type = models.CharField(max_length=30)
    confidence = models.FloatField(default=0.0)
    x1 = models.FloatField(default=0)
    y1 = models.FloatField(default=0)
    x2 = models.FloatField(default=0)
    y2 = models.FloatField(default=0)
    detected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle_type} @ {self.detected_at}"


class TrafficSnapshot(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="snapshots")
    total_vehicles = models.IntegerField(default=0)
    car_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    density = models.FloatField(default=0.0)
    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Snapshot {self.id} - {self.total_vehicles} vehicles"


class TrafficStatus(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=20, choices=[
        ("Bình thường", "Bình thường"),
        ("Đông", "Đông"),
        ("Ùn tắc", "Ùn tắc"),
    ])
    status_label = models.CharField(max_length=50)
    vehicle_count = models.IntegerField(default=0)
    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.video.title} - {self.status}"
