from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from integration import TargetEvent


@dataclass
class ResilienceState:
    mode: str
    jammer_suspected: bool
    notes: str
    trigger: str = "none"          # "keyword" | "heartbeat_timeout" | "none"
    degraded_sources: Optional[List[str]] = None   # STALE/FAULT durumundaki sensorler


class ResilienceManager:
    """
    Jammer veya iletisim bozulmasi durumunda sistemi saldiriya gecirmeden
    guvenli ve dayanikli modda tutmak icin kullanilir.
    """

    def assess(
        self,
        radar_event: Optional[TargetEvent],
        vision_event: Optional[TargetEvent],
        acoustic_event: Optional[TargetEvent],
        sensor_status: Optional[Dict[str, str]] = None,
    ) -> ResilienceState:
        """
        Iki tetikleyici vardir:
        1) radar metninde anahtar kelime (simulasyonun yazdigi mesaja tepki, RF OLCUMU DEGIL)
        2) radar heartbeat'i zaman asimina ugradi (sensor_status["radar"] == STALE/FAULT)
        Ayrica STALE/FAULT durumundaki tum sensorler degraded_sources'a yazilir.
        """
        sensor_status = sensor_status or {}
        degraded = [s for s, st in sorted(sensor_status.items()) if st in ("STALE", "FAULT")]
        radar_text = ""
        if radar_event is not None:
            radar_text = str((radar_event.metadata or {}).get("raw_line", "")).lower()

        jammer_keywords = ("jammer", "iletisim kesintisi", "karistirma", "interference", "jamming")
        keyword_hit = any(keyword in radar_text for keyword in jammer_keywords)
        heartbeat_lost = sensor_status.get("radar") in ("STALE", "FAULT")
        jammer_suspected = keyword_hit or heartbeat_lost
        trigger = "keyword" if keyword_hit else ("heartbeat_timeout" if heartbeat_lost else "none")

        if jammer_suspected and vision_event and vision_event.target_detected:
            return ResilienceState(
                mode="LOCAL_SENSOR_HOLD",
                jammer_suspected=True,
                trigger=trigger,
                degraded_sources=degraded,
                notes="rf bozulmasi var; sistem görsel yerel izleme moduna geçti",
            )

        if jammer_suspected and acoustic_event and acoustic_event.target_detected:
            return ResilienceState(
                mode="ACOUSTIC_RESILIENCE",
                jammer_suspected=True,
                trigger=trigger,
                degraded_sources=degraded,
                notes="rf bozulmasi var; akustik destekli güvenli izleme aktif",
            )

        if jammer_suspected:
            return ResilienceState(
                mode="SAFE_ALERT",
                jammer_suspected=True,
                trigger=trigger,
                degraded_sources=degraded,
                notes="rf bozulmasi var; alarm verildi ve güvenli mod korundu",
            )

        return ResilienceState(
            mode="NORMAL",
            jammer_suspected=False,
            trigger="none",
            degraded_sources=degraded,
            notes=("sensor sorunu: " + ", ".join(degraded)) if degraded else "sistem normal calisiyor",
        )
