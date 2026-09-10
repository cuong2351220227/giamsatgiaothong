"""Video vehicle-detection pipeline with YOLO, frame skipping and CSV/JSON logs."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO


VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck")
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_WEIGHTS = Path(__file__).resolve().parents[1] / "final_weights" / "vehicle_detector_best.pt"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "runs" / "detect" / "pipeline_output.mp4"
DEFAULT_LOG_DIRECTORY = Path(__file__).resolve().parents[1] / "runs" / "detect"


@dataclass(frozen=True)
class FrameResult:
    """Detection data and rendered frame returned by process_frame."""

    frame: Any
    detections: list[list[Any]]
    counts: dict[str, int]


class TrafficDetectorPipeline:
    """Process a video stream, render detections, and write per-frame logs."""

    def __init__(
        self,
        weights: str | Path = DEFAULT_WEIGHTS,
        output: str | Path = DEFAULT_OUTPUT,
        frame_skip: int = 1,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        target_size: tuple[int, int] = (DEFAULT_WIDTH, DEFAULT_HEIGHT),
        log_directory: str | Path = DEFAULT_LOG_DIRECTORY,
    ) -> None:
        if frame_skip < 1:
            raise ValueError("frame_skip phải lớn hơn hoặc bằng 1.")
        if not 0 <= conf_threshold <= 1:
            raise ValueError("conf_threshold phải nằm trong khoảng từ 0 đến 1.")
        if not 0 <= iou_threshold <= 1:
            raise ValueError("iou_threshold phải nằm trong khoảng từ 0 đến 1.")
        if len(target_size) != 2 or min(target_size) <= 0:
            raise ValueError("target_size phải gồm width và height lớn hơn 0.")

        self.project_root = Path(__file__).resolve().parents[1]
        self.weights = Path(weights)
        self.output = Path(output)
        self.frame_skip = frame_skip
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.target_width, self.target_height = target_size
        self.log_directory = Path(log_directory)
        self.model = YOLO(str(self.weights))
        self.history: list[dict[str, Any]] = []
        self._last_detections: list[list[Any]] = []
        self._start_time: float | None = None
        self._processed_frames = 0

    @staticmethod
    def _canonical_class_name(name: str) -> str:
        normalized = name.strip().lower().replace("motorbike", "motorcycle")
        return normalized

    def _allowed_model_ids(self) -> list[int] | None:
        names = self.model.names
        if isinstance(names, dict):
            items = names.items()
        else:
            items = enumerate(names)
        allowed_ids = [int(class_id) for class_id, name in items
                       if self._canonical_class_name(str(name)) in VEHICLE_CLASSES]
        return allowed_ids or None

    def _resize_frame(self, frame):
        """Resize with aspect ratio preserved and pad to the target canvas."""
        source_height, source_width = frame.shape[:2]
        scale = min(self.target_width / source_width, self.target_height / source_height)
        resized_width = max(1, round(source_width * scale))
        resized_height = max(1, round(source_height * scale))
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        canvas = cv2.copyMakeBorder(
            resized,
            (self.target_height - resized_height) // 2,
            self.target_height - resized_height - (self.target_height - resized_height) // 2,
            (self.target_width - resized_width) // 2,
            self.target_width - resized_width - (self.target_width - resized_width) // 2,
            cv2.BORDER_CONSTANT,
            value=(24, 30, 36),
        )
        return canvas

    def _read_detections(self, result) -> list[list[Any]]:
        detections: list[list[Any]] = []
        if result.boxes is None:
            return detections

        names = self.model.names
        for box in result.boxes:
            class_id = int(box.cls[0])
            raw_name = names[class_id] if isinstance(names, dict) else names[class_id]
            class_name = self._canonical_class_name(str(raw_name))
            if class_name not in VEHICLE_CLASSES:
                continue
            coordinates = [int(round(value)) for value in box.xyxy[0].tolist()]
            confidence = round(float(box.conf[0]), 4)
            detections.append([*coordinates, confidence, class_id, class_name])
        return detections

    @staticmethod
    def _counts(detections: list[list[Any]]) -> dict[str, int]:
        counts = Counter(detection[6] for detection in detections)
        return {class_name: counts.get(class_name, 0) for class_name in VEHICLE_CLASSES}

    def _draw_hud(self, frame, counts: dict[str, int], fps: float):
        overlay = frame.copy()
        cv2.rectangle(overlay, (12, 12), (250, 148), (12, 18, 24), -1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
        cv2.putText(frame, f"FPS: {fps:.1f}", (24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 220, 255), 2, cv2.LINE_AA)
        for row, class_name in enumerate(VEHICLE_CLASSES, start=1):
            cv2.putText(
                frame,
                f"{class_name}: {counts[class_name]}",
                (24, 38 + row * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (235, 240, 245),
                1,
                cv2.LINE_AA,
            )
        return frame

    def _draw_detections(self, frame, detections: list[list[Any]], fps: float):
        colors = {
            "car": (60, 190, 255),
            "motorcycle": (90, 220, 120),
            "bus": (255, 170, 70),
            "truck": (220, 120, 240),
        }
        for x1, y1, x2, y2, confidence, _class_id, class_name in detections:
            color = colors[class_name]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name} {confidence:.2f}"
            text_y = max(y1 - 8, 22)
            cv2.putText(frame, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        return self._draw_hud(frame, self._counts(detections), fps)

    def process_frame(self, frame, frame_index: int = 0) -> FrameResult:
        """Run inference when due, reuse the previous boxes, and render one frame."""
        processed = self._resize_frame(frame)
        if frame_index % self.frame_skip == 0 or not self._last_detections:
            results = self.model.predict(
                source=processed,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                classes=self._allowed_model_ids(),
                verbose=False,
            )
            self._last_detections = self._read_detections(results[0])

        self._processed_frames += 1
        elapsed = max((time.perf_counter() - self._start_time) if self._start_time else 0.0, 1e-6)
        fps = self._processed_frames / elapsed
        counts = self._counts(self._last_detections)
        rendered = self._draw_detections(processed, self._last_detections, fps)
        return FrameResult(rendered, list(self._last_detections), counts)

    def process_video(self, source: str | Path):
        """Read a video or RTSP stream, write annotated video, and save logs."""
        source_value = str(source)
        capture = cv2.VideoCapture(source_value)
        if not capture.isOpened():
            raise OSError(f"Không mở được video hoặc RTSP stream: {source_value}")

        input_fps = capture.get(cv2.CAP_PROP_FPS)
        output_fps = input_fps if input_fps and input_fps > 0 else 30.0
        self.output.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(self.output),
            cv2.VideoWriter_fourcc(*"mp4v"),
            output_fps,
            (self.target_width, self.target_height),
        )
        if not writer.isOpened():
            capture.release()
            raise OSError(f"Không tạo được video kết quả: {self.output}")

        self.history.clear()
        self._last_detections = []
        self._processed_frames = 0
        self._start_time = time.perf_counter()
        frame_index = 0
        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break
                result = self.process_frame(frame, frame_index)
                timestamp = frame_index / output_fps
                self.history.append({
                    "timestamp": round(timestamp, 3),
                    "frame_index": frame_index,
                    **result.counts,
                })
                writer.write(result.frame)
                frame_index += 1
        finally:
            capture.release()
            writer.release()

        self.save_logs()
        return {
            "source": source_value,
            "output": str(self.output),
            "frames": frame_index,
            "fps": round(self._processed_frames / max(time.perf_counter() - self._start_time, 1e-6), 3),
            "json_log": str(self.log_directory / "detection_summary.json"),
            "csv_log": str(self.log_directory / "detection_summary.csv"),
        }

    def save_logs(self):
        """Write frame history to the required JSON and CSV files."""
        self.log_directory.mkdir(parents=True, exist_ok=True)
        json_path = self.log_directory / "detection_summary.json"
        csv_path = self.log_directory / "detection_summary.csv"
        summary = {
            "source": str(self.output),
            "weights": str(self.weights),
            "conf_threshold": self.conf_threshold,
            "iou_threshold": self.iou_threshold,
            "frame_skip": self.frame_skip,
            "target_size": [self.target_width, self.target_height],
            "classes": list(VEHICLE_CLASSES),
            "frames": len(self.history),
            "history": self.history,
        }
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            fieldnames = ["timestamp", "frame_index", *VEHICLE_CLASSES]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.history)
        return json_path, csv_path


def parse_arguments():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Nhận diện phương tiện từ video hoặc RTSP bằng YOLO.")
    parser.add_argument("--source", required=True, help="Đường dẫn video hoặc URL RTSP.")
    parser.add_argument("--weights", type=Path, default=project_root / "final_weights" / "vehicle_detector_best.pt")
    parser.add_argument("--output", type=Path, default=project_root / "runs" / "detect" / "pipeline_output.mp4")
    parser.add_argument("--skip-frames", type=int, default=1, help="Chạy inference mỗi N frame.")
    parser.add_argument("--conf", type=float, default=0.35, help="Ngưỡng confidence.")
    parser.add_argument("--iou", type=float, default=0.45, help="Ngưỡng IoU cho NMS.")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if not args.weights.is_file():
        raise SystemExit(f"Không tìm thấy model: {args.weights}")
    try:
        pipeline = TrafficDetectorPipeline(
            weights=args.weights,
            output=args.output,
            frame_skip=args.skip_frames,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
        )
        result = pipeline.process_video(args.source)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
