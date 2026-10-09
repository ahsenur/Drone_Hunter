from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

from integration import TargetEvent, build_target_event
from integration.bridge.radar_bridge import RadarBridge
from integration.stm32_bridge.serial_bridge import STM32SerialBridge
from research_core import (
    FriendFoeClassifier,
    MultiSensorPipeline,
    HologramPanel,
    TargetHistoryTracker,
    ZoneRiskEvaluator,
    load_profile,
)
from research_core.sensor_health import SensorHealthMonitor
from thermal_engine import ThermalSignatureAnalyzer
from acoustic_engine.analyzer import AkustikMotor


class DemoOrchestrator:
    """
    Mevcut dosyalari degistirmeden gercek veriye yaklasan demo akisi.

    Bilesenler:
    - Radar: integration bridge uzerinden
    - Vision: YOLO kamera tespiti
    - Acoustic: mevcut analyzer modulu
    - Fusion: research_core pipeline
    - STM32: opsiyonel seri kopru
    """

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path).resolve()
        # config/research/orchestrator_config.json -> proje koku iki ust klasor
        self.project_root = self.config_path.parents[2]
        with self.config_path.open("r", encoding="utf-8") as handle:
            self.config = json.load(handle)

        self.health = SensorHealthMonitor()
        profile = load_profile(self._resolve(self.config["profile_path"]))
        classifier_cfg = self.config.get("classification", {})
        self.friend_foe_classifier = FriendFoeClassifier(
            friendly_labels=classifier_cfg.get("friendly_labels", ["person", "operator", "staff"]),
            threat_labels=classifier_cfg.get("threat_labels", ["drone", "uav", "quadcopter"]),
            operator_zones=classifier_cfg.get("operator_zones", ["operator_zone", "safe_operator_zone"]),
            forbidden_zones=classifier_cfg.get("forbidden_zones", ["kritik_merkez", "yasak_bolge", "forbidden_zone"]),
            friend_threshold=float(classifier_cfg.get("friend_threshold", 0.55)),
            threat_threshold=float(classifier_cfg.get("threat_threshold", 0.75)),
            ambiguity_margin=float(classifier_cfg.get("ambiguity_margin", 0.12)),
        )
        self.pipeline = MultiSensorPipeline(profile, classifier=self.friend_foe_classifier)
        self.zone_evaluator = ZoneRiskEvaluator(self.config.get("zones", []))
        self.history_tracker = TargetHistoryTracker()

        radar_cfg = self.config.get("radar", {})
        self.radar_bridge = RadarBridge(
            json_path=radar_cfg.get("json_path"),
            text_log_path=self._resolve(radar_cfg.get("text_log_path")),
            hyperbolic_baseline_m=float(radar_cfg.get("hyperbolic_baseline_m", 0.42)),
            delta_to_path_scale=float(radar_cfg.get("delta_to_path_scale", 0.00008)),
            delta_is_path_difference=bool(radar_cfg.get("delta_is_path_difference", False)),
        )
        self.radar_recent_limit = int(radar_cfg.get("recent_limit", 10))
        self.radar_track_ttl = float(radar_cfg.get("track_ttl_s", 3.0))
        self._last_radar_events: list[TargetEvent] = []

        self.vision_cfg = self.config.get("vision", {})
        self.model = YOLO(self._resolve(self.vision_cfg.get("model_path", "yolov8n.pt")))
        self.cap = cv2.VideoCapture(int(self.vision_cfg.get("camera_index", 0)), cv2.CAP_DSHOW)
        self.camera_available = self.cap.isOpened()
        self.frame_skip = max(1, int(self.vision_cfg.get("frame_skip", 2)))
        self.imgsz = int(self.vision_cfg.get("imgsz", 416))
        self._frame_index = 0
        self._last_vision_event: Optional[TargetEvent] = None
        self._last_detection_count = 0
        self._last_detections = []
        self._last_resilience_mode = "NORMAL"
        self._last_resilience_notes = "sistem normal calisiyor"
        self._last_friend_foe_reason = "karar bekleniyor"
        self._last_stm32_status = "devre disi"

        self.acoustic_enabled = bool(self.config.get("acoustic", {}).get("enabled", True))
        self.acoustic = AkustikMotor() if self.acoustic_enabled else None
        self.acoustic_poll_interval = float(self.config.get("acoustic", {}).get("poll_interval", 0.8))
        self.acoustic_track_ttl = float(self.config.get("acoustic", {}).get("track_ttl_s", 1.2))
        self._last_acoustic_event: Optional[TargetEvent] = None
        self._last_acoustic_events: list[TargetEvent] = []
        self._last_acoustic_update = 0.0
        self._stop_event = threading.Event()
        self._acoustic_thread: Optional[threading.Thread] = None

        self.stm32_enabled = bool(self.config.get("stm32", {}).get("enabled", False))
        self.stm32_bridge: Optional[STM32SerialBridge] = None
        if self.stm32_enabled:
            stm_cfg = self.config["stm32"]
            self.stm32_bridge = STM32SerialBridge(
                port=stm_cfg["port"],
                baudrate=int(stm_cfg.get("baudrate", 115200)),
            )

        self.last_radar_signature: Optional[str] = None
        self.thermal_cfg = self.config.get("thermal", {})
        self.thermal_enabled = bool(self.thermal_cfg.get("enabled", False))
        self.thermal_cap = None
        self.thermal_analyzer: Optional[ThermalSignatureAnalyzer] = None
        self._last_thermal_event: Optional[TargetEvent] = None
        self._last_aux_tracks: list[dict] = []
        self.display_cfg = self.config.get("display", {})
        self.window_name = "DroneHunter Research Orchestrator"
        self.hologram_window_name = "DroneHunter Hologram Tactical View"
        self.fullscreen = bool(self.display_cfg.get("fullscreen", False))
        self.target_height = int(self.display_cfg.get("target_height", 900))
        self.sidebar_width = int(self.display_cfg.get("sidebar_width", 520))
        self.hologram_enabled = bool(self.display_cfg.get("hologram_enabled", True))
        self.hologram_fullscreen = bool(self.display_cfg.get("hologram_fullscreen", False))
        self.hologram_panel = HologramPanel(
            width=int(self.display_cfg.get("hologram_width", 1280)),
            height=int(self.display_cfg.get("hologram_height", 720)),
            title=self.hologram_window_name,
        )
        if self.thermal_enabled:
            self.thermal_cap = cv2.VideoCapture(int(self.thermal_cfg.get("camera_index", 1)), cv2.CAP_DSHOW)
            self.thermal_analyzer = ThermalSignatureAnalyzer(
                hotspot_threshold=int(self.thermal_cfg.get("hotspot_threshold", 220)),
                min_area=int(self.thermal_cfg.get("min_area", 80)),
            )

    def _resolve(self, value):
        """Goreli yollari proje kokune gore cozer. Model adi (yolov8n.pt) dosya yoksa oldugu gibi kalir."""
        if value is None:
            return None
        path = Path(value)
        if path.is_absolute():
            return str(path)
        candidate = (self.project_root / path)
        return str(candidate) if candidate.exists() or path.parent != Path(".") else str(path)

    def run(self) -> None:
        if self.stm32_bridge is not None:
            try:
                self.stm32_bridge.connect()
                self._last_stm32_status = f"bagli: {self.stm32_bridge.port}"
            except Exception as exc:
                self._last_stm32_status = f"baglanti hatasi: {exc}"
                self.stm32_bridge = None
        if self.acoustic is not None:
            self._start_acoustic_worker()

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        if self.hologram_enabled:
            cv2.namedWindow(self.hologram_window_name, cv2.WINDOW_NORMAL)
            if self.hologram_fullscreen:
                cv2.setWindowProperty(self.hologram_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        try:
            print("[orchestrator] basladi. Cikis icin q")
            while True:
                vision_event, frame = self._read_vision_event()
                radar_event = self._read_radar_event()
                acoustic_event = self._read_acoustic_event()
                thermal_event = self._read_thermal_event()
                auxiliary_tracks = self._build_auxiliary_tracks(thermal_event)
                self._last_aux_tracks = auxiliary_tracks

                result = self.pipeline.process(
                    radar_event=radar_event,
                    vision_event=vision_event,
                    acoustic_event=acoustic_event,
                    thermal_event=thermal_event,
                    sensor_status=self.health.snapshot(),
                )

                if self.stm32_bridge is not None and result.command.get("target_detected"):
                    try:
                        sent = self.stm32_bridge.send_command(result.command)
                        self._last_stm32_status = f"komut gonderildi: {' | '.join(sent)}"
                    except Exception as exc:
                        self._last_stm32_status = f"gonderim hatasi: {exc}"

                display_frame = self._compose_display(
                    frame,
                    radar_event,
                    acoustic_event,
                    thermal_event,
                    result.command,
                    result.threat_score,
                    result.friend_foe_label,
                    result.friend_foe_reason,
                    result.resilience_mode,
                    result.resilience_notes,
                )
                self._last_resilience_mode = result.resilience_mode
                self._last_resilience_notes = result.resilience_notes
                self._last_friend_foe_reason = result.friend_foe_reason
                cv2.imshow(self.window_name, display_frame)

                if self.hologram_enabled:
                    hologram_frame = self.hologram_panel.render(
                        command=result.command,
                        threat_score=result.threat_score,
                        friend_foe=result.friend_foe_label,
                        friend_foe_reason=result.friend_foe_reason,
                        resilience_mode=result.resilience_mode,
                        resilience_notes=result.resilience_notes,
                        detections=self._last_detections,
                        auxiliary_tracks=auxiliary_tracks,
                        radar_event=radar_event,
                        acoustic_event=acoustic_event,
                        thermal_event=thermal_event,
                    )
                    cv2.imshow(self.hologram_window_name, hologram_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            self._stop_event.set()
            if self.cap is not None:
                self.cap.release()
            if self.thermal_cap is not None:
                self.thermal_cap.release()
            cv2.destroyAllWindows()
            if self.stm32_bridge is not None:
                self.stm32_bridge.disconnect()

    def _read_vision_event(self) -> tuple[Optional[TargetEvent], any]:
        if not self.camera_available or self.cap is None or not self.cap.isOpened():
            self.health.fault("vision", "kamera acilamadi / kapandi")
            self._last_detection_count = 0
            self._last_detections = []
            self._last_vision_event = None
            return None, self._make_placeholder_frame()

        ret, frame = self.cap.read()
        if not ret:
            self.camera_available = False
            self.health.fault("vision", "kare okunamadi")
            self._last_detection_count = 0
            self._last_detections = []
            self._last_vision_event = None
            return None, self._make_placeholder_frame()

        self.health.heartbeat("vision")   # kare alindi: sensor calisiyor (hedef olmasa da)
        self._frame_index += 1
        if self._frame_index % self.frame_skip != 0:
            self._draw_cached_detections(frame)
            return self._last_vision_event, frame

        results = self.model(
            frame,
            conf=float(self.vision_cfg.get("confidence", 0.4)),
            imgsz=self.imgsz,
            verbose=False,
        )
        if not results or len(results[0].boxes) == 0:
            self._last_detection_count = 0
            self._last_detections = []
            self._last_vision_event = None
            return None, frame

        candidates = []
        detections = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            cls_idx = int(box.cls[0])
            confidence = float(box.conf[0])
            label = self.model.names[cls_idx]
            area = float((x2 - x1) * (y2 - y1))
            center_x = (x1 + x2) / 2.0
            width = frame.shape[1]
            angle = (center_x / width) * 180.0
            distance_est = max(1.0, min(50.0, 50000.0 / max(area, 1.0)))

            priority = confidence + min(area / 40000.0, 0.5)
            position_tag = self._position_tag(center_x, frame.shape[1])
            x_ratio = center_x / max(frame.shape[1], 1)
            y_ratio = ((y1 + y2) / 2.0) / max(frame.shape[0], 1)
            zone_decision = self.zone_evaluator.evaluate_ratio(x_ratio, y_ratio)
            track_id = f"{label}_{int(center_x // 40)}"
            history_decision = self.history_tracker.update(track_id, distance_est)
            friend_foe = self.friend_foe_classifier.evaluate(
                build_target_event(
                    source="vision",
                    target_detected=True,
                    target_id=label,
                    angle_deg=float(angle),
                    distance_m=float(distance_est),
                    confidence=float(confidence),
                    threat_level="medium",
                    metadata={"position": position_tag, "bbox_area": area, "zone": zone_decision.zone_label},
                ),
                zone_decision=zone_decision,
                history_decision=history_decision,
            )
            detections.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2),
                    "center_x": float(center_x),
                    "angle": float(angle),
                    "distance": float(distance_est),
                    "position": position_tag,
                    "friend_foe": friend_foe.label,
                    "zone": zone_decision.zone_label,
                    "persistence": history_decision.persistence_s,
                    "approach": history_decision.approach_score,
                    "history_note": history_decision.note,
                    "reason": friend_foe.reason,
                    "selected": False,
                }
            )
            candidates.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "area": area,
                    "angle": angle,
                    "distance": distance_est,
                    "priority": priority,
                }
            )

        self._last_detection_count = len(candidates)
        self._last_detections = detections
        self._draw_cached_detections(frame)
        best = max(candidates, key=lambda item: item["priority"])
        for detection in self._last_detections:
            if detection["label"] == str(best["label"]) and abs(detection["angle"] - float(best["angle"])) < 0.6:
                detection["selected"] = True
                break
        self._last_vision_event = build_target_event(
            source="vision",
            target_detected=True,
            target_id=str(best["label"]),
            angle_deg=float(best["angle"]),
            distance_m=float(best["distance"]),
            confidence=float(best["confidence"]),
            threat_level="medium",
            metadata={
                "bbox_area": float(best["area"]),
                "detection_count": self._last_detection_count,
            },
        )
        return self._last_vision_event, frame

    def _read_radar_event(self) -> Optional[TargetEvent]:
        try:
            events = self.radar_bridge.load_recent_events_from_text(limit=self.radar_recent_limit)
        except Exception as exc:
            self.health.fault("radar", f"log okunamadi: {exc}")
            return None

        hb = self.radar_bridge.last_heartbeat_ts()
        if hb is not None:
            self.health.heartbeat("radar", now=hb)

        if not events:
            self._last_radar_events = []
            return None

        now = time.time()
        fresh_events = [event for event in events if (now - event.timestamp) <= self.radar_track_ttl]
        self._last_radar_events = self._dedupe_tracks(fresh_events)
        if not self._last_radar_events:
            return None
        # Olay TTL icinde oldugu surece her dongude verilir; suresi dolunca yukaridaki filtre eler.
        event = self._last_radar_events[-1]
        self.last_radar_signature = f"{event.target_id}|{event.angle_deg}|{event.distance_m}|{event.timestamp}"
        return event

    def _read_acoustic_event(self) -> Optional[TargetEvent]:
        return self._last_acoustic_event

    def _read_thermal_event(self) -> Optional[TargetEvent]:
        if not self.thermal_enabled or self.thermal_cap is None or self.thermal_analyzer is None:
            return None

        ret, frame = self.thermal_cap.read()
        if not ret:
            return self._last_thermal_event

        event, _ = self.thermal_analyzer.analyze_frame(frame)
        self._last_thermal_event = event
        return event

    def _start_acoustic_worker(self) -> None:
        if self.acoustic is None:
            return

        def _worker() -> None:
            while not self._stop_event.is_set():
                try:
                    threats, _ = self.acoustic.coklu_analiz_et()
                    if self.acoustic.last_error:
                        self.health.fault("acoustic", self.acoustic.last_error)
                    else:
                        self.health.heartbeat("acoustic")
                    if threats:
                        band_angle_map = {
                            "ARABA": 35.0,
                            "INSAN": 80.0,
                            "IHA": 120.0,
                            "ROKET_BENZERI": 155.0,
                        }
                        strongest = max(threats, key=lambda item: float(item.get("enerji", 0.0)))
                        strongest_band_label = str(strongest.get("band_label", "ACOUSTIC_TARGET"))
                        self._last_acoustic_event = build_target_event(
                            source="acoustic",
                            target_detected=True,
                            target_id=str(strongest.get("id", "acoustic_target")),
                            angle_deg=float(band_angle_map.get(str(strongest.get("band_label", "")), 90.0)),
                            distance_m=float(strongest.get("metre", 0.0)),
                            confidence=min(1.0, float(strongest.get("enerji", 0.0)) * 20.0),
                            threat_level="medium" if strongest.get("tip") == "SINYAL" else "high",
                            metadata={
                                "signature_type": strongest.get("tip", "unknown"),
                                "band_label": strongest_band_label,
                                "dominant_freq": strongest.get("dominant_freq"),
                                "sector_only": True,
                            },
                        )
                        self._last_acoustic_events = [self._last_acoustic_event]
                    else:
                        self._last_acoustic_event = None
                        self._last_acoustic_events = []
                    self._last_acoustic_update = time.time()
                except Exception as exc:
                    self.health.fault("acoustic", f"{type(exc).__name__}: {exc}")
                    self._last_acoustic_event = None
                    self._last_acoustic_events = []
                time.sleep(self.acoustic_poll_interval)

        self._acoustic_thread = threading.Thread(target=_worker, daemon=True)
        self._acoustic_thread.start()

    def _compose_display(self, frame, radar_event, acoustic_event, thermal_event, command, threat_score, friend_foe, friend_foe_reason, resilience_mode, resilience_notes):
        frame = self._resize_for_display(frame, self.target_height)
        info_panel = np.zeros((frame.shape[0], self.sidebar_width, 3), dtype=np.uint8)
        info_panel[:] = (34, 36, 40)
        self._draw_overlay(info_panel, radar_event, acoustic_event, thermal_event, command, threat_score, friend_foe, friend_foe_reason, resilience_mode, resilience_notes)
        return np.hstack((frame, info_panel))

    def _draw_overlay(self, panel, radar_event, acoustic_event, thermal_event, command, threat_score, friend_foe, friend_foe_reason, resilience_mode, resilience_notes) -> None:
        y = 74
        lines = [
            f"Mode: {command.get('mode')}",
            f"Threat score: {threat_score:.2f}",
            f"Friend/Foe: {friend_foe}",
            f"Resilience: {resilience_mode}",
            f"Command angle: {command.get('angle_deg')}",
            f"STM32: {self._last_stm32_status}",
            f"Radar tracks: {len(self._last_radar_events)}",
            f"Acoustic tracks: {len(self._last_acoustic_events)}",
            f"Thermal: {'var' if thermal_event else 'yok'}",
            f"Vision count: {self._last_detection_count}",
        ]
        for line in lines:
            cv2.putText(panel, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            y += 32

        detail_y = y + 8
        cv2.putText(panel, "Karar Nedeni:", (18, detail_y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (140, 220, 255), 1)
        detail_y += 22
        for chunk in self._wrap_text(friend_foe_reason, 46)[:3]:
            cv2.putText(panel, chunk, (18, detail_y), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)
            detail_y += 20

        list_y = detail_y + 14
        cv2.putText(panel, "Hedef Listesi", (18, list_y), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (140, 220, 255), 1)
        list_y += 26
        for index, detection in enumerate(self._last_detections[:5], start=1):
            text = (
                f"{index}. {detection['label']} | {detection['friend_foe']} | "
                f"{detection['position']} | {detection['zone']} | Aci {detection['angle']:.0f} | {detection['confidence']:.2f}"
            )
            color = self._friend_foe_color(detection["friend_foe"])
            if detection.get("selected"):
                cv2.rectangle(panel, (10, list_y - 16), (panel.shape[1] - 14, list_y + 10), (55, 70, 80), -1)
            cv2.putText(panel, text[:62], (18, list_y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 1)
            list_y += 22
            for chunk in self._wrap_text(str(detection.get("reason", "")), 48)[:2]:
                cv2.putText(panel, chunk, (28, list_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1)
                list_y += 18
            list_y += 6

        cv2.putText(
            panel,
            resilience_notes[:62],
            (18, min(panel.shape[0] - 30, list_y + 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (0, 255, 255),
            1,
        )
        if resilience_mode != "NORMAL":
            cv2.rectangle(panel, (0, 0), (panel.shape[1] - 1, 48), (0, 0, 120), -1)
            cv2.putText(
                panel,
                f"JAMMER / BOZULMA MODU: {resilience_mode}",
                (16, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (255, 255, 255),
                2,
            )
        else:
            cv2.rectangle(panel, (0, 0), (panel.shape[1] - 1, 48), (0, 90, 0), -1)
            cv2.putText(
                panel,
                "SISTEM DURUMU: NORMAL",
                (16, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (255, 255, 255),
                2,
            )

    def _build_auxiliary_tracks(self, thermal_event: Optional[TargetEvent]) -> list[dict]:
        tracks: list[dict] = []
        now = time.time()
        for event in self._last_radar_events[-self.radar_recent_limit:]:
            if not event.target_detected:
                continue
            tracks.append(self._event_to_track(event, zone="radar_only", friend_foe="tehdit", source_label="radar"))

        for event in self._last_acoustic_events:
            if not event.target_detected or (now - event.timestamp) > self.acoustic_track_ttl:
                continue
            metadata = event.metadata or {}
            tracks.append(
                self._event_to_track(
                    event,
                    zone=str(metadata.get("band_label", "acoustic_cue")).lower(),
                    friend_foe="bilinmeyen",
                    source_label="acoustic",
                    sector_only=bool(metadata.get("sector_only", True)),
                )
            )

        if thermal_event is not None and thermal_event.target_detected:
            tracks.append(self._event_to_track(thermal_event, zone="thermal_hotspot", friend_foe="tehdit", source_label="thermal"))
        return tracks

    @staticmethod
    def _dedupe_tracks(events: list[TargetEvent]) -> list[TargetEvent]:
        unique: list[TargetEvent] = []
        seen: set[tuple[str, int, int]] = set()
        for event in events:
            key = (
                event.target_id,
                int(round((event.angle_deg or 0.0) / 4.0)),
                int(round((event.distance_m or 0.0) / 2.0)),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        return unique

    def _event_to_track(self, event: TargetEvent, zone: str, friend_foe: str, source_label: str, sector_only: bool = False) -> dict:
        metadata = event.metadata or {}
        frame_width = max(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH), 640)
        angle = float(event.angle_deg if event.angle_deg is not None else 90.0)
        source_tag = {
            "vision": "V",
            "radar": "R",
            "acoustic": "A",
            "thermal": "T",
        }.get(source_label, "X")
        return {
            "label": event.target_id,
            "confidence": event.confidence,
            "angle": angle,
            "distance": float(event.distance_m or 12.0),
            "position": self._position_tag((angle / 180.0) * frame_width, frame_width),
            "friend_foe": friend_foe,
            "zone": zone,
            "reason": str(metadata.get("raw_line") or metadata.get("band_label") or metadata.get("signature_type") or source_label),
            "source": source_label,
            "source_tag": source_tag,
            "selected": False,
            "sector_only": sector_only,
        }

    def _draw_cached_detections(self, frame) -> None:
        for detection in self._last_detections:
            color = self._friend_foe_color(detection["friend_foe"])
            thickness = 3 if detection.get("selected") else 2
            cv2.rectangle(
                frame,
                (detection["x1"], detection["y1"]),
                (detection["x2"], detection["y2"]),
                color,
                thickness,
            )
            label = (
                f"{detection['label']} {detection['confidence']:.2f} "
                f"| {detection['friend_foe']} | {detection['position']} | "
                f"{detection['zone']} | {detection['angle']:.0f}deg"
            )
            cv2.putText(
                frame,
                label,
                (detection["x1"], max(20, detection["y1"] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2 if detection.get("selected") else 1,
            )
            if detection.get("selected"):
                cv2.putText(
                    frame,
                    "AKTIF HEDEF",
                    (detection["x1"], min(frame.shape[0] - 12, detection["y2"] + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.56,
                    color,
                    2,
                )

    @staticmethod
    def _resize_for_display(frame, target_height: int):
        h, w = frame.shape[:2]
        scale = target_height / max(h, 1)
        target_width = int(w * scale)
        return cv2.resize(frame, (target_width, target_height))

    @staticmethod
    def _friend_foe_color(label: str):
        if label == "dost":
            return (0, 255, 0)
        if label == "tehdit":
            return (0, 0, 255)
        return (0, 180, 255)

    @staticmethod
    def _wrap_text(text: str, width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines = []
        current = words[0]
        for word in words[1:]:
            if len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    @staticmethod
    def _position_tag(center_x: float, frame_width: int) -> str:
        ratio = center_x / max(frame_width, 1)
        if ratio < 0.33:
            return "SOL"
        if ratio < 0.66:
            return "ORTA"
        return "SAG"

    def _make_placeholder_frame(self) -> np.ndarray:
        width = int(self.display_cfg.get("placeholder_width", 1280))
        height = int(self.display_cfg.get("placeholder_height", 720))
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (22, 24, 30)
        cv2.putText(frame, "KAMERA BAGLI DEGIL", (60, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 180, 255), 3)
        cv2.putText(frame, "Radar / Acoustic / Thermal izleme aktif kalabilir", (60, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (220, 220, 220), 2)
        cv2.putText(frame, "Hologram ekraninda sensor hedefleri gosteriliyor", (60, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (220, 220, 220), 2)
        return frame


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config" / "research" / "orchestrator_config.json"
    DemoOrchestrator(config_path).run()


if __name__ == "__main__":
    main()
