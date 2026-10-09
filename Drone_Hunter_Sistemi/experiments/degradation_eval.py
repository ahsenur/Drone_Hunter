"""
Bozulma altinda tek sensor ve fuzyon karsilastirma iskeleti.

DIKKAT - bu bir SENTETIK simulasyondur:
- Sensor davranislari asagidaki SENSOR_MODEL tablosundaki VARSAYIMSAL sayilardir; olculmus degildir.
- Uretilen tablo bir performans iddiasi degildir; boru hattinin (zaman asimi, agirlik, esik)
  bozulma altinda nasil davrandigini gostermek ve gercek kayitlar gelince ayni metrik koduyla
  degerlendirme yapabilmek icindir.
- Gercek veri icin: build_stream() yerine kayit dosyalarindan olay ureten bir fonksiyon verin.

Calistirma (proje kokunden):  PYTHONPATH=src python experiments/degradation_eval.py
"""
from __future__ import annotations

import csv
import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from integration import build_target_event                      # noqa: E402
from research_core import MultiSensorPipeline, load_profile     # noqa: E402

TICKS = 300            # her kosuda 300 adim, adim = 0.5 sn
DT = 0.5
DRONE_PRESENT = lambda k: 100 <= k < 200      # ortadaki 100 adimda drone var

# VARSAYIMSAL sensor modeli: (p_tespit, tespit_guveni, p_yanlis_alarm, yanlis_alarm_guveni)
SENSOR_MODEL = {
    "clean":          {"vision": (0.90, 0.85, 0.02, 0.55), "acoustic": (0.70, 0.60, 0.05, 0.40), "radar": (0.85, 0.80, 0.02, 0.50)},
    "low_visibility": {"vision": (0.35, 0.55, 0.04, 0.50), "acoustic": (0.70, 0.60, 0.05, 0.40), "radar": (0.85, 0.80, 0.02, 0.50)},
    "noisy_audio":    {"vision": (0.90, 0.85, 0.02, 0.55), "acoustic": (0.45, 0.45, 0.35, 0.55), "radar": (0.85, 0.80, 0.02, 0.50)},
    "link_loss":      {"vision": (0.90, 0.85, 0.02, 0.55), "acoustic": (0.70, 0.60, 0.05, 0.40), "radar": (0.00, 0.00, 0.00, 0.00)},
    "combined":       {"vision": (0.35, 0.55, 0.04, 0.50), "acoustic": (0.45, 0.45, 0.35, 0.55), "radar": (0.00, 0.00, 0.00, 0.00)},
}
CONFIGS = {
    "vision_only": ("vision",),
    "acoustic_only": ("acoustic",),
    "radar_only": ("radar",),
    "fusion_mean": ("vision", "acoustic", "radar"),
    "fusion_noisyor": ("vision", "acoustic", "radar"),
}


def make_event(source, now, rng, conf_mu):
    conf = max(0.05, min(1.0, rng.gauss(conf_mu, 0.1)))
    return build_target_event(source=source, target_detected=True, target_id=f"{source}_t",
                              angle_deg=90 + rng.gauss(0, 5), distance_m=max(3.0, rng.gauss(22, 4)),
                              confidence=conf, threat_level="medium", timestamp=now)


def run_once(condition, config_name, config_sources, seed):
    rng = random.Random(seed)
    agg = "noisy_or" if config_name == "fusion_noisyor" else "mean"
    pipe = MultiSensorPipeline(load_profile(ROOT / "config/research/campus_perimeter_profile.json"), aggregation=agg)
    model = SENSOR_MODEL[condition]
    hits = misses = false_alarms = quiet = 0
    for k in range(TICKS):
        now = 1_000.0 + k * DT
        present = DRONE_PRESENT(k)
        events = {}
        for src in config_sources:
            p_det, c_det, p_fa, c_fa = model[src]
            if present and rng.random() < p_det:
                events[src] = make_event(src, now, rng, c_det)
            elif (not present) and rng.random() < p_fa:
                events[src] = make_event(src, now, rng, c_fa)
        status = {s: ("STALE" if (condition in ("link_loss", "combined") and s == "radar") else "OK")
                  for s in config_sources}
        res = pipe.process(radar_event=events.get("radar"), vision_event=events.get("vision"),
                           acoustic_event=events.get("acoustic"), now=now, sensor_status=status)
        alarm = res.threat_score >= pipe.profile.alert_threshold and res.fused_event.target_detected
        if present:
            hits += alarm
            misses += (not alarm)
        else:
            false_alarms += alarm
            quiet += 1
    return hits / (hits + misses), false_alarms / quiet


def main(n_seeds=30):
    rows = []
    for cond in SENSOR_MODEL:
        for name, srcs in CONFIGS.items():
            res = [run_once(cond, name, srcs, seed) for seed in range(n_seeds)]
            rows.append({
                "kosul": cond, "yapilandirma": name,
                "tespit_orani": round(statistics.mean(r[0] for r in res), 3),
                "yanlis_alarm_orani": round(statistics.mean(r[1] for r in res), 3),
            })
    out = ROOT / "experiments" / "degradation_results_synthetic.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"{'kosul':<15}{'yapilandirma':<15}{'tespit':>8}{'yanlis alarm':>14}")
    for r in rows:
        print(f"{r['kosul']:<15}{r['yapilandirma']:<15}{r['tespit_orani']:>8}{r['yanlis_alarm_orani']:>14}")
    print(f"\n[SENTETIK, varsayimsal sensor modeli] yazildi: {out}")


if __name__ == "__main__":
    main()
