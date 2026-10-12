import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.traffic_kmeans import TrafficKMeansAnalyzer


class TrafficKMeansAnalyzerTests(unittest.TestCase):
    def test_cluster_mapping_and_status_labels(self):
        rows = [
            {"track_id": i, "class_name": "car", "timestamp": float(i), "frame_index": i * 10} for i in range(1, 31)
        ]
        rows.extend(
            [
                {"track_id": 100 + i, "class_name": "motorcycle", "timestamp": 100 + i, "frame_index": 1000 + i}
                for i in range(1, 21)
            ]
        )
        rows.extend(
            [
                {"track_id": 200 + i, "class_name": "truck", "timestamp": 200 + i, "frame_index": 2000 + i}
                for i in range(1, 21)
            ]
        )

        analyzer = TrafficKMeansAnalyzer(window_seconds=10, k_clusters=3)
        features = analyzer.prepare_features(rows)
        analyzer.fit(features)

        self.assertEqual(analyzer.n_clusters, 3)
        status_labels = set(analyzer.cluster_mapping.values())
        self.assertTrue({"Bình thường", "Đông", "Ùn tắc"}.issubset(status_labels))
        ordered = [
            analyzer.cluster_mapping[cluster_id]
            for cluster_id in sorted(
                analyzer.cluster_centers,
                key=lambda cluster_id: analyzer.cluster_centers[cluster_id]["density_mean"],
            )
        ]
        self.assertEqual(ordered[0], "Bình thường")
        self.assertEqual(ordered[1], "Đông")
        self.assertEqual(ordered[2], "Ùn tắc")


if __name__ == "__main__":
    unittest.main()
