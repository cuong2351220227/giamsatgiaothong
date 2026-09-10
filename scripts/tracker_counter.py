"""Track vehicles with ByteTrack and count crossings over a configurable line."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO


VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck")
DEFAULT_WEIGHTS = Path(__file__).resolve().parents[1] / "final_weights" / "vehicle_detector_best.pt"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "runs" / "counting" / "counted_output.mp4"
DEFAULT_REPORT_DIRECTORY = Path(__file__).resolve().parents[1] / "runs" / "counting"


class VehicleTrackerCounter:
    """ByteTrack-based vehicle tracker and counting-line processor."""

    def __init__(
        self,
        weights: str | Path = DEFAULT_WEIGHTS,
        output: str | Path = DEFAULT_OUTPUT,
        line: tuple[tuple[int, int], tuple[int, int]] = ((320, 360), (960, 360)),
        conf_threshold: float = 0.35,
        report_directory: str | Path = DEFAULT_REPORT_DIRECTORY,
        trail_length: int = 30,
    ) -> None:
        if not 0 <= conf_threshold <= 1:
            raise ValueError("conf_threshold phải nằm trong khoảng từ 0 đến 1.")
        if trail_length < 2:
            raise ValueError("trail_length phải lớn hơn hoặc bằng 2.")
        self.weights = Path(weights)
        self.output = Path(output)
        self.line = line
        self.conf_threshold = conf_threshold
        self.report_directory = Path(report_directory)
        self.trail_length = trail_length
        self.model = YOLO(str(self.weights))
        self.trails: dict[int, deque[tuple[int, int]]] = defaultdict(
            lambda: deque(maxlen=self.trail_length)
        )
        self.previous_centers: dict[int, tuple[int, int]] = {}
        self.counted_ids: set[int] = set()
        self.counts = Counter({class_name: 0 for class_name in VEHICLE_CLASSES})
        self.crossings: list[dict[str, Any]] = []
        self._last_crossing_frame = -1
        self._frame_count = 0
        self._start_time = 0.0
        self._allowed_ids = self._find_allowed_model_ids()

    @staticmethod
    def _canonical_class_name(name: str) -> str:
        return name.strip().lower().replace("motorbike", "motorcycle")

    def _find_allowed_model_ids(self) -> list[int] | None:
        names = self.model.names
        items = names.items() if isinstance(names, dict) else enumerate(names)
        allowed = [
            int(class_id)
            for class_id, name in items
            if self._canonical_class_name(str(name)) in VEHICLE_CLASSES
        ]
        return allowed or None

    @staticmethod
    def _side_of_line(point: tuple[int, int], line: tuple[tuple[int, int], tuple[int, int]]) -> int:
        """Return the signed side of point relative to the directed counting line."""
        (x1, y1), (x2, y2) = line
        cross = (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
        if cross > 0:
            return 1
        if cross < 0:
            return -1
        return 0

    def _crossed_line(self, previous: tuple[int, int], current: tuple[int, int]) -> bool:
        previous_side = self._side_of_line(previous, self.line)
        current_side = self._side_of_line(current, self.line)
        return previous_side != 0 and current_side != 0 and previous_side != current_side

    def _extract_tracks(self, result) -> list[dict[str, Any]]:
        if result.boxes is None or result.boxes.id is None:
            return []
        names = self.model.names
        tracks = []
        for index, box in enumerate(result.boxes):
            track_id = int(result.boxes.id[index].item())
            class_id = int(box.cls[0].item())
            raw_name = names[class_id] if isinstance(names, dict) else names[class_id]
            class_name = self._canonical_class_name(str(raw_name))
            if class_name not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = [int(round(value)) for value in box.xyxy[0].tolist()]
            center = ((x1 + x2) // 2, y2)
            tracks.append({
                "track_id": track_id,
                "class_id": class_id,
                "class_name": class_name,
                "confidence": round(float(box.conf[0].item()), 4),
                "box": (x1, y1, x2, y2),
                "center": center,
            })
        return tracks

    def _register_crossing(self, track: dict[str, Any], timestamp: float) -> None:
        track_id = track["track_id"]
        if track_id in self.counted_ids:
            return
        self.counted_ids.add(track_id)
        class_name = track["class_name"]
        self.counts[class_name] += 1
        self.crossings.append({
            "track_id": track_id,
            "class_name": class_name,
            "timestamp": round(timestamp, 3),
            "frame_index": self._frame_count,
        })
        self._last_crossing_frame = self._frame_count

    def _draw_trail(self, frame, track_id: int) -> None:
        points = list(self.trails[track_id])
        for start, end in zip(points, points[1:]):
            cv2.line(frame, start, end, (255, 190, 0), 2, cv2.LINE_AA)

    def _draw_hud(self, frame, fps: float) -> None:
        overlay = frame.copy()
        cv2.rectangle(overlay, (12, 12), (260, 178), (12, 18, 24), -1)
        cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
        cv2.putText(frame, f"FPS: {fps:.1f}", (24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (80, 220, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"TOTAL: {sum(self.counts.values())}", (24, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (235, 240, 245), 2, cv2.LINE_AA)
        for row, class_name in enumerate(VEHICLE_CLASSES, start=1):
            cv2.putText(
                frame,
                f"{class_name}: {self.counts[class_name]}",
                (24, 64 + row * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.53,
                (235, 240, 245),
                1,
                cv2.LINE_AA,
            )

    def process_frame(self, frame, frame_index: int, fps: float, timestamp: float):
        """Track one frame, update counts, and return the annotated frame."""
        results = self.model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=self.conf_threshold,
            classes=self._allowed_ids,
            verbose=False,
        )
        tracks = self._extract_tracks(results[0])
        for track in tracks:
            track_id = track["track_id"]
            center = track["center"]
            if track_id in self.previous_centers and self._crossed_line(self.previous_centers[track_id], center):
                self._register_crossing(track, timestamp)
            self.previous_centers[track_id] = center
            self.trails[track_id].append(center)
            x1, y1, x2, y2 = track["box"]
            color = (0, 220, 80) if track_id in self.counted_ids else (0, 180, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"ID {track_id} {track['class_name']} {track['confidence']:.2f}",
                (x1, max(y1 - 8, 22)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
            self._draw_trail(frame, track_id)

        line_color = (0, 220, 80) if self._last_crossing_frame == frame_index else (0, 0, 255)
        cv2.line(frame, *self.line, line_color, 4, cv2.LINE_AA)
        self._draw_hud(frame, fps)
        return frame

    def process_video(self, source: str | Path):
        """Track a video file or stream and save the output/report files."""
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise OSError(f"Không mở được video hoặc stream: {source}")
        input_fps = capture.get(cv2.CAP_PROP_FPS)
        output_fps = input_fps if input_fps and input_fps > 0 else 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            capture.release()
            raise OSError("Không đọc được kích thước video đầu vào.")

        self.output.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(self.output),
            cv2.VideoWriter_fourcc(*"mp4v"),
            output_fps,
            (width, height),
        )
        if not writer.isOpened():
            capture.release()
            raise OSError(f"Không tạo được video output: {self.output}")

        self._frame_count = 0
        self._start_time = time.perf_counter()
        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break
                timestamp = self._frame_count / output_fps
                elapsed = max(time.perf_counter() - self._start_time, 1e-6)
                fps = (self._frame_count + 1) / elapsed
                annotated = self.process_frame(frame, self._frame_count, fps, timestamp)
                writer.write(annotated)
                self._frame_count += 1
        finally:
            capture.release()
            writer.release()
        self.save_logs(source)
        return {
            "source": str(source),
            "output": str(self.output),
            "frames": self._frame_count,
            "counts": dict(self.counts),
            "total": sum(self.counts.values()),
        }

    def save_logs(self, source: str | Path):
        """Write total counts and every unique counted ID to JSON and CSV."""
        self.report_directory.mkdir(parents=True, exist_ok=True)
        json_path = self.report_directory / "counting_summary.json"
        csv_path = self.report_directory / "counting_summary.csv"
        summary = {
            "source": str(source),
            "weights": str(self.weights),
            "line": [list(point) for point in self.line],
            "confidence_threshold": self.conf_threshold,
            "counts": dict(self.counts),
            "total": sum(self.counts.values()),
            "crossings": self.crossings,
        }
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            fieldnames = ["track_id", "class_name", "timestamp", "frame_index"]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.crossings)
        return json_path, csv_path


def parse_line_coordinates(value: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Parse x1,y1,x2,y2 or a JSON-like [[x1,y1],[x2,y2]] value."""
    try:
        parsed = json.loads(value)
        if len(parsed) == 2 and all(len(point) == 2 for point in parsed):
            return tuple((int(point[0]), int(point[1])) for point in parsed)  # type: ignore[return-value]
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    try:
        values = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("--line-coords cần dạng x1,y1,x2,y2 hoặc [[x1,y1],[x2,y2]].") from error
    if len(values) != 4:
        raise argparse.ArgumentTypeError("--line-coords cần đúng 4 tọa độ.")
    return ((values[0], values[1]), (values[2], values[3]))


def parse_arguments():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Tracking và đếm phương tiện qua vạch bằng ByteTrack.")
    parser.add_argument("--source", required=True, help="Đường dẫn video đầu vào.")
    parser.add_argument("--weights", type=Path, default=project_root / "final_weights" / "vehicle_detector_best.pt")
    parser.add_argument("--line-coords", type=parse_line_coordinates, required=True, help="x1,y1,x2,y2 hoặc [[x1,y1],[x2,y2]].")
    parser.add_argument("--conf", type=float, default=0.35, help="Ngưỡng confidence.")
    parser.add_argument("--output", type=Path, default=project_root / "runs" / "counting" / "counted_output.mp4")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if not args.weights.is_file():
        raise SystemExit(f"Không tìm thấy model: {args.weights}")
    try:
        counter = VehicleTrackerCounter(
            weights=args.weights,
            output=args.output,
            line=args.line_coords,
            conf_threshold=args.conf,
        )
        result = counter.process_video(args.source)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
