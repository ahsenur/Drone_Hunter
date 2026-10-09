from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from integration import TargetEvent
from research_core.target_history import HistoryDecision
from research_core.zone_risk import ZoneDecision


@dataclass
class FriendFoeDecision:
    label: str
    friend_score: float
    foe_score: float
    reason: str


class FriendFoeClassifier:
    """
    Mikroislemci sinifinda da yorumlanabilir kalabilecek kadar basit,
    agir model gerektirmeyen dost/dusman puanlama mantigi.
    """

    def __init__(
        self,
        friendly_labels: Iterable[str] | None = None,
        threat_labels: Iterable[str] | None = None,
        operator_zones: Sequence[str] | None = None,
        forbidden_zones: Sequence[str] | None = None,
        friend_threshold: float = 0.55,
        threat_threshold: float = 0.75,
        ambiguity_margin: float = 0.12,
    ) -> None:
        self.friendly_labels = {label.lower() for label in (friendly_labels or ["person", "operator", "staff"])}
        self.threat_labels = {label.lower() for label in (threat_labels or ["drone", "uav", "quadcopter"])}
        self.operator_zones = {zone.lower() for zone in (operator_zones or ["operator_zone", "safe_operator_zone"])}
        self.forbidden_zones = {zone.lower() for zone in (forbidden_zones or ["kritik_merkez", "yasak_bolge", "forbidden_zone"])}
        self.friend_threshold = friend_threshold
        self.threat_threshold = threat_threshold
        self.ambiguity_margin = ambiguity_margin

    def evaluate(
        self,
        event: TargetEvent,
        zone_decision: Optional[ZoneDecision] = None,
        history_decision: Optional[HistoryDecision] = None,
    ) -> FriendFoeDecision:
        label = event.target_id.lower()
        friend_score = 0.0
        foe_score = 0.0
        reasons: List[str] = []
        metadata = event.metadata or {}
        zone_label = str(metadata.get("zone", "general_area")).lower()
        source_count = int(metadata.get("source_count", 1))

        if label in self.friendly_labels:
            friend_score += 0.55
            reasons.append("etiket dost listesinde")
        elif label in self.threat_labels:
            foe_score += 0.55
            reasons.append("etiket tehdit listesinde")
        else:
            foe_score += 0.25
            friend_score += 0.05
            reasons.append("etiket bilinmeyen")

        if event.distance_m is not None and event.distance_m < 8:
            foe_score += 0.26
            reasons.append("cok yakin temas")
        elif event.distance_m is not None and event.distance_m < 15:
            foe_score += 0.20
            reasons.append("yakin temas")
        elif event.distance_m is not None and event.distance_m > 25 and label in self.friendly_labels:
            friend_score += 0.08
            reasons.append("uzak dost profili")

        if event.confidence > 0.80:
            foe_score += 0.15
            reasons.append("yuksek tespit guveni")
        elif event.confidence < 0.45:
            friend_score += 0.04
            reasons.append("dusuk guven, temkinli yorum")

        position = str((event.metadata or {}).get("position", "")).upper()
        if position in {"ORTA", "CENTER"}:
            foe_score += 0.10
            reasons.append("merkez eksene yakin")
        elif position in {"SOL", "SAG"} and label in self.friendly_labels:
            friend_score += 0.05
            reasons.append("yan koridorda dost profili")

        if event.source == "vision" and label in self.friendly_labels:
            friend_score += 0.20
            reasons.append("gorsel dogrulama")

        if event.source == "acoustic":
            foe_score += 0.10
            reasons.append("akustik destek")

        if event.source == "radar":
            foe_score += 0.10
            reasons.append("radar destek")

        if event.source == "thermal":
            foe_score += 0.18
            reasons.append("termal imza destek")

        if zone_decision is not None:
            foe_score += max(0.0, zone_decision.risk_bonus)
            reasons.append(f"bolge: {zone_decision.zone_label}")
            zone_label = zone_decision.zone_label.lower()

        if zone_label in self.operator_zones and label in self.friendly_labels:
            friend_score += 0.24
            reasons.append("operator bolgesinde dost gorulumu")
        elif zone_label in self.operator_zones and label in self.threat_labels:
            foe_score += 0.18
            reasons.append("operator bolgesine tehdit yaklasti")

        if zone_label in self.forbidden_zones:
            foe_score += 0.18
            reasons.append("yasak/kritik bolge ihlali")

        if history_decision is not None:
            foe_score += min(0.25, history_decision.approach_score)
            if history_decision.persistence_s > 3.0:
                foe_score += 0.08
            reasons.append(history_decision.note)
            if history_decision.persistence_s > 5.0 and label in self.friendly_labels and zone_label in self.operator_zones:
                friend_score += 0.08
                reasons.append("bolgede kalici dost davranisi")

        if source_count >= 2:
            foe_score += 0.10
            reasons.append("coklu sensor teyidi")
        if source_count >= 3 and label in self.threat_labels:
            foe_score += 0.08
            reasons.append("uc kaynaktan tehdit teyidi")

        if label in self.friendly_labels and source_count == 1 and zone_label in self.operator_zones:
            friend_score += 0.10
            reasons.append("tekil dost teyidi yeterli")

        if friend_score >= self.friend_threshold and (friend_score - foe_score) >= self.ambiguity_margin:
            final_label = "dost"
        elif foe_score >= self.threat_threshold:
            final_label = "tehdit"
        elif abs(foe_score - friend_score) < self.ambiguity_margin:
            final_label = "bilinmeyen"
        elif foe_score >= friend_score:
            final_label = "bilinmeyen"
        else:
            final_label = "dost"

        return FriendFoeDecision(
            label=final_label,
            friend_score=min(1.0, friend_score),
            foe_score=min(1.0, foe_score),
            reason=", ".join(reasons) if reasons else "kural uygulanmadi",
        )
