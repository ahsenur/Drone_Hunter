"""
Sensor saglik izleyicisi.

Amac: "hedef yok" ile "sensor calismiyor" durumlarini ayirmak.
- Sensor calisiyor ve hedef yoksa  -> heartbeat() cagrilir, durum OK
- Sensor hata verdiyse              -> fault() cagrilir, durum FAULT
- Belirli sureden beri heartbeat yoksa -> durum STALE
- Hic heartbeat gelmediyse          -> UNKNOWN (alarm uretilmez)
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Dict, Optional

OK = "OK"
STALE = "STALE"
FAULT = "FAULT"
UNKNOWN = "UNKNOWN"

DEFAULT_TIMEOUTS_S = {"vision": 1.0, "acoustic": 3.0, "radar": 5.0, "thermal": 1.0}


@dataclass
class SensorHealth:
    source: str
    state: str
    age_s: Optional[float]
    reason: str = ""


class SensorHealthMonitor:
    def __init__(self, timeouts: Optional[Dict[str, float]] = None, clock: Callable[[], float] = time.time) -> None:
        self.timeouts = {**DEFAULT_TIMEOUTS_S, **(timeouts or {})}
        self._clock = clock
        self._last_ok: Dict[str, float] = {}
        self._fault: Dict[str, str] = {}

    def heartbeat(self, source: str, now: Optional[float] = None) -> None:
        self._last_ok[source] = self._clock() if now is None else float(now)
        self._fault.pop(source, None)

    def fault(self, source: str, reason: str) -> None:
        self._fault[source] = reason or "bilinmeyen hata"

    def status(self, source: str, now: Optional[float] = None) -> SensorHealth:
        now = self._clock() if now is None else float(now)
        last = self._last_ok.get(source)
        age = None if last is None else max(0.0, now - last)
        if source in self._fault:
            return SensorHealth(source, FAULT, age, self._fault[source])
        if last is None:
            return SensorHealth(source, UNKNOWN, None, "heartbeat hic gelmedi")
        if age > self.timeouts.get(source, 2.0):
            return SensorHealth(source, STALE, age, f"{age:.1f} sn heartbeat yok")
        return SensorHealth(source, OK, age)

    def snapshot(self, now: Optional[float] = None) -> Dict[str, str]:
        sources = set(self._last_ok) | set(self._fault)
        return {s: self.status(s, now).state for s in sorted(sources)}
