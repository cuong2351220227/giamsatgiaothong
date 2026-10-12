from __future__ import annotations

from typing import Any

from src.traffic_kmeans import TrafficKMeansAnalyzer


class KMeansTrafficClassifier:
    """Map traffic counts into density states using the project K-Means analyzer."""

    def __init__(self, window_seconds: int = 10, k_clusters: int = 3):
        self.window_seconds = int(window_seconds)
        self.k_clusters = int(k_clusters)

    def classify(
        self,
        counts: dict[str, Any],
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized = {
            "car": int(counts.get("car", 0)),
            "motorcycle": int(counts.get("motorcycle", 0)),
            "bus": int(counts.get("bus", 0)),
            "truck": int(counts.get("truck", 0)),
        }
        rows = list(events or [])
        if not rows:
            for vehicle_name, value in normalized.items():
                for index in range(value):
                    rows.append({
                        "track_id": f"{vehicle_name}-{index}",
                        "class_name": vehicle_name,
                        "timestamp": index * 0.5,
                        "frame_index": index * 5,
                    })

        if not rows:
            return {
                "status": "Bình thường",
                "status_label": "Bình thường",
                "cluster_mapping": {0: "Bình thường", 1: "Đông", 2: "Ùn tắc"},
                "density": 0.0,
            }

        analyzer = TrafficKMeansAnalyzer(window_seconds=self.window_seconds, k_clusters=self.k_clusters)
        features = analyzer.prepare_features(rows)
        if features.empty:
            return {
                "status": "Bình thường",
                "status_label": "Bình thường",
                "cluster_mapping": {},
                "density": 0.0,
            }

        distinct_features = features[analyzer.feature_columns].drop_duplicates().shape[0]
        analyzer.k_clusters = min(analyzer.k_clusters, max(1, distinct_features))
        analyzer.fit(features)
        predicted = analyzer.predict(features)
        latest_status = predicted["status"].iloc[-1] if not predicted.empty else "Bình thường"
        density = float(predicted["density"].mean()) if not predicted.empty else 0.0
        return {
            "status": latest_status,
            "status_label": latest_status,
            "cluster_mapping": analyzer.cluster_mapping,
            "density": density,
        }
