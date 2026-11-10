from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import cv2
from django.conf import settings
from django.db import transaction

from scripts.tracker_counter import VehicleTrackerCounter

from ..models import TrafficSnapshot, TrafficStatus, Video
from .classifier import KMeansTrafficClassifier


class LiveVehicleStream:
    """Keep one camera capture and one trained YOLO tracker alive per MJPEG feed."""

    def __init__(self, source: str, video: Video):
        project_root = Path(__file__).resolve().parents[2]
        weights = project_root / "final_weights" / "vehicle_detector_best.pt"
        if not weights.is_file():
            raise OSError(f"Không tìm thấy model YOLO đã huấn luyện: {weights}")

        person_weights = project_root / "weights" / "yolo11n.pt"
        self.tracker = VehicleTrackerCounter(
            weights=weights,
            person_weights=person_weights if person_weights.is_file() else None,
            output=Path(settings.MEDIA_ROOT) / "live" / f"video_{video.id}.mp4",
            report_directory=project_root / "runs" / "counting" / "live" / f"video_{video.id}",
        )
        capture_source = int(source) if source.isdecimal() else source
        self.capture = cv2.VideoCapture(capture_source)
        if not self.capture.isOpened():
            self.capture.release()
            raise OSError(f"Không mở được luồng camera: {source}")

        success, first_frame = self.capture.read()
        if not success:
            self.capture.release()
            raise OSError("Đã mở luồng nhưng không đọc được frame đầu tiên.")

        height, width = first_frame.shape[:2]
        self.tracker.line = self.tracker.default_counting_line(width, height)
        self.video = video
        self.pending_frame = first_frame
        self.frame_index = 0
        self.started_at = time.perf_counter()
        self.fps = self.capture.get(cv2.CAP_PROP_FPS) or 30.0
        self.closed = False

    def frames(self) -> Iterator[bytes]:
        try:
            while True:
                frame = self.pending_frame
                self.pending_frame = None
                if frame is None:
                    success, frame = self.capture.read()
                    if not success:
                        break

                elapsed = max(time.perf_counter() - self.started_at, 1e-6)
                processing_fps = (self.frame_index + 1) / elapsed
                self.tracker._frame_count = self.frame_index
                annotated = self.tracker.process_frame(
                    frame,
                    self.frame_index,
                    processing_fps,
                    self.frame_index / self.fps,
                )
                encoded, jpeg = cv2.imencode(
                    ".jpg",
                    annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, 82],
                )
                self.frame_index += 1
                if encoded:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Cache-Control: no-store\r\n\r\n"
                        + jpeg.tobytes()
                        + b"\r\n"
                    )
        finally:
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.capture.release()
        counts = self.tracker.counts
        result = KMeansTrafficClassifier(window_seconds=10, k_clusters=3).classify(
            {**counts, "total": sum(counts.values())},
            events=self.tracker.crossings,
        )
        with transaction.atomic():
            snapshot = TrafficSnapshot.objects.create(
                video=self.video,
                total_vehicles=sum(counts.values()),
                car_count=counts.get("car", 0),
                motorcycle_count=counts.get("motorcycle", 0),
                bus_count=counts.get("bus", 0),
                truck_count=counts.get("truck", 0),
                density=float(result.get("density", 0.0)),
            )
            TrafficStatus.objects.create(
                video=self.video,
                status=result.get("status", "Bình thường"),
                status_label=result.get("status_label", "Bình thường"),
                vehicle_count=snapshot.total_vehicles,
            )