"""Validate the custom model and compare it with the pretrained model."""

import argparse
import ast
import json
import shutil
from pathlib import Path

import cv2
from ultralytics import YOLO


COCO_VEHICLE_IDS = [2, 3, 5, 7]
COCO_VEHICLE_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def parse_arguments():
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Validate and compare pretrained and custom YOLO models."
    )
    parser.add_argument(
        "--custom-model",
        type=Path,
        default=project_root / "runs" / "detect" / "train" / "weights" / "best.pt",
        help="Checkpoint custom best.pt.",
    )
    parser.add_argument(
        "--pretrained-model",
        type=Path,
        default=project_root / "weights" / "yolo11n.pt",
        help="Model pretrained gốc.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=project_root / "runs" / "detect" / "data_train.yaml",
        help="data.yaml đã có đường dẫn hợp lệ.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=project_root / "test_samples" / "videos" / "17604987-hd_1920_1080_30fps.mp4",
        help="Ảnh hoặc video dùng để so sánh.",
    )
    parser.add_argument("--conf", type=float, default=0.3)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument(
        "--device",
        default="auto",
        help="auto, cpu hoặc GPU index như 0.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "runs" / "compare",
        help="Thư mục lưu báo cáo và video so sánh.",
    )
    return parser.parse_args()


def choose_device(device_argument):
    if device_argument.lower() != "auto":
        return device_argument
    try:
        import torch
    except ImportError:
        return "cpu"
    return 0 if torch.cuda.is_available() else "cpu"


def read_class_names(data_path):
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("names:"):
            names = ast.literal_eval(line.split(":", 1)[1].strip())
            return [str(name) for name in names]
    raise SystemExit(f"Không tìm thấy names trong data.yaml: {data_path}")


def validate_arguments(args):
    if not 0 <= args.conf <= 1 or not 0 <= args.iou <= 1:
        raise SystemExit("--conf và --iou phải nằm trong khoảng từ 0 đến 1.")
    for path, label in (
        (args.custom_model, "custom model"),
        (args.pretrained_model, "pretrained model"),
        (args.data, "data.yaml"),
        (args.source, "source"),
    ):
        if not path.is_file():
            raise SystemExit(f"Không tìm thấy {label}: {path}")


def metric_value(values, index):
    if values is None or index >= len(values):
        return None
    return float(values[index])


def validate_custom_model(model, data_path, device):
    metrics = model.val(
        data=str(data_path),
        split="test",
        device=device,
        plots=True,
        verbose=False,
    )
    class_names = [
        "motorcycle" if name == "motorbike" else name
        for name in model.names.values()
    ]
    precision = getattr(metrics.box, "p", None)
    recall = getattr(metrics.box, "r", None)
    map50 = getattr(metrics.box, "ap50", None)
    map50_95 = getattr(metrics.box, "ap", None)
    per_class = {}
    for class_id, class_name in enumerate(class_names):
        per_class[class_name] = {
            "precision": metric_value(precision, class_id),
            "recall": metric_value(recall, class_id),
            "mAP50": metric_value(map50, class_id),
            "mAP50-95": metric_value(map50_95, class_id),
        }

    return {
        "model": "custom",
        "checkpoint": str(model.ckpt_path) if hasattr(model, "ckpt_path") else None,
        "split": "test",
        "class_metrics": per_class,
        "overall": {
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "mAP50": float(metrics.box.map50),
            "mAP50-95": float(metrics.box.map),
        },
    }


def predict_annotated(model, frame, confidence, iou, classes=None):
    results = model.predict(
        source=frame,
        conf=confidence,
        iou=iou,
        classes=classes,
        verbose=False,
    )
    return results[0].plot(labels=True, conf=True, boxes=True)


def compare_image(pretrained, custom, source, output_path, confidence, iou):
    frame = cv2.imread(str(source))
    if frame is None:
        raise SystemExit(f"Không đọc được ảnh: {source}")
    pretrained_frame = predict_annotated(
        pretrained, frame.copy(), confidence, iou, COCO_VEHICLE_IDS
    )
    custom_frame = predict_annotated(custom, frame.copy(), confidence, iou)
    comparison = cv2.hconcat([pretrained_frame, custom_frame])
    cv2.putText(comparison, "PRETRAINED", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    cv2.putText(comparison, "CUSTOM", (frame.shape[1] + 20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    if not cv2.imwrite(str(output_path), comparison):
        raise SystemExit(f"Không ghi được ảnh so sánh: {output_path}")


def compare_video(pretrained, custom, source, output_path, confidence, iou):
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise SystemExit(f"Không mở được video: {source}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width * 2, height)
    )
    if not writer.isOpened():
        capture.release()
        raise SystemExit(f"Không tạo được video so sánh: {output_path}")

    frame_count = 0
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            pretrained_frame = predict_annotated(
                pretrained, frame.copy(), confidence, iou, COCO_VEHICLE_IDS
            )
            custom_frame = predict_annotated(custom, frame.copy(), confidence, iou)
            comparison = cv2.hconcat([pretrained_frame, custom_frame])
            cv2.putText(comparison, "PRETRAINED", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(comparison, "CUSTOM", (width + 20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            writer.write(comparison)
            frame_count += 1
    finally:
        capture.release()
        writer.release()
    return frame_count


def main():
    args = parse_arguments()
    validate_arguments(args)
    args.output.mkdir(parents=True, exist_ok=True)
    device = choose_device(args.device)

    final_weights = Path(__file__).resolve().parent / "final_weights" / "vehicle_detector_best.pt"
    final_weights.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.custom_model, final_weights)
    print(f"Đã lưu best.pt tại: {final_weights}")

    print(f"Đang validate custom model trên test bằng device={device}...")
    custom = YOLO(str(args.custom_model))
    pretrained = YOLO(str(args.pretrained_model))
    validation = validate_custom_model(custom, args.data, device)

    report_path = args.output / "model_comparison.json"
    report = {
        "validation": validation,
        "pretrained_model": str(args.pretrained_model),
        "custom_model": str(args.custom_model),
        "source": str(args.source),
        "conf_threshold": args.conf,
        "iou_threshold": args.iou,
        "final_weights": str(final_weights),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.source.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        comparison_path = args.output / f"{args.source.stem}_comparison.jpg"
        compare_image(pretrained, custom, args.source, comparison_path, args.conf, args.iou)
        processed = 1
    else:
        comparison_path = args.output / f"{args.source.stem}_comparison.mp4"
        processed = compare_video(pretrained, custom, args.source, comparison_path, args.conf, args.iou)

    print(f"Đã validate và lưu báo cáo: {report_path}")
    print(f"Đã tạo kết quả side-by-side: {comparison_path} ({processed} frame/ảnh)")


if __name__ == "__main__":
    main()