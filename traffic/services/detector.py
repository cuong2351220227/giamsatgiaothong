from __future__ import annotations

import json
from pathlib import Path


class VehicleDetectorService:
    """Read YOLO detection summaries from the project outputs when available."""

    def __init__(self, summary_path: str | Path | None = None):
        project_root = Path(__file__).resolve().parents[2]
        default_path = project_root / "runs" / "counting" / "counting_summary.json"
        self.summary_path = Path(summary_path) if summary_path else default_path

    def detect(self) -> dict:
        if not self.summary_path.exists():
            return {
                "car": 0,
                "motorcycle": 0,
                "bus": 0,
                "truck": 0,
                "total": 0,
            }

        payload = json.loads(self.summary_path.read_text(encoding="utf-8"))
        counts = payload.get("counts", {})
        return {
            "car": int(counts.get("car", 0)),
            "motorcycle": int(counts.get("motorcycle", 0)),
            "bus": int(counts.get("bus", 0)),
            "truck": int(counts.get("truck", 0)),
            "total": int(payload.get("total", sum(counts.values()))),
        }
