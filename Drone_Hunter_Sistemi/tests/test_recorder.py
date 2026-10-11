import pathlib, sqlite3, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from integration import build_target_event
from research_core import MultiSensorPipeline, load_profile
from research_core.run_analysis import format_report, summarize
from research_core.run_recorder import RunRecorder
from research_core.sensor_health import SensorHealthMonitor


def vision_event(t):
    return build_target_event(source="vision", target_detected=True, target_id="v1", angle_deg=100.0,
                              distance_m=20.0, confidence=0.8, threat_level="medium", timestamp=t)


class RecorderEndToEndTest(unittest.TestCase):
    def simulate(self, db):
        """40 sn, 0.2 sn adim. Kamera hep var. Radar heartbeat'i 0-15 sn ve 30-40 sn arasinda gelir."""
        pipe = MultiSensorPipeline(load_profile(ROOT / "config/research/campus_perimeter_profile.json"))
        mon = SensorHealthMonitor(timeouts={"radar": 5.0})
        rec = RunRecorder(db, label="test", clock=lambda: 1000.0)
        t0, k = 1000.0, 0
        while k * 0.2 <= 40.0:
            t = t0 + k * 0.2
            rel = k * 0.2
            mon.heartbeat("vision", now=t)
            if (rel < 15.0 or rel >= 30.0) and abs(rel - round(rel)) < 1e-6:     # saniyede bir heartbeat
                mon.heartbeat("radar", now=t)
            ev = vision_event(t)
            res = pipe.process(vision_event=ev, now=t, sensor_status=mon.snapshot(now=t))
            rec.record_tick(t, {"vision": ev, "radar": None}, mon.details(now=t), res)
            k += 1
        rec.close()

    def test_link_loss_latency_and_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            db = pathlib.Path(d) / "t.db"
            self.simulate(db)
            s = summarize(db)
            print("\n" + format_report(s))

            conn = sqlite3.connect(db)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 100)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 20)
            conn.close()

            self.assertAlmostEqual(s["duration_s"], 40.0, delta=0.3)
            self.assertIn("NORMAL", s["mode_durations_s"])
            self.assertNotIn(None, s["mode_durations_s"])
            self.assertTrue(any(t["to"] == "LOCAL_SENSOR_HOLD" and t["trigger"] == "heartbeat_timeout"
                                for t in s["transitions"]))

            radar = [o for o in s["outages"] if o["source"] == "radar"]
            self.assertEqual(len(radar), 1)
            o = radar[0]
            self.assertAlmostEqual(o["t_last_ok_s"], 14.0, delta=0.3)          # son heartbeat t=14
            self.assertGreater(o["detected_after_s"], 5.0)                      # zaman asimi 5 sn
            self.assertLess(o["detected_after_s"], 5.5)
            self.assertLess(o["decision_after_s"], 5.7)                         # karar ayni adimda degisir
            self.assertTrue(o["recovered"])
            self.assertLess(o["recovery_after_s"], 0.5)

    def test_recorder_never_stores_none_event(self):
        with tempfile.TemporaryDirectory() as d:
            db = pathlib.Path(d) / "t.db"
            self.simulate(db)
            conn = sqlite3.connect(db)
            sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM events")}
            conn.close()
            self.assertEqual(sources, {"vision"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
