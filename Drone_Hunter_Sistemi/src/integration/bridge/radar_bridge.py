from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from integration import TargetEvent, build_target_event


class RadarBridge:
    """
    Radar projesine dokunmadan veri almak icin kullanilir.

    Ilk surumde iki giris yontemi sunar:
    - JSON dosyasi okumak
    - Python sozlugu normalize etmek

    Ek olarak radar terminal/log ciktilarini bozmeden okuyabilmek icin
    duz metin satirlarini da yorumlayabilir.
    """

    HEDEF_RE = re.compile(r"hedef", re.IGNORECASE)
    RISK_RE = re.compile(r"risk", re.IGNORECASE)
    DISTANCE_RE = re.compile(r"(?:mesafe|distance|uzaklik)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    ANGLE_RE = re.compile(r"(?:aci|angle)\s*[:=]\s*(-?[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    DELTA_RE = re.compile(r"delta\s*[:=]?\s*(-?[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    ID_RE = re.compile(r"(?:id|hedef)\s*[:=]?\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
    # ROS2 log satiri: [WARN] [1791306831.296023452] [radar]: ...  (epoch saniye)
    TIMESTAMP_RE = re.compile(r"\[(\d{9,10}\.\d+)\]")
    COUNTDOWN_RE = re.compile(r"kalan\s*s[üu]re\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

    def __init__(
        self,
        json_path: Optional[str] = None,
        text_log_path: Optional[str] = None,
        parser: Optional[Callable[[str], Optional[TargetEvent]]] = None,
        hyperbolic_baseline_m: float = 0.42,
        delta_to_path_scale: float = 0.00008,
        delta_is_path_difference: bool = False,
    ) -> None:
        """
        delta_is_path_difference:
          False (varsayilan): Delta'dan aci URETILMEZ. iha_radar_sistemi/radar.cpp'deki Delta,
            hedefin yon dogrusu ile sabit bir hiperbol (a=2, b=1.5) arasindaki kesisim
            diskriminantidir; bir yol farki degildir, bu yuzden asin ile aciya cevrilmesi
            fiziksel anlam tasimaz.
          True: eski davranis (Delta*scale/baseline -> asin). Yalnizca Delta gercekten
            yol farki olan bir radar kaynagi icin kullanin.
        """
        self.delta_is_path_difference = delta_is_path_difference
        self.json_path = Path(json_path).expanduser() if json_path else None
        self.text_log_path = Path(text_log_path).expanduser() if text_log_path else None
        self.parser = parser
        self.hyperbolic_baseline_m = hyperbolic_baseline_m
        self.delta_to_path_scale = delta_to_path_scale

    def load_latest_event(self) -> Optional[TargetEvent]:
        if self.json_path and self.json_path.exists():
            with self.json_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return self.normalize_payload(payload)

        if self.text_log_path and self.text_log_path.exists():
            return self.load_latest_event_from_text()

        raise ValueError("Ne json_path ne de text_log_path kullanima uygun.")

    def normalize_payload(self, payload: Dict[str, Any]) -> TargetEvent:
        metadata = dict(payload)

        target_detected = payload.get("target_detected")
        if target_detected is None:
            target_detected = any(
                payload.get(key) is not None
                for key in ("target_id", "angle_deg", "distance_m", "confidence")
            )

        return build_target_event(
            source="radar",
            target_detected=target_detected,
            target_id=payload.get("target_id", payload.get("id", "radar_target")),
            angle_deg=payload.get("angle_deg", payload.get("angle")),
            distance_m=payload.get("distance_m", payload.get("distance")),
            confidence=payload.get("confidence", payload.get("guven", 0.5)),
            threat_level=payload.get("threat_level", payload.get("threat", "medium")),
            timestamp=payload.get("timestamp"),
            metadata=metadata,
        )

    def parse_text_line(self, line: str) -> Optional[TargetEvent]:
        text = line.strip()
        if not text:
            return None

        if self.parser is not None:
            parsed = self.parser(text)
            if parsed is not None:
                return parsed

        lower = text.lower()
        target_detected = bool(self.HEDEF_RE.search(text) or self.RISK_RE.search(text))

        angle = self._extract_number(self.ANGLE_RE, text)
        delta = self._extract_number(self.DELTA_RE, text)
        if angle is None and delta is not None and self.delta_is_path_difference:
            angle = self._estimate_hyperbolic_angle(delta)
        line_ts = self._extract_number(self.TIMESTAMP_RE, text)

        distance = self._extract_number(self.DISTANCE_RE, text)
        countdown_s = self._extract_number(self.COUNTDOWN_RE, text)
        if distance is None and countdown_s is not None:
            distance = max(1.0, float(countdown_s) * 20.0)
        confidence = 0.75 if target_detected else 0.0
        if "kritik" in lower or "critical" in lower:
            threat_level = "critical"
            confidence = 0.95
        elif "risk" in lower or "tehdit" in lower:
            threat_level = "high"
            confidence = 0.85
        elif target_detected:
            threat_level = "medium"
        else:
            threat_level = "low"

        target_id = self._extract_text(self.ID_RE, text) or "radar_target"

        if not target_detected and angle is None and distance is None:
            return None

        return build_target_event(
            source="radar",
            target_detected=target_detected,
            target_id=target_id,
            angle_deg=angle,
            distance_m=distance,
            confidence=confidence,
            threat_level=threat_level,
            timestamp=line_ts,
            metadata={
                "raw_line": text,
                "mode": "text_log",
                "delta_value": delta,
                "delta_meaning": "line_hyperbola_discriminant" if not self.delta_is_path_difference else "path_difference",
                "hyperbolic_angle": angle,
                "countdown_s": countdown_s,
                "timestamp_source": "line" if line_ts is not None else "parse_time",
            },
        )

    def parse_text_lines(self, lines: Iterable[str]) -> List[TargetEvent]:
        events: List[TargetEvent] = []
        for line in lines:
            event = self.parse_text_line(line)
            if event is not None:
                events.append(event)
        return events

    def load_latest_event_from_text(self) -> Optional[TargetEvent]:
        if not self.text_log_path:
            raise ValueError("text_log_path tanimli degil.")
        if not self.text_log_path.exists():
            return None

        with self.text_log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()

        events = self.parse_text_lines(lines)
        return events[-1] if events else None

    def load_all_events_from_text(self) -> List[TargetEvent]:
        """
        Zaman damgasi onceligi: (1) satirdaki ROS epoch damgasi, (2) yoksa dosyanin son
        yazilma zamani (mtime). Daha once olaylar okunduklari an damgalaniyordu; bu yuzden
        eski bir satir TTL'e takilmadan sonsuza kadar "taze" gorunuyordu.
        Sinir: damga WSL saatine aittir; Windows saatiyle farkliysa bayatlik hesabi sapar.
        """
        if not self.text_log_path:
            raise ValueError("text_log_path tanimli degil.")
        if not self.text_log_path.exists():
            return []

        mtime = self.text_log_path.stat().st_mtime
        with self.text_log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            events = self.parse_text_lines(handle.readlines())
        for event in events:
            if event.metadata.get("timestamp_source") != "line":
                event.timestamp = mtime
        return events

    def last_heartbeat_ts(self) -> Optional[float]:
        """
        Son 'HEARTBEAT' satirinin zamanini doner (satirdaki damga, yoksa dosya mtime).
        Heartbeat satiri hic yoksa None (radar saglik durumu bilinmiyor, alarm uretilmez).
        """
        if not self.text_log_path or not self.text_log_path.exists():
            return None
        last_line = None
        with self.text_log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if "heartbeat" in line.lower():
                    last_line = line
        if last_line is None:
            return None
        ts = self._extract_number(self.TIMESTAMP_RE, last_line)
        return ts if ts is not None else self.text_log_path.stat().st_mtime

    def load_recent_events_from_text(self, limit: int = 12) -> List[TargetEvent]:
        events = self.load_all_events_from_text()
        return events[-limit:] if limit > 0 else events

    def create_manual_event(
        self,
        angle_deg: float,
        distance_m: float,
        confidence: float = 0.8,
        target_id: str = "radar_target",
        threat_level: str = "medium",
    ) -> TargetEvent:
        return build_target_event(
            source="radar",
            target_detected=True,
            target_id=target_id,
            angle_deg=angle_deg,
            distance_m=distance_m,
            confidence=confidence,
            threat_level=threat_level,
            metadata={"mode": "manual_test"},
        )

    @staticmethod
    def _extract_number(pattern: re.Pattern[str], text: str) -> Optional[float]:
        match = pattern.search(text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_text(pattern: re.Pattern[str], text: str) -> Optional[str]:
        match = pattern.search(text)
        return match.group(1) if match else None

    def _estimate_hyperbolic_angle(self, delta_value: float) -> float:
        path_difference = float(delta_value) * self.delta_to_path_scale
        baseline = max(0.01, float(self.hyperbolic_baseline_m))
        normalized = max(-0.98, min(0.98, path_difference / baseline))
        return float(math.degrees(math.asin(normalized)))
