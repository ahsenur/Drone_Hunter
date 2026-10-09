from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional, Sequence, Union

from integration import TargetEvent, build_target_event, clamp_confidence, event_from_dict


EventLike = Union[TargetEvent, Dict]

# Kaynak basina azami olay yasi (saniye). Degerler orchestrator config'indeki
# track_ttl_s degerleriyle uyumludur (radar 3.0, akustik 1.2).
DEFAULT_MAX_AGE_S = {"radar": 3.0, "vision": 1.0, "acoustic": 1.2, "thermal": 1.0}


class FusionCenter:
    """
    Radar, kamera ve akustik veriyi tek karara indirger.

    Bu sinif mevcut projeye dogrudan baglanmak zorunda degildir.
    Disaridan gelen event'leri normalize edip tek cikti uretir.
    """

    SOURCE_WEIGHTS = {
        "radar": 1.0,
        "vision": 1.2,
        "acoustic": 0.8,
        "thermal": 1.0,
    }

    def _normalize_event(self, event: Optional[EventLike]) -> Optional[TargetEvent]:
        if event is None:
            return None
        if isinstance(event, TargetEvent):
            return event
        if isinstance(event, dict):
            return event_from_dict(event)
        raise TypeError(f"Desteklenmeyen event tipi: {type(event)!r}")

    def drop_stale(
        self,
        named_events: Dict[str, Optional[EventLike]],
        now: Optional[float] = None,
        max_age_s: Optional[Dict[str, float]] = None,
    ):
        """
        Zaman damgasi kaynaga gore izin verilen yasi asan olaylari eler.
        Doner: (taze_olaylar: {kaynak: TargetEvent|None}, bayat_kaynaklar: [kaynak], yaslar: {kaynak: sn})
        """
        limits = {**DEFAULT_MAX_AGE_S, **(max_age_s or {})}
        now = time.time() if now is None else float(now)
        fresh: Dict[str, Optional[TargetEvent]] = {}
        stale: List[str] = []
        ages: Dict[str, float] = {}
        for name, raw in named_events.items():
            event = self._normalize_event(raw)
            if event is None:
                fresh[name] = None
                continue
            age = max(0.0, now - event.timestamp)
            ages[name] = round(age, 3)
            if age > limits.get(name, 3.0):
                fresh[name] = None
                stale.append(name)
            else:
                fresh[name] = event
        return fresh, stale, ages

    def _weighted_angle(self, events: Sequence[TargetEvent]) -> Optional[float]:
        usable = [e for e in events if e.angle_deg is not None]
        if not usable:
            return None

        total_weight = 0.0
        weighted_sum = 0.0
        for event in usable:
            weight = self.SOURCE_WEIGHTS.get(event.source, 1.0) * max(event.confidence, 0.1)
            total_weight += weight
            weighted_sum += event.angle_deg * weight

        return weighted_sum / total_weight if total_weight else None

    def _nearest_distance(self, events: Sequence[TargetEvent]) -> Optional[float]:
        distances = [e.distance_m for e in events if e.distance_m is not None]
        return min(distances) if distances else None

    def _threat_level(self, events: Sequence[TargetEvent]) -> str:
        levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        if not events:
            return "low"
        max_level = max(levels.get(event.threat_level, 1) for event in events)
        reverse = {value: key for key, value in levels.items()}
        return reverse[max_level]

    def fuse(
        self,
        radar_event: Optional[EventLike] = None,
        vision_event: Optional[EventLike] = None,
        acoustic_event: Optional[EventLike] = None,
        thermal_event: Optional[EventLike] = None,
    ) -> TargetEvent:
        events: List[TargetEvent] = [
            event
            for event in (
                self._normalize_event(radar_event),
                self._normalize_event(vision_event),
                self._normalize_event(acoustic_event),
                self._normalize_event(thermal_event),
            )
            if event is not None and event.target_detected
        ]

        if not events:
            return build_target_event(
                source="fusion",
                target_detected=False,
                target_id="none",
                confidence=0.0,
                threat_level="low",
                metadata={"active_sources": []},
            )

        angle_deg = self._weighted_angle(events)
        distance_m = self._nearest_distance(events)
        confidence = clamp_confidence(sum(event.confidence for event in events) / len(events))
        threat_level = self._threat_level(events)
        strongest = max(events, key=lambda item: item.confidence)

        return build_target_event(
            source="fusion",
            target_detected=True,
            target_id=strongest.target_id,
            angle_deg=angle_deg,
            distance_m=distance_m,
            confidence=confidence,
            threat_level=threat_level,
            metadata={
                "active_sources": [event.source for event in events],
                "source_count": len(events),
            },
        )

    def build_command(self, fused_event: EventLike) -> Dict[str, object]:
        event = self._normalize_event(fused_event)
        if event is None:
            raise ValueError("Fused event bos olamaz.")

        mode = "IDLE"
        if event.target_detected:
            mode = "TRACK"
            if event.threat_level in {"high", "critical"}:
                mode = "ALERT_TRACK"

        return {
            "mode": mode,
            "target_detected": event.target_detected,
            "angle_deg": int(round(event.angle_deg)) if event.angle_deg is not None else None,
            "threat_level": event.threat_level,
            "confidence": event.confidence,
            "target_id": event.target_id,
            "metadata": event.metadata or {},
        }
