from __future__ import annotations

from dataclasses import dataclass, asdict
import time
from typing import Any, Dict, Optional


VALID_SOURCES = {"radar", "vision", "acoustic", "thermal", "fusion"}


@dataclass
class TargetEvent:
    source: str
    target_detected: bool
    target_id: str
    angle_deg: Optional[float]
    distance_m: Optional[float]
    confidence: float
    threat_level: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def now_ts() -> float:
    return time.time()


def clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in VALID_SOURCES else "fusion"


def build_target_event(
    source: str,
    target_detected: bool,
    target_id: str = "unknown",
    angle_deg: Optional[float] = None,
    distance_m: Optional[float] = None,
    confidence: float = 0.0,
    threat_level: str = "low",
    timestamp: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TargetEvent:
    return TargetEvent(
        source=normalize_source(source),
        target_detected=bool(target_detected),
        target_id=str(target_id or "unknown"),
        angle_deg=float(angle_deg) if angle_deg is not None else None,
        distance_m=float(distance_m) if distance_m is not None else None,
        confidence=clamp_confidence(confidence),
        threat_level=str(threat_level or "low").lower(),
        timestamp=float(timestamp) if timestamp is not None else now_ts(),
        metadata=metadata or {},
    )


def event_from_dict(payload: Dict[str, Any]) -> TargetEvent:
    return build_target_event(
        source=payload.get("source", "fusion"),
        target_detected=payload.get("target_detected", False),
        target_id=payload.get("target_id", "unknown"),
        angle_deg=payload.get("angle_deg"),
        distance_m=payload.get("distance_m"),
        confidence=payload.get("confidence", 0.0),
        threat_level=payload.get("threat_level", "low"),
        timestamp=payload.get("timestamp"),
        metadata=payload.get("metadata", {}),
    )
