"""
Kayitli bir calismadan (run_recorder.py) sayilar cikarir:
- hangi modda ne kadar kalindi, mod gecisleri ve tetikleyicileri
- sensor kesintileri: son saglikli veriden ne kadar sonra tespit edildi, karara ne kadar sonra
  yansidi, toparlanma kararina ne kadar sonra yansidi

Zamanlar, calismanin ilk karar kaydina gore saniye cinsindendir.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional


def _sources(csv: Optional[str]) -> set:
    return set(filter(None, (csv or "").split(",")))


def summarize(db_path, run_id: Optional[int] = None) -> Dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if run_id is None:
            row = conn.execute("SELECT MAX(id) AS m FROM runs").fetchone()
            run_id = row["m"]
        if run_id is None:
            return {"run_id": None, "empty": True}

        dec = conn.execute("SELECT * FROM decisions WHERE run_id=? ORDER BY t", (run_id,)).fetchall()
        if not dec:
            return {"run_id": run_id, "empty": True}
        t0, t_end = dec[0]["t"], dec[-1]["t"]

        durations: Dict[str, float] = {}
        for a, b in zip(dec, dec[1:]):
            durations[a["resilience_mode"]] = durations.get(a["resilience_mode"], 0.0) + (b["t"] - a["t"])

        transitions: List[Dict[str, object]] = []
        prev = None
        for r in dec:
            if r["resilience_mode"] != prev:
                transitions.append({"t_s": r["t"] - t0, "from": prev, "to": r["resilience_mode"], "trigger": r["trigger"]})
                prev = r["resilience_mode"]

        counts = {r["source"]: r["n"] for r in conn.execute(
            "SELECT source, COUNT(*) AS n FROM events WHERE run_id=? GROUP BY source", (run_id,))}

        health = conn.execute("SELECT * FROM sensor_health WHERE run_id=? ORDER BY t", (run_id,)).fetchall()
        by_source: Dict[str, list] = {}
        for h in health:
            by_source.setdefault(h["source"], []).append(h)

        outages: List[Dict[str, object]] = []
        for source, rows in by_source.items():
            current = None
            for h in rows:
                bad = h["state"] in ("STALE", "FAULT")
                if bad and current is None:
                    age = h["age_s"] or 0.0
                    t_last_ok = h["t"] - age
                    first = next((d for d in dec if d["t"] >= t_last_ok and source in _sources(d["degraded_sources"])), None)
                    current = {
                        "source": source, "state": h["state"], "reason": h["reason"],
                        "t_last_ok_s": t_last_ok - t0, "detected_after_s": age,
                        "decision_after_s": (first["t"] - t_last_ok) if first else None,
                        "recovered": False, "recovery_after_s": None, "_t_last_ok": t_last_ok,
                    }
                elif h["state"] == "OK" and current is not None:
                    rec = next((d for d in dec if d["t"] >= h["t"] and source not in _sources(d["degraded_sources"])), None)
                    current["recovered"] = True
                    current["recovery_after_s"] = (rec["t"] - h["t"]) if rec else None
                    outages.append(current)
                    current = None
            if current is not None:
                outages.append(current)
        for o in outages:
            o.pop("_t_last_ok", None)
        outages.sort(key=lambda o: o["t_last_ok_s"])

        return {
            "run_id": run_id, "empty": False, "duration_s": t_end - t0, "n_decisions": len(dec),
            "event_counts": counts, "mode_durations_s": durations, "transitions": transitions, "outages": outages,
        }
    finally:
        conn.close()


def format_report(s: Dict[str, object]) -> str:
    if s.get("empty"):
        return "Kayit yok (karar satiri bulunamadi)."
    L = [f"Calisma #{s['run_id']}  sure: {s['duration_s']:.1f} sn  karar kaydi: {s['n_decisions']}"]
    L.append("Olay sayilari: " + (", ".join(f"{k}={v}" for k, v in sorted(s["event_counts"].items())) or "yok"))
    L.append("Modda gecen sure (sn):")
    for mode, sec in sorted(s["mode_durations_s"].items(), key=lambda kv: -kv[1]):
        L.append(f"  {mode:<22}{sec:8.1f}")
    L.append("Mod gecisleri:")
    for t in s["transitions"]:
        L.append(f"  t={t['t_s']:7.1f} sn  {t['from'] or '-':<20} -> {t['to']:<20} tetikleyici: {t['trigger']}")
    L.append("Sensor kesintileri:")
    if not s["outages"]:
        L.append("  yok")
    for o in s["outages"]:
        dec = "karara yansimadi" if o["decision_after_s"] is None else f"karara {o['decision_after_s']:.2f} sn sonra"
        rec = ("toparlanma karara yansimadi" if o["recovery_after_s"] is None else
               f"toparlanma {o['recovery_after_s']:.2f} sn sonra karara yansidi") if o["recovered"] else "toparlanmadi"
        L.append(f"  {o['source']:<9} {o['state']:<6} son saglikli veri t={o['t_last_ok_s']:.1f} sn | "
                 f"tespit {o['detected_after_s']:.2f} sn sonra | {dec} | {rec}")
    return "\n".join(L)
