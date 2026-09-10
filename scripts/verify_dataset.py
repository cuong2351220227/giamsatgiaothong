"""Verify YOLO labels, create visual previews, and prepare data.yaml."""

import argparse
import ast
import math
import random
from pathlib import Path

import cv2


CLASS_NAMES = ["car", "motorcycle", "bus", "truck"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def choose_dataset_directory(project_root):
    custom = project_root / "data" / "custom_dataset"
    external = project_root / "data" / "external_dataset"
    return custom if custom.is_dir() else external


def parse_arguments():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Kiểm tra nhãn YOLO và tạo preview cho dataset custom."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=choose_dataset_directory(project_root),
        help="Thư mục dataset chứa train/valid hoặc val.",
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=10,
        help="Số ảnh preview tối đa cho mỗi split train và val.",
    )
    parser.add_argument(
        "--write-yaml",
        action="store_true",
        help="Ghi data.yaml theo mapping car, motorcycle, bus, truck.",
    )
    return parser.parse_args()


def find_split(dataset_directory, split):
    split_directory = dataset_directory / split
    if split_directory.is_dir():
        return split_directory
    if split == "val":
        valid_directory = dataset_directory / "valid"
        if valid_directory.is_dir():
            return valid_directory
    return None


def get_files(directory, extension):
    if not directory.is_dir():
        return {}
    return {
        path.stem: path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == extension
    }


def check_label(label_path, class_count):
    errors = []
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return ["file label rỗng"]

    for line_number, line in enumerate(text.splitlines(), 1):
        values = line.split()
        if len(values) != 5:
            errors.append(f"dòng {line_number}: cần 5 giá trị")
            continue
        try:
            class_id = int(values[0])
            coordinates = [float(value) for value in values[1:]]
        except ValueError:
            errors.append(f"dòng {line_number}: class ID hoặc tọa độ không phải số")
            continue

        if class_id < 0 or class_id >= class_count:
            errors.append(f"dòng {line_number}: class ID {class_id} ngoài khoảng hợp lệ")
        if not all(math.isfinite(value) for value in coordinates):
            errors.append(f"dòng {line_number}: tọa độ không hữu hạn")
        elif not all(0 <= value <= 1 for value in coordinates):
            errors.append(f"dòng {line_number}: tọa độ ngoài khoảng [0, 1]")
        elif coordinates[2] <= 0 or coordinates[3] <= 0:
            errors.append(f"dòng {line_number}: width/height phải lớn hơn 0")
    return errors


def check_split(dataset_directory, split, class_count):
    split_directory = find_split(dataset_directory, split)
    if split_directory is None:
        return None

    images_directory = split_directory / "images"
    labels_directory = split_directory / "labels"
    images = {}
    for extension in IMAGE_EXTENSIONS:
        images.update(get_files(images_directory, extension))
    labels = get_files(labels_directory, ".txt")
    errors = []

    for stem, image_path in sorted(images.items()):
        if stem not in labels:
            errors.append(f"Ảnh không có label: {image_path}")
    for stem, label_path in sorted(labels.items()):
        if stem not in images:
            errors.append(f"Label không có ảnh: {label_path}")
        errors.extend(
            f"{label_path}: {message}"
            for message in check_label(label_path, class_count)
        )

    return {
        "directory": split_directory,
        "images": images,
        "labels": labels,
        "errors": errors,
    }


def read_existing_class_names(dataset_directory):
    yaml_path = dataset_directory / "data.yaml"
    if not yaml_path.is_file():
        return CLASS_NAMES
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("names:"):
            try:
                names = ast.literal_eval(line.split(":", 1)[1].strip())
                if isinstance(names, list) and len(names) == len(CLASS_NAMES):
                    return [str(name) for name in names]
            except (SyntaxError, ValueError):
                break
    return CLASS_NAMES


def draw_preview(image_path, label_path, output_path, class_names):
    image = cv2.imread(str(image_path))
    if image is None:
        return False
    height, width = image.shape[:2]
    if label_path.is_file():
        for line in label_path.read_text(encoding="utf-8").splitlines():
            values = line.split()
            if len(values) != 5:
                continue
            try:
                class_id = int(values[0])
                x_center, y_center, box_width, box_height = map(float, values[1:])
            except ValueError:
                continue
            x1 = int((x_center - box_width / 2) * width)
            y1 = int((y_center - box_height / 2) * height)
            x2 = int((x_center + box_width / 2) * width)
            y2 = int((y_center + box_height / 2) * height)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width - 1, x2), min(height - 1, y2)
            name = class_names[class_id] if 0 <= class_id < len(class_names) else str(class_id)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(
                image,
                name,
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 220, 0),
                2,
                cv2.LINE_AA,
            )
    return cv2.imwrite(str(output_path), image)


def write_data_yaml(dataset_directory):
    yaml_path = dataset_directory / "data.yaml"
    validation_directory = "val" if (dataset_directory / "val").is_dir() else "valid"
    content = (
        "# YOLO dataset configuration\n"
        "train: train/images\n"
        f"val: {validation_directory}/images\n"
        "test: test/images\n\n"
        "nc: 4\n"
        "names: ['car', 'motorcycle', 'bus', 'truck']\n"
    )
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def main():
    args = parse_arguments()
    dataset_directory = args.dataset.resolve()
    if not dataset_directory.is_dir():
        raise SystemExit(f"Không tìm thấy dataset: {dataset_directory}")
    if args.preview_count < 0:
        raise SystemExit("--preview-count không được âm.")

    print(f"Dataset: {dataset_directory}")
    reports = {}
    class_names = read_existing_class_names(dataset_directory)
    if class_names != CLASS_NAMES:
        print(
            "CẢNH BÁO: data.yaml hiện có mapping class "
            f"{class_names}; preview sẽ dùng mapping này."
        )
    for split in ("train", "val", "test"):
        report = check_split(dataset_directory, split, len(CLASS_NAMES))
        if report is None:
            print(f"{split}: không tìm thấy")
            continue
        reports[split] = report
        print(
            f"{split}: {len(report['images'])} ảnh, "
            f"{len(report['labels'])} label, {len(report['errors'])} lỗi"
        )
        for error in report["errors"]:
            print(f"  - {error}")

    preview_directory = dataset_directory / "preview_labels"
    preview_directory.mkdir(parents=True, exist_ok=True)
    random_generator = random.Random(42)
    for split in ("train", "val"):
        report = reports.get(split)
        if report is None:
            continue
        candidates = list(report["images"].items())
        random_generator.shuffle(candidates)
        for stem, image_path in candidates[:args.preview_count]:
            label_path = report["labels"].get(stem, Path())
            output_path = preview_directory / f"{split}_{image_path.name}"
            draw_preview(image_path, label_path, output_path, class_names)
        print(f"{split}: đã tạo tối đa {min(args.preview_count, len(candidates))} preview trong {preview_directory}")

    yaml_path = dataset_directory / "data.yaml"
    if args.write_yaml:
        yaml_path = write_data_yaml(dataset_directory)
        print(f"Đã ghi cấu hình chuẩn: {yaml_path}")
    elif yaml_path.is_file():
        print(f"data.yaml hiện có: {yaml_path} (chưa ghi đè; dùng --write-yaml để ghi cấu hình chuẩn)")
    else:
        print("Chưa có data.yaml; dùng --write-yaml để tạo file cấu hình chuẩn.")

    print("Hoàn tất kiểm tra. Dataset và label gốc không bị di chuyển.")


if __name__ == "__main__":
    main()