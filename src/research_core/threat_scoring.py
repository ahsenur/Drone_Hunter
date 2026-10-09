from __future__ import annotations

from typing import Iterable, List

from integration import TargetEvent
from research_core.mission_profiles import MissionProfile


class ThreatScorer:
    """
    2209 icin ozgun katkilarin merkezinde yer alabilecek basit ama acik bir
    tehdit skorlama modeli.

    Amaç:
    - tek sensor yerine coklu algi skorunu birlestirmek
    - hedef yakinligi ve sensor cesitliligini dikkate almak
    - dusuk maliyetli prototipte yorumlanabilir karar uretmek
    """

    def __init__(self, profile: MissionProfile, aggregation: str = "mean") -> None:
        """
        aggregation:
          "mean"     (varsayilan, onceki davranis): olay skorlarinin ortalamasi + cesitlilik bonusu.
                     Zayif bir sensor eklemek guclu bir tespitin skorunu dusurebilir.
          "noisy_or" : 1 - carpim(1 - s_i). Birbirini dogrulayan sensorler skoru yukseltir,
                     zayif sensor skoru dusurmez; bedeli yanlis alarmlarin da birikebilmesidir.
        """
        if aggregation not in ("mean", "noisy_or"):
            raise ValueError(f"bilinmeyen aggregation: {aggregation}")
        self.profile = profile
        self.aggregation = aggregation

    def score_events(self, events: Iterable[TargetEvent]) -> float:
        event_list: List[TargetEvent] = [event for event in events if event.target_detected]
        if not event_list:
            return 0.0

        if self.aggregation == "noisy_or":
            miss = 1.0
            for event in event_list:
                miss *= 1.0 - self._score_single(event)
            return min(1.0, 1.0 - miss)

        total = 0.0
        for event in event_list:
            total += self._score_single(event)

        diversity_bonus = min(0.15, 0.05 * len({event.source for event in event_list}))
        return min(1.0, total / len(event_list) + diversity_bonus)

    def classify(self, score: float) -> str:
        if score >= 0.85:
            return "critical"
        if score >= self.profile.alert_threshold:
            return "high"
        if score >= self.profile.track_threshold:
            return "medium"
        return "low"

    def _score_single(self, event: TargetEvent) -> float:
        source_weight = {
            "radar": self.profile.radar_weight,
            "vision": self.profile.vision_weight,
            "acoustic": self.profile.acoustic_weight,
            "thermal": 1.05,
            "fusion": 1.0,
        }.get(event.source, 1.0)

        confidence_term = event.confidence * 0.65
        distance_term = 0.0
        if event.distance_m is not None:
            # Daha yakin hedef daha riskli kabul edilir.
            distance_term = max(0.0, min(1.0, (60.0 - event.distance_m) / 60.0)) * 0.35

        return min(1.0, (confidence_term + distance_term) * source_weight)
