"""Run K-Means analysis on counting data to classify traffic density."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.traffic_kmeans import TrafficKMeansAnalyzer


def load_rows(source: Path):
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source).to_dict(orient="records")
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "crossings" in payload:
            return payload["crossings"]
        if isinstance(payload, list):
            return payload
        raise ValueError("JSON đầu vào phải là danh sách hoặc object chứa key 'crossings'.")
    raise ValueError("Source phải là .csv hoặc .json.")


def main():
    project_root = PROJECT_ROOT
    parser = argparse.ArgumentParser(description="Phân tích lưu lượng bằng K-Means.")
    parser.add_argument(
        "--source",
        type=Path,
        default=project_root / "runs" / "counting" / "counting_summary.csv",
        help="Tệp CSV/JSON chứa dữ liệu đếm phương tiện đã được ghi ra từ counting.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "runs" / "traffic_analysis",
        help="Thư mục chứa feature, model và mapping K-Means.",
    )
    parser.add_argument("--window-seconds", type=int, default=10)
    parser.add_argument("--k-clusters", type=int, default=3)
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"Không tìm thấy dữ liệu đầu vào: {args.source}")

    rows = load_rows(args.source)
    analyzer = TrafficKMeansAnalyzer(window_seconds=args.window_seconds, k_clusters=args.k_clusters)
    features = analyzer.prepare_features(rows)
    if features.empty:
        raise SystemExit("Dữ liệu đầu vào không có dữ liệu thời gian hợp lệ để phân tích.")

    analyzer.fit(features)
    predicted = analyzer.predict(features)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    features_path = output_dir / "traffic_features.csv"
    predicted_path = output_dir / "traffic_statuses.csv"
    model_path = output_dir / "traffic_kmeans_model.pkl"
    mapping_path = output_dir / "cluster_mapping.json"

    features.to_csv(features_path, index=False)
    predicted[["window_start", "total_count", "density", "status"]].to_csv(predicted_path, index=False)
    analyzer.save(model_path)
    analyzer.export_mapping(mapping_path)

    print("\nK-MEANS TRAFFIC ANALYSIS")
    print(f"Input: {args.source}")
    print(f"Output: {output_dir}")
    print(f"Window: {args.window_seconds}s, K={args.k_clusters}")
    print("\nCluster mapping:")
    for cluster_id, label in sorted(analyzer.cluster_mapping.items()):
        density_mean = analyzer.cluster_centers[cluster_id]["density_mean"]
        print(f"  cluster {cluster_id}: {label} (mật độ trung bình {density_mean:.2f})")

    status_counts = predicted["status"].value_counts().to_dict()
    print("\nStatus summary:")
    for label in ["Bình thường", "Đông", "Ùn tắc"]:
        print(f"  {label}: {status_counts.get(label, 0)}")

    print(f"\nĐã lưu model: {model_path}")
    print(f"Đã lưu mapping: {mapping_path}")


if __name__ == "__main__":
    main()
