from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from integration import TargetEvent
from integration.bridge.radar_bridge import RadarBridge


class RadarWatcher:
    """
    Radar projesine dokunmadan disaridan veri izlemek icin kullanilir.

    Bu sinif radar kodunu degistirmez. Yalnizca radar tarafindan zaten uretilen
    bir dosya veya cikti kanalini okuyup yeni event var mi diye bakar.
    """

    def __init__(
        self,
        bridge: RadarBridge,
        poll_interval: float = 0.5,
    ) -> None:
        self.bridge = bridge
        self.poll_interval = poll_interval
        self._last_signature: Optional[str] = None

    def poll_once(self) -> Optional[TargetEvent]:
        event = self.bridge.load_latest_event()
        if event is None:
            return None

        signature = self._build_signature(event)
        if signature == self._last_signature:
            return None

        self._last_signature = signature
        return event

    def watch_forever(self, on_event: Callable[[TargetEvent], None]) -> None:
        while True:
            try:
                event = self.poll_once()
                if event is not None:
                    on_event(event)
            except KeyboardInterrupt:
                raise
            except Exception:
                # Izleyici radar projesini etkilememeli; hata alsa bile yeniden denemeli.
                pass
            time.sleep(self.poll_interval)

    @staticmethod
    def _build_signature(event: TargetEvent) -> str:
        return f"{event.target_id}|{event.angle_deg}|{event.distance_m}|{event.timestamp}"
