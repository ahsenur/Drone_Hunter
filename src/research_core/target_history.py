from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Dict, Optional


@dataclass
class HistoryDecision:
    persistence_s: float
    approach_score: float
    note: str


class TargetHistoryTracker:
    """
    Hedefin zaman icindeki davranisini kaba ama yorumlanabilir bicimde izler.
    """

    def __init__(self) -> None:
        self._history: Dict[str, Dict[str, float]] = {}

    def update(self, target_id: str, distance_m: Optional[float]) -> HistoryDecision:
        now = time.time()
        item = self._history.get(target_id)
        if item is None:
            self._history[target_id] = {
                "first_seen": now,
                "last_seen": now,
                "last_distance": float(distance_m) if distance_m is not None else -1.0,
            }
            return HistoryDecision(
                persistence_s=0.0,
                approach_score=0.0,
                note="ilk gorulum",
            )

        persistence_s = now - item["first_seen"]
        approach_score = 0.0
        if distance_m is not None and item["last_distance"] > 0:
            if float(distance_m) < item["last_distance"]:
                delta = item["last_distance"] - float(distance_m)
                approach_score = min(1.0, delta / 10.0)

        item["last_seen"] = now
        if distance_m is not None:
            item["last_distance"] = float(distance_m)

        note = "yaklasma yok"
        if approach_score > 0.0:
            note = "hedef yaklasiyor"
        elif persistence_s > 3.0:
            note = "hedef surekli sahada"

        return HistoryDecision(
            persistence_s=persistence_s,
            approach_score=approach_score,
            note=note,
        )
