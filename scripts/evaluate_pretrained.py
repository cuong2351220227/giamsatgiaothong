"""Summarize an Ultralytics inference run for a pretrained model.

This script reports observable detections. It does not claim precision or
recall unless a ground-truth annotation set is available.
"""

import argparse
import json
from pathlib import Path


VEHICLE_CLASSES = ("car", "motorcycle", "bus", "truck")


def parse_arguments():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Đánh giá định lượng ban đầu cho kết quả YOLO pretrained."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=project_root / "runs" / "detect" / "predictions" / "detection_summary.json",
        help="File detection_summary.json từ inference_test.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "runs" / "detect" / "predictions" / "evaluation_report.json",
        help="Nơi lưu báo cáo đánh giá dạng JSON.",
    )
    return parser.parse_args()


def load_summary(summary_path):
    if not summary_path.is_file():
        raise SystemExit(f"Không tìm thấy file summary: {summary_path}")
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"summary không phải JSON hợp lệ: {error}") from error


def calculate_metrics(summary):
    total_frames = sum(item.get("frames", 0) for item in summary.get("results", []))
    total_detections = {
        name: int(summary.get("total_detections", {}).get(name, 0))
        for name in VEHICLE_CLASSES
    }
    detection_total = sum(total_detections.values())
    detections_per_frame = detection_total / total_frames if total_frames else 0
    class_distribution = {
        name: (count / detection_total if detection_total else 0)
        for name, count in total_detections.items()
    }

    return {
        "model": summary.get("model"),
        "conf_threshold": summary.get("conf_threshold"),
        "iou_threshold": summary.get("iou_threshold"),
        "sample_count": len(summary.get("results", [])),
        "frame_count": total_frames,
        "detection_count": detection_total,
        "detections_per_frame": round(detections_per_frame, 4),
        "detections_by_class": total_detections,
        "detection_distribution_by_class": {
            name: round(value, 4) for name, value in class_distribution.items()
        },
        "ground_truth_available": False,
        "precision": None,
        "recall": None,
        "false_positive_count": None,
        "missed_vehicle_count": None,
        "car_truck_confusion_count": None,
        "manual_review_required": [
            "Đánh dấu false positive trên frame mẫu.",
            "Đếm xe máy nhỏ bị bỏ sót hoặc bị che khuất.",
            "Kiểm tra nhầm lẫn giữa car và truck.",
        ],
    }


def print_report(metrics):
    print("ĐÁNH GIÁ PRETRAINED MODEL")
    print(f"Model: {metrics['model']}")
    print(f"Số frame: {metrics['frame_count']}")
    print(f"Tổng detection: {metrics['detection_count']}")
    print(f"Detection trung bình/frame: {metrics['detections_per_frame']}")
    print("Detection theo class:")
    for name, count in metrics["detections_by_class"].items():
        share = metrics["detection_distribution_by_class"][name] * 100
        print(f"  {name}: {count} ({share:.2f}%)")
    print("Precision/recall, false positive, bỏ sót và nhầm car-truck cần review thủ công")
    print("vì summary hiện tại không chứa ground-truth annotation.")


def main():
    args = parse_arguments()
    summary = load_summary(args.summary)
    metrics = calculate_metrics(summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print_report(metrics)
    print(f"Đã lưu báo cáo JSON: {args.output}")


if __name__ == "__main__":
    main()