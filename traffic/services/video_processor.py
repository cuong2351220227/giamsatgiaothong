from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.tracker_counter import VehicleTrackerCounter

from .classifier import KMeansTrafficClassifier


class VideoProcessingService:
    """Run OpenCV/YOLO tracking, count crossings, then classify traffic density."""

    def __init__(self, source_path: str | Path, video_id: int | None = None):
        self.source_path = Path(source_path) if source_path else None
        self.video_id = video_id

    def process(self) -> dict[str, Any]:
        if self.source_path is None or not self.source_path.is_file():
            raise OSError(f"Không tìm thấy video đầu vào: {self.source_path}")

        project_root = Path(__file__).resolve().parents[2]
        weights = project_root / "final_weights" / "vehicle_detector_best.pt"
        if not weights.is_file():
            raise OSError(f"Không tìm thấy model YOLO: {weights}")

        output_directory = project_root / "runs" / "counting" / "processed"
        if self.video_id is not None:
            output_directory /= f"video_{self.video_id}"
        else:
            output_directory /= self.source_path.stem
        output_path = output_directory / "annotated.mp4"
        person_weights = project_root / "weights" / "yolo11n.pt"
        tracker = VehicleTrackerCounter(
            weights=weights,
            person_weights=person_weights if person_weights.is_file() else None,
            output=output_path,
            report_directory=output_directory,
        )
        tracking_result = tracker.process_video(self.source_path)
        raw_counts = tracking_result.get("counts", {})
        counts = {
            name: int(raw_counts.get(name, 0))
            for name in ("car", "motorcycle", "bus", "truck")
        }
        counts["total"] = int(tracking_result.get("total", sum(counts.values())))
        classifier = KMeansTrafficClassifier(window_seconds=10, k_clusters=3)
        result = classifier.classify(counts, events=tracking_result.get("crossings", []))
        result["counts"] = counts
        result["source"] = str(self.source_path)
        result["output"] = str(tracking_result.get("output", output_path))
        result["frames"] = int(tracking_result.get("frames", 0))
        return result
