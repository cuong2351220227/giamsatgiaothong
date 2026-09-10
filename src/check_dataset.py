"""Check a YOLO object-detection dataset without changing any files."""

import argparse
import ast
import math
from collections import Counter
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
REQUIRED_CLASSES = ["car", "motorcycle", "bus", "truck"]


def read_data_yaml(yaml_path):
    """Read the simple fields used by a YOLO data.yaml file."""
    values = {}
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()

    names = ast.literal_eval(values.get("names", "[]"))
    if isinstance(names, dict):
        names = [names[str(index)] for index in range(len(names))]
    if not isinstance(names, list):
        raise ValueError("Trường names trong data.yaml phải là một danh sách.")

    result = {"names": [str(name) for name in names]}
    for split in ("train", "val", "valid", "test"):
        if split in values:
            result[split] = values[split].strip("'\"")
    if "nc" in values:
        result["nc"] = int(values["nc"])
    return result


def find_split_directories(dataset_root, yaml_values):
    """Resolve split image directories from data.yaml and common YOLO names."""
    split_directories = {}
    for split in ("train", "val", "valid", "test"):
        configured_path = yaml_values.get(split)
        if configured_path:
            image_directory = (dataset_root / "data.yaml").parent / configured_path
            image_directory = image_directory.resolve()
            if image_directory.is_dir():
                split_directories[split] = image_directory

    if "val" not in split_directories and "valid" in split_directories:
        split_directories["val"] = split_directories["valid"]

    for split in ("train", "val", "test"):
        if split not in split_directories:
            fallback_name = "valid" if split == "val" else split
            fallback = dataset_root / fallback_name / "images"
            if fallback.is_dir():
                split_directories[split] = fallback.resolve()
    return split_directories


def image_label_pairs(image_directory):
    labels_directory = image_directory.parent / "labels"
    images = {
        image.stem: image
        for image in image_directory.iterdir()
        if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS
    }
    labels = {
        label.stem: label
        for label in labels_directory.iterdir()
        if label.is_file() and label.suffix.lower() == ".txt"
    } if labels_directory.is_dir() else {}
    return images, labels, labels_directory


def check_split(split, image_directory, class_names):
    images, labels, labels_directory = image_label_pairs(image_directory)
    class_counts = Counter()
    errors = []
    invalid_rows = 0

    for stem, image_path in sorted(images.items()):
        label_path = labels.get(stem)
        if label_path is None:
            errors.append(f"Ảnh không có label: {image_path.relative_to(image_directory.parent.parent)}")
            continue

        for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            fields = line.split()
            if len(fields) != 5:
                errors.append(f"Sai format: {label_path.name}:{line_number} (cần 5 giá trị)")
                invalid_rows += 1
                continue
            try:
                class_id = int(fields[0])
                coordinates = [float(value) for value in fields[1:]]
            except ValueError:
                errors.append(f"Sai format số: {label_path.name}:{line_number}")
                invalid_rows += 1
                continue

            if class_id < 0 or class_id >= len(class_names):
                errors.append(f"Class ID không hợp lệ: {label_path.name}:{line_number} -> {class_id}")
                invalid_rows += 1
                continue
            if not all(math.isfinite(value) for value in coordinates):
                errors.append(f"Tọa độ không hữu hạn: {label_path.name}:{line_number}")
                invalid_rows += 1
                continue
            if not all(0 <= value <= 1 for value in coordinates):
                errors.append(f"Tọa độ ngoài [0, 1]: {label_path.name}:{line_number}")
                invalid_rows += 1
                continue
            if coordinates[2] <= 0 or coordinates[3] <= 0:
                errors.append(f"Kích thước bounding box không hợp lệ: {label_path.name}:{line_number}")
                invalid_rows += 1
                continue
            class_counts[class_id] += 1

    for stem, label_path in sorted(labels.items()):
        if stem not in images:
            errors.append(f"Label không có ảnh: {label_path.relative_to(labels_directory.parent.parent)}")

    return {
        "images": len(images),
        "labels": len(labels),
        "class_counts": class_counts,
        "invalid_rows": invalid_rows,
        "errors": errors,
    }


def print_dataset_tree(dataset_root):
    print("\nCẤU TRÚC DATASET")
    for path in sorted(dataset_root.rglob("*")):
        if path.is_dir() and path.relative_to(dataset_root).parts[-1] in {"images", "labels"}:
            print(f"  {path.relative_to(dataset_root)}/")
    print(f"  data.yaml: {'có' if (dataset_root / 'data.yaml').is_file() else 'không có'}")


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra dataset YOLO mà không sửa dữ liệu.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "external_dataset",
        help="Thư mục dataset (mặc định: data/external_dataset)",
    )
    args = parser.parse_args()
    dataset_root = args.dataset.resolve()
    yaml_path = dataset_root / "data.yaml"

    if not dataset_root.is_dir():
        raise SystemExit(f"Không tìm thấy thư mục dataset: {dataset_root}")
    if not yaml_path.is_file():
        raise SystemExit(f"Không tìm thấy data.yaml: {yaml_path}")

    yaml_values = read_data_yaml(yaml_path)
    class_names = yaml_values["names"]
    split_directories = find_split_directories(dataset_root, yaml_values)

    print_dataset_tree(dataset_root)
    print("\nĐỊNH DẠNG")
    print("  YOLO object detection (mỗi dòng label: class_id x_center y_center width height)")
    print(f"  data.yaml: {yaml_path}")
    print(f"  nc khai báo: {yaml_values.get('nc', 'không có')}")
    print(f"  names: {class_names}")
    print("  Đường dẫn split:")
    for split in ("train", "val", "test"):
        print(f"    {split}: {split_directories.get(split, 'không tìm thấy')}")

    print("\nCLASS VÀ MỨC ĐỘ PHÙ HỢP")
    for class_id, name in enumerate(class_names):
        print(f"  {class_id} = {name}")
    normalized_names = {name.lower().replace("motorbike", "motorcycle") for name in class_names}
    missing = [name for name in REQUIRED_CLASSES if name not in normalized_names]
    if missing:
        print(f"  KẾT LUẬN: thiếu class phù hợp: {missing}")
    else:
        print("  KẾT LUẬN: đủ 4 loại phương tiện theo tên chuẩn.")
        print("  LƯU Ý: ID thực tế lấy theo data.yaml; không tự đổi sang thứ tự ID của đề tài.")

    reports = {}
    for split in ("train", "val", "test"):
        if split in split_directories:
            reports[split] = check_split(split, split_directories[split], class_names)

    print("\nTHỐNG KÊ ẢNH VÀ OBJECT")
    total_counts = Counter()
    for split in ("train", "val", "test"):
        report = reports.get(split)
        if report is None:
            print(f"  {split}: không có")
            continue
        total_counts.update(report["class_counts"])
        print(f"  {split}: {report['images']} ảnh, {report['labels']} label, {sum(report['class_counts'].values())} object hợp lệ")
    print("  Object theo class toàn dataset:")
    for class_id, name in enumerate(class_names):
        print(f"    {class_id} = {name}: {total_counts[class_id]}")

    print("\nKIỂM TRA LỖI ANNOTATION")
    all_errors = []
    for split, report in reports.items():
        print(f"  {split}: {len(report['errors'])} lỗi, {report['invalid_rows']} dòng annotation không hợp lệ")
        all_errors.extend((split, error) for error in report["errors"])
    if all_errors:
        print("  Chi tiết:")
        for split, error in all_errors:
            print(f"    [{split}] {error}")
    else:
        print("  Không phát hiện lỗi annotation trong các split đã tìm thấy.")
    print("\nKhông có file nào bị sửa, xóa hoặc di chuyển.")


if __name__ == "__main__":
    main()