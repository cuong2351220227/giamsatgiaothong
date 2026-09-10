"""Train a custom YOLO model with the Ultralytics API."""

import argparse
import ast
from pathlib import Path


SPLITS = ("train", "val", "test")


def parse_arguments():
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Huấn luyện YOLO custom cho bốn loại phương tiện."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=project_root / "weights" / "yolo11n.pt",
        help="Model base pretrained, mặc định weights/yolo11n.pt.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=project_root / "data" / "external_dataset" / "data.yaml",
        help="File data.yaml của dataset.",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument(
        "--device",
        default="auto",
        help="auto, cpu hoặc chỉ số GPU như 0 (mặc định: auto).",
    )
    parser.add_argument(
        "--name",
        default="train",
        help="Tên thư mục run trong runs/detect/.",
    )
    return parser.parse_args()


def read_yaml_values(yaml_path):
    """Read the simple data.yaml fields without changing the source file."""
    values = {}
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def split_path(dataset_root, configured_path):
    configured_path = configured_path.strip("'\"")
    path_from_yaml = (dataset_root / configured_path).resolve()
    if path_from_yaml.exists():
        return path_from_yaml

    # Some exported Roboflow YAML files use ../train while train is inside
    # the dataset root. Try the conventional root-relative path as fallback.
    path_from_root = (dataset_root / configured_path.removeprefix("../")).resolve()
    return path_from_root if path_from_root.exists() else None


def prepare_data_yaml(data_path, output_directory):
    """Return a usable YAML path, correcting only broken relative paths."""
    values = read_yaml_values(data_path)
    dataset_root = data_path.parent.resolve()
    resolved_splits = {
        split: split_path(dataset_root, values[split])
        for split in SPLITS
        if split in values
    }
    missing = [split for split in ("train", "val") if not resolved_splits.get(split)]
    if missing:
        missing_text = ", ".join(missing)
        raise SystemExit(
            f"Không tìm thấy đường dẫn {missing_text} trong data.yaml: {data_path}"
        )

    original_paths_are_valid = all(
        (dataset_root / values[split].strip("'\"")).resolve().exists()
        for split in resolved_splits
    )
    if original_paths_are_valid:
        return data_path

    output_directory.mkdir(parents=True, exist_ok=True)
    corrected_path = output_directory / "data_train.yaml"
    names = ast.literal_eval(values.get("names", "[]"))
    class_count = int(values.get("nc", len(names)))
    lines = [
        f"train: {resolved_splits['train']}",
        f"val: {resolved_splits['val']}",
    ]
    if resolved_splits.get("test"):
        lines.append(f"test: {resolved_splits['test']}")
    lines.extend([
        "",
        f"nc: {class_count}",
        f"names: {names!r}",
        "",
    ])
    corrected_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"data.yaml có path chưa đúng; dùng bản đã chuẩn hóa: {corrected_path}")
    return corrected_path


def choose_device(device_argument):
    if device_argument.lower() != "auto":
        return device_argument
    try:
        import torch
    except ImportError:
        return "cpu"
    return 0 if torch.cuda.is_available() else "cpu"


def main():
    args = parse_arguments()
    if args.epochs <= 0 or args.imgsz <= 0 or args.batch <= 0:
        raise SystemExit("epochs, imgsz và batch phải lớn hơn 0.")
    if not args.model.is_file():
        raise SystemExit(f"Không tìm thấy model base: {args.model}")
    if not args.data.is_file():
        raise SystemExit(f"Không tìm thấy data.yaml: {args.data}")

    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("Chưa cài ultralytics. Hãy chạy: pip install ultralytics")

    project_root = Path(__file__).resolve().parent
    data_path = prepare_data_yaml(args.data.resolve(), project_root / "runs" / "detect")
    device = choose_device(args.device)
    output_directory = project_root / "runs" / "detect" / args.name

    print(f"Model: {args.model.resolve()}")
    print(f"Data: {data_path}")
    print(f"Device: {device}")
    print(f"epochs={args.epochs}, imgsz={args.imgsz}, batch={args.batch}, optimizer=auto")
    print(f"Output: {output_directory}")

    model = YOLO(str(args.model.resolve()))
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        optimizer="auto",
        project=str(project_root / "runs" / "detect"),
        name=args.name,
        save=True,
        save_period=-1,
        plots=True,
        exist_ok=False,
    )

    print("Huấn luyện hoàn tất.")
    print(f"Checkpoint thường nằm trong: {output_directory / 'weights'}")
    print("Theo dõi TensorBoard bằng lệnh:")
    print("tensorboard --logdir runs/detect/train")


if __name__ == "__main__":
    main()