from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, Optional


@dataclass
class MissionProfile:
    name: str
    use_case: str
    environment: str
    acoustic_weight: float
    radar_weight: float
    vision_weight: float
    alert_threshold: float
    track_threshold: float


def load_profile(path: str | Path) -> MissionProfile:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data: Dict[str, object] = json.load(handle)
    return MissionProfile(
        name=str(data.get("name", "kampus_profili")),
        use_case=str(data.get("use_case", "kampus_cevre_gozetimi")),
        environment=str(data.get("environment", "outdoor")),
        acoustic_weight=float(data.get("acoustic_weight", 0.8)),
        radar_weight=float(data.get("radar_weight", 1.0)),
        vision_weight=float(data.get("vision_weight", 1.2)),
        alert_threshold=float(data.get("alert_threshold", 0.65)),
        track_threshold=float(data.get("track_threshold", 0.45)),
    )
