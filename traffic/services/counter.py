from __future__ import annotations

import csv
import json
from pathlib import Path


class TrafficCounterService:
    """Read or normalize counting output from JSON or CSV files."""

    def __init__(self, source: str | Path | None = None):
        project_root = Path(__file__).resolve().parents[2]
        default_path = project_root / "runs" / "counting" / "counting_summary.csv"
        self.source = Path(source) if source else default_path

    def read(self) -> dict:
        if not self.source.exists():
            return {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "total": 0}

        if self.source.suffix.lower() == ".json":
            payload = json.loads(self.source.read_text(encoding="utf-8"))
            counts = payload.get("counts", {})
            return {
                "car": int(counts.get("car", 0)),
                "motorcycle": int(counts.get("motorcycle", 0)),
                "bus": int(counts.get("bus", 0)),
                "truck": int(counts.get("truck", 0)),
                "total": int(payload.get("total", sum(counts.values()))),
            }

        with self.source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            counts = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0}
            for row in reader:
                class_name = str(row.get("class_name", "")).strip().lower()
                if class_name in counts:
                    counts[class_name] += 1
            total = sum(counts.values())
            return {**counts, "total": total}
