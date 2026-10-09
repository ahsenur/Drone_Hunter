from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass
class ZoneDecision:
    zone_label: str
    risk_bonus: float
    note: str


class ZoneRiskEvaluator:
    """
    Goruntu uzerinde basit bolge tabanli risk degerlendirmesi.
    Akademik sunumda "alan farkindaligi" olarak guclu durur.
    """

    def __init__(self, zones: Optional[Iterable[Dict[str, object]]] = None) -> None:
        self.zones = list(zones or [])

    def evaluate_ratio(self, x_ratio: float, y_ratio: float = 0.5) -> ZoneDecision:
        for zone in self.zones:
            if (
                float(zone.get("x_min", 0.0)) <= x_ratio <= float(zone.get("x_max", 1.0))
                and float(zone.get("y_min", 0.0)) <= y_ratio <= float(zone.get("y_max", 1.0))
            ):
                return ZoneDecision(
                    zone_label=str(zone.get("label", "unknown_zone")),
                    risk_bonus=float(zone.get("risk_bonus", 0.0)),
                    note=str(zone.get("note", "bolge etkisi aktif")),
                )

        return ZoneDecision(
            zone_label="general_area",
            risk_bonus=0.0,
            note="genel izleme alanı",
        )
