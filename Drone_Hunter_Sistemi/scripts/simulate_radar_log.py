"""
Radar log'unu ROS2 olmadan uretir: once duzenli HEARTBEAT satirlari, sonra sessizlik
(baglanti kaybi senaryosu). Orchestrator'un LOCAL_SENSOR_HOLD'a gecisini ve gecikmeyi
olcmek icin kullanilir. SENTETIK veridir.

Kullanim:
  python scripts/simulate_radar_log.py --out data/integration/radar_output.log --beat 15 --silence 15 --with-target
"""
from __future__ import annotations

import argparse
import time


def build_lines(start_ts: float, beat_s: int, with_target: bool):
    lines = []
    for k in range(beat_s):
        ts = start_ts + k
        lines.append((ts, f"[INFO] [{ts:.9f}] [radar]: HEARTBEAT"))
        if with_target:
            lines.append((ts, f"[WARN] [{ts:.9f}] [radar]: HEDEF: SIM_T1 ACI: 80 MESAFE: 40"))
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--beat", type=int, default=15, help="heartbeat suresi (sn)")
    ap.add_argument("--silence", type=int, default=15, help="sonraki sessizlik (sn)")
    ap.add_argument("--with-target", action="store_true")
    args = ap.parse_args()

    open(args.out, "w", encoding="utf-8").close()
    t0 = time.time()
    print(f"[{t0:.0f}] heartbeat basladi")
    for k in range(args.beat):
        ts = time.time()
        with open(args.out, "a", encoding="utf-8") as fh:
            fh.write(f"[INFO] [{ts:.9f}] [radar]: HEARTBEAT\n")
            if args.with_target:
                fh.write(f"[WARN] [{ts:.9f}] [radar]: HEDEF: SIM_T1 ACI: 80 MESAFE: 40\n")
        time.sleep(1.0)
    print(f"[{time.time():.0f}] BAGLANTI KESILDI (log yazimi durdu) - {args.silence} sn bekleniyor")
    time.sleep(args.silence)


if __name__ == "__main__":
    main()
