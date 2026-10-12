from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

STATUS_LABELS = ["Bình thường", "Đông", "Ùn tắc"]
DEFAULT_FEATURE_COLUMNS = [
    "total_count",
    "density",
    "volume_change",
    "car_ratio",
    "motorcycle_ratio",
    "bus_ratio",
    "truck_ratio",
]


class TrafficKMeansAnalyzer:
    """Prepare traffic counts, train K-Means, and map clusters to traffic states."""

    def __init__(self, window_seconds: int = 10, k_clusters: int = 3, random_state: int = 42):
        if window_seconds <= 0:
            raise ValueError("window_seconds phải lớn hơn 0.")
        if k_clusters <= 0:
            raise ValueError("k_clusters phải lớn hơn 0.")

        self.window_seconds = int(window_seconds)
        self.k_clusters = int(k_clusters)
        self.n_clusters = self.k_clusters
        self.random_state = int(random_state)
        self.feature_columns = list(DEFAULT_FEATURE_COLUMNS)
        self.scaler: StandardScaler | None = None
        self.model: KMeans | None = None
        self.cluster_mapping: dict[int, str] = {}
        self.cluster_centers: dict[int, dict[str, float]] = {}

    @staticmethod
    def _canonical_vehicle_name(value: Any) -> str:
        return str(value).strip().lower().replace("motorbike", "motorcycle")

    def _normalize_rows(self, rows: Iterable[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
        if isinstance(rows, pd.DataFrame):
            frame = rows.copy()
        else:
            frame = pd.DataFrame(rows)

        if frame.empty:
            return pd.DataFrame(columns=["window_start", "total_count", "density", "volume_change", "car_ratio", "motorcycle_ratio", "bus_ratio", "truck_ratio"])

        if "timestamp" not in frame.columns:
            raise ValueError("Dữ liệu đầu vào phải có cột 'timestamp' để tính theo thời gian.")

        frame = frame.copy()
        frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
        frame = frame.dropna(subset=["timestamp"]).copy()
        if frame.empty:
            return frame

        frame["class_name"] = frame.get("class_name", "").map(self._canonical_vehicle_name)
        frame["window_start"] = (frame["timestamp"] // self.window_seconds) * self.window_seconds
        vehicle_classes = ["car", "motorcycle", "bus", "truck"]

        aggregated = (
            frame.groupby("window_start", as_index=True)
            .agg(
                total_count=("track_id", "count"),
                car_count=("class_name", lambda column: int((column == "car").sum())),
                motorcycle_count=("class_name", lambda column: int((column == "motorcycle").sum())),
                bus_count=("class_name", lambda column: int((column == "bus").sum())),
                truck_count=("class_name", lambda column: int((column == "truck").sum())),
            )
            .reset_index()
            .rename(columns={"window_start": "window_start"})
        )

        aggregated["density"] = aggregated["total_count"] / max(self.window_seconds, 1)
        aggregated["volume_change"] = aggregated["total_count"].diff().fillna(0.0)

        for vehicle_name in vehicle_classes:
            column_name = f"{vehicle_name}_ratio"
            aggregated[column_name] = aggregated[f"{vehicle_name.split()[0]}_count"] / aggregated["total_count"].replace(0, 1)
        aggregated["car_ratio"] = aggregated["car_count"] / aggregated["total_count"].replace(0, 1)
        aggregated["motorcycle_ratio"] = aggregated["motorcycle_count"] / aggregated["total_count"].replace(0, 1)
        aggregated["bus_ratio"] = aggregated["bus_count"] / aggregated["total_count"].replace(0, 1)
        aggregated["truck_ratio"] = aggregated["truck_count"] / aggregated["total_count"].replace(0, 1)

        return aggregated[[
            "window_start",
            "total_count",
            "density",
            "volume_change",
            "car_ratio",
            "motorcycle_ratio",
            "bus_ratio",
            "truck_ratio",
        ]]

    def prepare_features(self, rows: Iterable[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
        """Create the feature table used by K-Means from raw vehicle events."""
        return self._normalize_rows(rows)

    def fit(self, features: pd.DataFrame | Iterable[dict[str, Any]]) -> dict[int, str]:
        feature_frame = features if isinstance(features, pd.DataFrame) else self.prepare_features(features)
        if feature_frame.empty:
            raise ValueError("Không có dữ liệu đủ để huấn luyện K-Means.")

        feature_matrix = feature_frame[self.feature_columns].fillna(0.0)
        self.scaler = StandardScaler()
        scaled = self.scaler.fit_transform(feature_matrix)

        self.k_clusters = int(self.k_clusters)
        self.n_clusters = self.k_clusters
        self.model = KMeans(n_clusters=self.k_clusters, random_state=self.random_state, n_init=10)
        labels = self.model.fit_predict(scaled)

        cluster_centers = {}
        for cluster_id in range(self.k_clusters):
            cluster_rows = feature_frame.loc[labels == cluster_id]
            if cluster_rows.empty:
                density_mean = 0.0
            else:
                density_mean = float(cluster_rows["density"].mean())
            cluster_centers[cluster_id] = {
                "density_mean": density_mean,
                "total_mean": float(cluster_rows["total_count"].mean()) if not cluster_rows.empty else 0.0,
            }

        self.cluster_centers = cluster_centers
        ordered = sorted(cluster_centers.items(), key=lambda item: item[1]["density_mean"])
        cluster_mapping = {}
        for index, (cluster_id, _) in enumerate(ordered):
            cluster_mapping[cluster_id] = STATUS_LABELS[min(index, len(STATUS_LABELS) - 1)]
        self.cluster_mapping = cluster_mapping
        return self.cluster_mapping

    def predict(self, features: pd.DataFrame | Iterable[dict[str, Any]]) -> pd.DataFrame:
        if self.model is None or self.scaler is None:
            raise ValueError("Model K-Means chưa được huấn luyện. Hãy gọi fit() trước.")

        feature_frame = features if isinstance(features, pd.DataFrame) else self.prepare_features(features)
        if feature_frame.empty:
            return feature_frame.copy()

        matrix = feature_frame[self.feature_columns].fillna(0.0)
        scaled = self.scaler.transform(matrix)
        labels = self.model.predict(scaled)
        result = feature_frame.copy()
        result["cluster_id"] = labels
        result["status"] = result["cluster_id"].map(self.cluster_mapping)
        return result

    def save(self, model_path: str | Path):
        target = Path(model_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "window_seconds": self.window_seconds,
            "k_clusters": self.k_clusters,
            "random_state": self.random_state,
            "feature_columns": self.feature_columns,
            "model": self.model,
            "scaler": self.scaler,
            "cluster_mapping": self.cluster_mapping,
            "cluster_centers": self.cluster_centers,
        }
        with target.open("wb") as handle:
            pickle.dump(payload, handle)
        return target

    @classmethod
    def load(cls, model_path: str | Path) -> "TrafficKMeansAnalyzer":
        with Path(model_path).open("rb") as handle:
            payload = pickle.load(handle)

        analyzer = cls(
            window_seconds=int(payload["window_seconds"]),
            k_clusters=int(payload["k_clusters"]),
            random_state=int(payload["random_state"]),
        )
        analyzer.feature_columns = list(payload.get("feature_columns", DEFAULT_FEATURE_COLUMNS))
        analyzer.model = payload.get("model")
        analyzer.scaler = payload.get("scaler")
        analyzer.cluster_mapping = payload.get("cluster_mapping", {})
        analyzer.cluster_centers = payload.get("cluster_centers", {})
        return analyzer

    def export_mapping(self, output_path: str | Path) -> dict[str, Any]:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cluster_mapping": {str(cluster_id): label for cluster_id, label in self.cluster_mapping.items()},
            "cluster_centers": {str(cluster_id): values for cluster_id, values in self.cluster_centers.items()},
            "status_order": STATUS_LABELS,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload


def main():
    analyzer = TrafficKMeansAnalyzer(window_seconds=10, k_clusters=3)
    sample = [
        {"track_id": 1, "class_name": "car", "timestamp": 0.0, "frame_index": 0},
        {"track_id": 2, "class_name": "car", "timestamp": 1.0, "frame_index": 5},
        {"track_id": 3, "class_name": "car", "timestamp": 2.0, "frame_index": 10},
        {"track_id": 4, "class_name": "motorcycle", "timestamp": 3.0, "frame_index": 15},
    ]
    features = analyzer.prepare_features(sample)
    analyzer.fit(features)
    print(analyzer.cluster_mapping)


if __name__ == "__main__":
    main()
