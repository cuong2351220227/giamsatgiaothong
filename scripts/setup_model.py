"""Download a pretrained Ultralytics YOLO model into the weights directory."""

import argparse
from pathlib import Path


MODEL_NAMES = ("yolo11n.pt", "yolov8n.pt")


def main():
    parser = argparse.ArgumentParser(
        description="Tải mô hình YOLO pretrained vào thư mục weights."
    )
    parser.add_argument(
        "--model",
        choices=MODEL_NAMES,
        default="yolo11n.pt",
        help="Tên model cần tải (mặc định: yolo11n.pt)",
    )
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit(
            "Chưa cài ultralytics. Hãy chạy: "
            "python -m pip install ultralytics"
        )

    project_root = Path(__file__).resolve().parents[1]
    weights_directory = project_root / "weights"
    weights_directory.mkdir(parents=True, exist_ok=True)
    model_path = weights_directory / args.model

    print(f"Đang tải hoặc kiểm tra mô hình: {args.model}")
    print(f"Đường dẫn lưu: {model_path}")

    try:
        YOLO(str(model_path))
    except Exception as error:
        raise SystemExit(f"Tải mô hình thất bại: {error}") from error

    if not model_path.is_file() or model_path.stat().st_size == 0:
        raise SystemExit("Tải mô hình thất bại: không tìm thấy file model hợp lệ.")

    size_mb = model_path.stat().st_size / (1024 * 1024)
    print("Tải mô hình thành công.")
    print(f"File model: {model_path}")
    print(f"Kích thước: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()