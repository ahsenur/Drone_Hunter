from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from integration import TargetEvent, build_target_event
from integration.fusion.fusion_center import FusionCenter
from research_core.friend_foe_classifier import FriendFoeClassifier
from research_core.mission_profiles import MissionProfile
from research_core.resilience_manager import ResilienceManager
from research_core.threat_scoring import ThreatScorer


@dataclass
class PipelineResult:
    fused_event: TargetEvent
    command: Dict[str, object]
    threat_score: float
    operating_mode: str
    friend_foe_label: str
    friend_foe_reason: str
    resilience_mode: str
    resilience_notes: str
    stale_sources: Optional[list] = None
    sensor_status: Optional[Dict[str, str]] = None


class MultiSensorPipeline:
    """
    Radar + kamera + akustik veriyi 2209 odakli, yorumlanabilir bir akisa sokar.
    """

    def __init__(
        self,
        profile: MissionProfile,
        classifier: FriendFoeClassifier | None = None,
        aggregation: str = "mean",
    ) -> None:
        self.profile = profile
        self.fusion = FusionCenter()
        self.scorer = ThreatScorer(profile, aggregation=aggregation)
        self.classifier = classifier or FriendFoeClassifier()
        self.resilience = ResilienceManager()

    def process(
        self,
        radar_event: Optional[TargetEvent] = None,
        vision_event: Optional[TargetEvent] = None,
        acoustic_event: Optional[TargetEvent] = None,
        thermal_event: Optional[TargetEvent] = None,
        sensor_status: Optional[Dict[str, str]] = None,
        now: Optional[float] = None,
        max_age_s: Optional[Dict[str, float]] = None,
    ) -> PipelineResult:
        # Bayat olaylar (zaman damgasi kaynak TTL'ini asan) tum zincirden cikarilir.
        fresh, stale_sources, ages = self.fusion.drop_stale(
            {"radar": radar_event, "vision": vision_event, "acoustic": acoustic_event, "thermal": thermal_event},
            now=now,
            max_age_s=max_age_s,
        )
        # Bayat radar satirindaki anahtar kelime alarmi kalici tutmasin diye resilience'a
        # yalnizca taze olay verilir; kalici sessizlik heartbeat zaman asimiyla yakalanir.
        radar_event = fresh["radar"]
        vision_event = fresh["vision"]
        acoustic_event = fresh["acoustic"]
        thermal_event = fresh["thermal"]
        sensor_status = dict(sensor_status or {})

        fused = self.fusion.fuse(
            radar_event=radar_event,
            vision_event=vision_event,
            acoustic_event=acoustic_event,
            thermal_event=thermal_event,
        )

        active_events = [event for event in (radar_event, vision_event, acoustic_event, thermal_event) if event and event.target_detected]
        threat_score = self.scorer.score_events(active_events)
        classified = self.scorer.classify(threat_score)
        friend_foe = self.classifier.evaluate(fused)
        resilience_state = self.resilience.assess(
            radar_event, vision_event, acoustic_event, sensor_status=sensor_status
        )

        upgraded = build_target_event(
            source="fusion",
            target_detected=fused.target_detected,
            target_id=fused.target_id,
            angle_deg=fused.angle_deg,
            distance_m=fused.distance_m,
            confidence=max(fused.confidence, threat_score),
            threat_level=classified,
            metadata={
                **(fused.metadata or {}),
                "use_case": self.profile.use_case,
                "environment": self.profile.environment,
                "threat_score": threat_score,
                "friend_foe": friend_foe.label,
                "friend_score": friend_foe.friend_score,
                "foe_score": friend_foe.foe_score,
                "friend_foe_reason": friend_foe.reason,
                "resilience_mode": resilience_state.mode,
                "resilience_notes": resilience_state.notes,
                "resilience_trigger": resilience_state.trigger,
                "degraded_sources": resilience_state.degraded_sources or [],
                "stale_sources": stale_sources,
                "source_ages_s": ages,
                "sensor_status": sensor_status,
            },
        )

        command = self.fusion.build_command(upgraded)
        operating_mode = self._decide_operating_mode(radar_event, vision_event, acoustic_event, threat_score, thermal_event)
        command["mode"] = resilience_state.mode if resilience_state.jammer_suspected else operating_mode
        command["friend_foe"] = friend_foe.label
        command["resilience"] = resilience_state.mode
        command["degraded_sources"] = resilience_state.degraded_sources or []

        return PipelineResult(
            fused_event=upgraded,
            command=command,
            threat_score=threat_score,
            operating_mode=command["mode"],
            friend_foe_label=friend_foe.label,
            friend_foe_reason=friend_foe.reason,
            resilience_mode=resilience_state.mode,
            resilience_notes=resilience_state.notes,
            stale_sources=stale_sources,
            sensor_status=sensor_status,
        )

    def _decide_operating_mode(
        self,
        radar_event: Optional[TargetEvent],
        vision_event: Optional[TargetEvent],
        acoustic_event: Optional[TargetEvent],
        threat_score: float,
        thermal_event: Optional[TargetEvent] = None,
    ) -> str:
        if threat_score >= self.profile.alert_threshold:
            return "ALERT_TRACK"
        if thermal_event and thermal_event.target_detected and not vision_event:
            return "THERMAL_CUE"
        if radar_event and radar_event.target_detected and not vision_event:
            return "SCAN_TO_RADAR"
        if acoustic_event and acoustic_event.target_detected and not vision_event:
            return "ACOUSTIC_CUE"
        if vision_event and vision_event.target_detected:
            return "TRACK"
        return "IDLE"
