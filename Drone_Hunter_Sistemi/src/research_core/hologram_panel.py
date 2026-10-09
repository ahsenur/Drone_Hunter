from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from integration import TargetEvent


class HologramPanel:
    """Taktik veriyi holografik gorunumde sunan ayri pencere."""

    def __init__(self, width: int = 1280, height: int = 720, title: str = 'DroneHunter Hologram Tactical View') -> None:
        self.width = int(width)
        self.height = int(height)
        self.title = title
        self.center = (self.width // 2, self.height // 2)
        self.max_radius = min(self.width, self.height) // 3

    def render(
        self,
        command: dict,
        threat_score: float,
        friend_foe: str,
        friend_foe_reason: str,
        resilience_mode: str,
        resilience_notes: str,
        detections: list[dict],
        auxiliary_tracks: list[dict],
        radar_event: Optional[TargetEvent],
        acoustic_event: Optional[TargetEvent],
        thermal_event: Optional[TargetEvent],
    ) -> np.ndarray:
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self._draw_background(canvas)
        self._draw_radar_grid(canvas)
        self._draw_header(canvas, command, threat_score, friend_foe, resilience_mode)
        self._draw_sensor_status(canvas, radar_event, acoustic_event, thermal_event)
        self._draw_targets(canvas, detections, auxiliary_tracks)
        self._draw_focus_target(canvas, command, detections, friend_foe_reason)
        self._draw_footer(canvas, resilience_notes)
        return canvas

    def _draw_background(self, canvas: np.ndarray) -> None:
        base = np.zeros_like(canvas)
        for y in range(self.height):
            ratio = y / max(self.height - 1, 1)
            color = (
                int(18 + ratio * 30),
                int(34 + ratio * 45),
                int(42 + ratio * 55),
            )
            base[y, :] = color
        glow = np.zeros_like(canvas)
        cv2.circle(glow, self.center, self.max_radius + 120, (70, 120, 120), -1)
        canvas[:] = cv2.addWeighted(base, 0.90, glow, 0.18, 0)

    def _draw_radar_grid(self, canvas: np.ndarray) -> None:
        cx, cy = self.center
        grid = (120, 255, 240)
        soft = (60, 110, 110)
        for radius in range(self.max_radius // 4, self.max_radius + 1, self.max_radius // 4):
            cv2.circle(canvas, (cx, cy), radius, soft, 1, cv2.LINE_AA)
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x = int(cx + math.cos(rad) * self.max_radius)
            y = int(cy - math.sin(rad) * self.max_radius)
            cv2.line(canvas, (cx, cy), (x, y), (45, 80, 80), 1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), 8, grid, -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), 18, grid, 1, cv2.LINE_AA)
        cv2.putText(canvas, 'TACTICAL HOLOGRAM', (36, 44), cv2.FONT_HERSHEY_DUPLEX, 0.95, grid, 2, cv2.LINE_AA)

    def _draw_header(self, canvas: np.ndarray, command: dict, threat_score: float, friend_foe: str, resilience_mode: str) -> None:
        cyan = (140, 255, 250)
        warning = (90, 190, 255)
        danger = (90, 90, 255)
        mode = str(command.get('mode', 'IDLE'))
        angle = int(command.get('angle_deg', 0) or 0)
        cv2.putText(canvas, f'MODE  {mode}', (36, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.90, cyan, 2, cv2.LINE_AA)
        cv2.putText(canvas, f'THREAT SCORE  {threat_score:.2f}', (36, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.75, warning if threat_score < 0.75 else danger, 2, cv2.LINE_AA)
        cv2.putText(canvas, f'CLASS  {friend_foe.upper()}', (36, 154), cv2.FONT_HERSHEY_SIMPLEX, 0.75, cyan, 2, cv2.LINE_AA)
        cv2.putText(canvas, f'AZIMUTH  {angle:03d} DEG', (36, 186), cv2.FONT_HERSHEY_SIMPLEX, 0.75, cyan, 2, cv2.LINE_AA)
        cv2.putText(canvas, f'RESILIENCE  {resilience_mode}', (36, 218), cv2.FONT_HERSHEY_SIMPLEX, 0.75, warning if resilience_mode == 'NORMAL' else danger, 2, cv2.LINE_AA)

    def _draw_sensor_status(self, canvas: np.ndarray, radar_event: Optional[TargetEvent], acoustic_event: Optional[TargetEvent], thermal_event: Optional[TargetEvent]) -> None:
        x = self.width - 320
        y = 56
        cv2.rectangle(canvas, (x - 24, y - 30), (self.width - 28, y + 126), (25, 55, 60), 1, cv2.LINE_AA)
        cv2.putText(canvas, 'SENSOR LINKS', (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (140, 255, 250), 2, cv2.LINE_AA)
        sensor_rows = [
            ('RADAR', radar_event is not None),
            ('ACOUSTIC', acoustic_event is not None),
            ('THERMAL', thermal_event is not None),
        ]
        row_y = y + 34
        for label, active in sensor_rows:
            color = (90, 255, 180) if active else (110, 110, 140)
            cv2.circle(canvas, (x + 8, row_y - 6), 8, color, -1, cv2.LINE_AA)
            status_text = 'ACTIVE' if active else 'IDLE'
            cv2.putText(canvas, f"{label}: {status_text}", (x + 28, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)
            row_y += 34

    def _draw_targets(self, canvas: np.ndarray, detections: list[dict], auxiliary_tracks: list[dict]) -> None:
        cx, cy = self.center
        ring_color = (120, 255, 240)
        side_x = self.width - 360
        side_y = 260
        cv2.putText(canvas, 'TRACKED OBJECTS', (side_x, side_y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, ring_color, 2, cv2.LINE_AA)
        side_y += 34
        combined_tracks = list(detections[:6]) + list(auxiliary_tracks[:6])
        for index, detection in enumerate(combined_tracks[:10], start=1):
            angle = float(detection.get('angle', 90.0))
            distance = float(detection.get('distance', 10.0) or 10.0)
            radius = self._distance_to_radius(distance)
            px, py = self._polar_to_canvas(angle, radius)
            color = self._friend_foe_color(str(detection.get('friend_foe', 'bilinmeyen')))
            source = str(detection.get('source', 'vision'))
            source_tag = str(detection.get('source_tag', source[:1].upper()))
            if detection.get("sector_only"):
                self._draw_sector(canvas, angle, radius, color)
            else:
                cv2.circle(canvas, (px, py), 10, color, -1, cv2.LINE_AA)
                cv2.circle(canvas, (px, py), 22, color, 1, cv2.LINE_AA)
                cv2.line(canvas, (cx, cy), (px, py), ring_color, 1, cv2.LINE_AA)
            cv2.putText(canvas, f'{source_tag}{index}', (px - 12, py + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (10, 20, 20), 2, cv2.LINE_AA)

            label = str(detection.get('label', 'target'))
            friend_foe = str(detection.get('friend_foe', 'bilinmeyen'))
            zone = str(detection.get('zone', 'zone'))
            conf = float(detection.get('confidence', 0.0))
            line = f'{source_tag}{index}. {source}:{label} | {friend_foe} | {zone} | {angle:.0f}d | {conf:.2f}'
            cv2.putText(canvas, line[:48], (side_x, side_y), cv2.FONT_HERSHEY_SIMPLEX, 0.54, color, 1, cv2.LINE_AA)
            side_y += 28

    def _draw_sector(self, canvas: np.ndarray, angle: float, radius: int, color: tuple[int, int, int]) -> None:
        start = int(180.0 - angle - 14)
        end = int(180.0 - angle + 14)
        cv2.ellipse(canvas, self.center, (radius, radius), 0, start, end, color, 3, cv2.LINE_AA)
        tip = self._polar_to_canvas(angle, radius)
        cv2.circle(canvas, tip, 8, color, -1, cv2.LINE_AA)

    def _draw_focus_target(self, canvas: np.ndarray, command: dict, detections: list[dict], friend_foe_reason: str) -> None:
        target_id = str(command.get('target_id') or '')
        focus = None
        for detection in detections:
            if str(detection.get('label')) == target_id:
                focus = detection
                break
        if focus is None and detections:
            focus = detections[0]
        if focus is None:
            return

        x0, y0 = 40, self.height - 180
        cv2.rectangle(canvas, (x0 - 10, y0 - 36), (x0 + 430, y0 + 96), (24, 70, 76), 1, cv2.LINE_AA)
        color = self._friend_foe_color(str(focus.get('friend_foe', 'bilinmeyen')))
        cv2.putText(canvas, 'FOCUS TARGET', (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (140, 255, 250), 2, cv2.LINE_AA)
        lines = [
            f"ID: {focus.get('label', '-')}",
            f"CLASS: {focus.get('friend_foe', '-')}",
            f"ZONE: {focus.get('zone', '-')}",
            f"ANGLE: {float(focus.get('angle', 0.0)):.0f} DEG | DIST: {float(focus.get('distance', 0.0)):.1f} M",
        ]
        line_y = y0 + 28
        for line in lines:
            cv2.putText(canvas, line, (x0, line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.60, color, 2 if line_y == y0 + 28 else 1, cv2.LINE_AA)
            line_y += 28
        for chunk in self._wrap_text(friend_foe_reason, 42)[:2]:
            cv2.putText(canvas, chunk, (x0, line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (140, 255, 250), 1, cv2.LINE_AA)
            line_y += 22

    def _draw_footer(self, canvas: np.ndarray, resilience_notes: str) -> None:
        footer_y = self.height - 28
        cv2.rectangle(canvas, (0, self.height - 56), (self.width, self.height), (18, 28, 32), -1)
        cv2.putText(canvas, resilience_notes[:110], (28, footer_y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (120, 255, 240), 1, cv2.LINE_AA)

    def _distance_to_radius(self, distance: float) -> int:
        clamped = max(1.0, min(distance, 50.0))
        ratio = 1.0 - ((clamped - 1.0) / 49.0)
        return max(40, int(50 + ratio * (self.max_radius - 60)))

    def _polar_to_canvas(self, angle_deg: float, radius: int) -> tuple[int, int]:
        rad = math.radians(180.0 - angle_deg)
        x = int(self.center[0] + math.cos(rad) * radius)
        y = int(self.center[1] - math.sin(rad) * radius)
        return x, y

    @staticmethod
    def _friend_foe_color(label: str) -> tuple[int, int, int]:
        if label == 'dost':
            return (80, 255, 140)
        if label == 'tehdit':
            return (90, 90, 255)
        return (90, 210, 255)

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