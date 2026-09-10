"""Run YOLO inference on sample images and videos.

Only the four vehicle classes requested by the project are kept:
car, motorcycle, bus and truck.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
from ultralytics import YOLO


COCO_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def parse_arguments():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Thử nghiệm nhận diện 4 class phương tiện bằng YOLO."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=project_root / "weights" / "yolo11n.pt",
        help="Đường dẫn model YOLO pretrained.",
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=project_root / "test_samples" / "images",
        help="Thư mục ảnh mẫu.",
    )
    parser.add_argument(
        "--videos",
        type=Path,
        default=project_root / "test_samples" / "videos",
        help="Thư mục video mẫu.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "runs" / "detect" / "predictions",
        help="Thư mục lưu kết quả và detection_summary.json.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.3,
        help="Confidence threshold, mặc định 0.3.",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="IoU threshold cho NMS, mặc định 0.45.",
    )
    return parser.parse_args()


def validate_thresholds(confidence, iou):
    if not 0 <= confidence <= 1:
        raise SystemExit("--conf phải nằm trong khoảng từ 0 đến 1.")
    if not 0 <= iou <= 1:
        raise SystemExit("--iou phải nằm trong khoảng từ 0 đến 1.")


def image_files(directory):
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def video_files(directory):
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def draw_detections(frame, result, counts):
    """Draw filtered detections and update per-class counts for one frame."""
    if result.boxes is None:
        return frame

    for box in result.boxes:
        class_id = int(box.cls[0])
        if class_id not in COCO_CLASSES:
            continue

        confidence = float(box.conf[0])
        x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
        class_name = COCO_CLASSES[class_id]
        counts[class_name] += 1
        label = f"{class_name} {confidence:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        text_y = max(y1 - 10, 20)
        cv2.putText(
            frame,
            label,
            (x1, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 220, 0),
            2,
            cv2.LINE_AA,
        )
    return frame


def predict_frame(model, frame, confidence, iou):
    results = model.predict(
        source=frame,
        conf=confidence,
        iou=iou,
        classes=list(COCO_CLASSES),
        verbose=False,
    )
    return results[0]


def process_image(model, image_path, output_directory, confidence, iou):
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise ValueError(f"Không đọc được ảnh: {image_path}")

    counts = Counter()
    result = predict_frame(model, frame, confidence, iou)
    annotated_frame = draw_detections(frame, result, counts)
    output_path = output_directory / image_path.name
    if not cv2.imwrite(str(output_path), annotated_frame):
        raise OSError(f"Không ghi được ảnh kết quả: {output_path}")

    return {
        "type": "image",
        "input": str(image_path),
        "output": str(output_path),
        "frames": 1,
        "detections": dict(counts),
    }


def process_video(model, video_path, output_directory, confidence, iou):
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Không mở được video: {video_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    output_path = output_directory / video_path.name
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise OSError(f"Không tạo được video kết quả: {output_path}")

    counts = Counter()
    frame_count = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            result = predict_frame(model, frame, confidence, iou)
            writer.write(draw_detections(frame, result, counts))
            frame_count += 1
    finally:
        capture.release()
        writer.release()

    return {
        "type": "video",
        "input": str(video_path),
        "output": str(output_path),
        "frames": frame_count,
        "detections": dict(counts),
    }


def main():
    args = parse_arguments()
    validate_thresholds(args.conf, args.iou)

    if not args.model.is_file():
        raise SystemExit(f"Không tìm thấy model: {args.model}")

    images = image_files(args.images)
    videos = video_files(args.videos)
    if not images and not videos:
        raise SystemExit(
            "Không tìm thấy ảnh hoặc video mẫu. "
            "Hãy đặt dữ liệu vào test_samples/images hoặc test_samples/videos."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.model))
    detections = []

    print(f"Model: {args.model}")
    print(f"Conf: {args.conf}, IoU: {args.iou}")
    print(f"Class được lọc: {COCO_CLASSES}")

    for image_path in images:
        print(f"Đang xử lý ảnh: {image_path.name}")
        detections.append(
            process_image(model, image_path, args.output, args.conf, args.iou)
        )
    for video_path in videos:
        print(f"Đang xử lý video: {video_path.name}")
        detections.append(
            process_video(model, video_path, args.output, args.conf, args.iou)
        )

    total_counts = Counter()
    for item in detections:
        total_counts.update(item["detections"])

    summary = {
        "model": str(args.model),
        "conf_threshold": args.conf,
        "iou_threshold": args.iou,
        "classes": COCO_CLASSES,
        "results": detections,
        "total_detections": dict(total_counts),
    }
    summary_path = args.output / "detection_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Đã lưu kết quả vào: {args.output}")
    print(f"Đã lưu log detection vào: {summary_path}")
    print(f"Tổng detection: {dict(total_counts)}")


if __name__ == "__main__":
    main()