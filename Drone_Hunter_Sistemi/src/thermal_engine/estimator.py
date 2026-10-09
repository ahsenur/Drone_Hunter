from __future__ import annotations

from typing import Optional

import cv2

from integration import TargetEvent, build_target_event


class ThermalSignatureAnalyzer:
    """
    Termal kamera verisi geldiginde basit hotspot/motor isi imzasi cikarimi yapar.

    Not:
    Bu gercek termal donanim olmadan kesin motor tanisi koymaz.
    Sadece termal verideki sicak bolgeleri sinyal olarak yorumlar.
    """

    def __init__(self, hotspot_threshold: int = 220, min_area: int = 80) -> None:
        self.hotspot_threshold = hotspot_threshold
        self.min_area = min_area

    def analyze_frame(self, frame) -> tuple[Optional[TargetEvent], any]:
        if frame is None:
            return None, frame

        if len(frame.shape) == 3 and frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        _, thresh = cv2.threshold(normalized, self.hotspot_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        display = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)

        if not contours:
            return None, display

        valid = [cnt for cnt in contours if cv2.contourArea(cnt) >= self.min_area]
        if not valid:
            return None, display

        best = max(valid, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(best)
        area = float(w * h)
        center_x = x + w / 2.0
        frame_width = display.shape[1]
        angle = (center_x / max(frame_width, 1)) * 180.0
        distance_est = max(1.0, min(50.0, 35000.0 / max(area, 1.0)))
        heat_score = min(1.0, area / 12000.0 + 0.25)

        cv2.rectangle(display, (x, y), (x + w, y + h), (0, 140, 255), 2)
        cv2.putText(
            display,
            f"thermal_hotspot {heat_score:.2f}",
            (x, max(20, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 140, 255),
            1,
        )

        event = build_target_event(
            source="thermal",
            target_detected=True,
            target_id="thermal_hotspot",
            angle_deg=angle,
            distance_m=distance_est,
            confidence=heat_score,
            threat_level="medium" if heat_score < 0.75 else "high",
            metadata={
                "thermal_area": area,
                "heat_signature": heat_score,
                "position": self._position_tag(center_x, frame_width),
            },
        )
        return event, display

    @staticmethod
    def _position_tag(center_x: float, frame_width: int) -> str:
        ratio = center_x / max(frame_width, 1)
        if ratio < 0.33:
            return "SOL"
        if ratio < 0.66:
            return "ORTA"
        return "SAG"
