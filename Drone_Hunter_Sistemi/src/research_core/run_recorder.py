"""
Calisma kaydi (SQLite). Orchestrator her dongude sensor olaylarini, sensor sagligini ve
fuzyon kararini kaydeder; sonradan run_analysis.py ile "veri kesilirse ne oldu" sorulari
sayiyla cevaplanir.

Tablolar:
  runs          : her orchestrator calistirmasi icin bir satir
  events        : sensorlerden gelen ham olaylar (kaynak, aci, mesafe, guven, olay zamani)
  sensor_health : sensor durum DEGISIKLIKLERI (OK / STALE / FAULT / UNKNOWN, yas, neden)
  decisions     : fuzyon karari (mod, tehdit skoru, tetikleyici, bozulan/bayat kaynaklar);
                  en az decision_interval_s aralikla ve mod degisince yazilir

Kayit hatasi sistemin calismasini durdurmamalidir: cagiran taraf istisnayi yakalar.
"""
from __future__ import annotations

import pathlib
import sqlite3
import time
from typing import Callable, Dict, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
    id INTEGER PRIMARY KEY, started_at REAL, label TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY, run_id INTEGER, t REAL, source TEXT, target_id TEXT,
    angle_deg REAL, distance_m REAL, confidence REAL, threat_level TEXT, event_ts REAL);
CREATE TABLE IF NOT EXISTS sensor_health(
    id INTEGER PRIMARY KEY, run_id INTEGER, t REAL, source TEXT, state TEXT,
    age_s REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS decisions(
    id INTEGER PRIMARY KEY, run_id INTEGER, t REAL, operating_mode TEXT,
    resilience_mode TEXT, trigger TEXT, threat_score REAL, friend_foe TEXT,
    target_detected INTEGER, degraded_sources TEXT, stale_sources TEXT);
CREATE INDEX IF NOT EXISTS ix_events_run_t ON events(run_id, t);
CREATE INDEX IF NOT EXISTS ix_health_run_t ON sensor_health(run_id, t);
CREATE INDEX IF NOT EXISTS ix_dec_run_t ON decisions(run_id, t);
"""


class RunRecorder:
    def __init__(
        self,
        db_path,
        label: str = "",
        note: str = "",
        decision_interval_s: float = 0.2,
        commit_interval_s: float = 1.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        path = pathlib.Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        cur = self.conn.execute(
            "INSERT INTO runs(started_at, label, note) VALUES (?, ?, ?)", (clock(), label, note)
        )
        self.run_id = int(cur.lastrowid)
        self.conn.commit()
        self.decision_interval_s = decision_interval_s
        self.commit_interval_s = commit_interval_s
        self._last_state: Dict[str, str] = {}
        self._last_mode = None
        self._last_decision_t = -1e18
        self._last_commit_t = -1e18

    def record_tick(self, now: float, events: Dict[str, Optional[object]], health: Dict[str, object], result) -> None:
        c = self.conn
        for source, ev in events.items():
            if ev is None:
                continue
            c.execute(
                "INSERT INTO events(run_id,t,source,target_id,angle_deg,distance_m,confidence,threat_level,event_ts)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (self.run_id, now, source, getattr(ev, "target_id", None), getattr(ev, "angle_deg", None),
                 getattr(ev, "distance_m", None), getattr(ev, "confidence", None),
                 getattr(ev, "threat_level", None), getattr(ev, "timestamp", None)),
            )
        for source, h in health.items():
            if self._last_state.get(source) != h.state:
                c.execute(
                    "INSERT INTO sensor_health(run_id,t,source,state,age_s,reason) VALUES (?,?,?,?,?,?)",
                    (self.run_id, now, source, h.state, h.age_s, h.reason),
                )
                self._last_state[source] = h.state

        mode = (result.operating_mode, result.resilience_mode)
        if mode != self._last_mode or now - self._last_decision_t >= self.decision_interval_s:
            meta = getattr(result.fused_event, "metadata", None) or {}
            degraded = ",".join(result.command.get("degraded_sources") or [])
            stale = ",".join(result.stale_sources or [])
            c.execute(
                "INSERT INTO decisions(run_id,t,operating_mode,resilience_mode,trigger,threat_score,friend_foe,"
                "target_detected,degraded_sources,stale_sources) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.run_id, now, result.operating_mode, result.resilience_mode,
                 meta.get("resilience_trigger", "none"), float(result.threat_score), result.friend_foe_label,
                 int(bool(getattr(result.fused_event, "target_detected", False))), degraded, stale),
            )
            self._last_mode = mode
            self._last_decision_t = now

        if now - self._last_commit_t >= self.commit_interval_s:
            c.commit()
            self._last_commit_t = now

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()
