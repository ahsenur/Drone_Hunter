import os, sys, pathlib, tempfile, time, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from integration import build_target_event
from integration.bridge.radar_bridge import RadarBridge
from research_core import MultiSensorPipeline, load_profile
from research_core.sensor_health import SensorHealthMonitor


def ev(source, t, angle=90.0, dist=20.0, conf=0.8, raw=None):
    meta = {"raw_line": raw} if raw else {}
    return build_target_event(source=source, target_detected=True, target_id=f"{source}_1",
                              angle_deg=angle, distance_m=dist, confidence=conf,
                              threat_level="medium", timestamp=t, metadata=meta)


class SensorHealthTest(unittest.TestCase):
    def test_states(self):
        h = SensorHealthMonitor()
        self.assertEqual(h.status("vision", now=100).state, "UNKNOWN")
        h.heartbeat("vision", now=100)
        self.assertEqual(h.status("vision", now=100.5).state, "OK")        # calisiyor, hedef olmasa da
        self.assertEqual(h.status("vision", now=102.5).state, "STALE")     # 1 sn timeout asildi
        h.fault("vision", "kare okunamadi")
        self.assertEqual(h.status("vision", now=100.5).state, "FAULT")
        h.heartbeat("vision", now=103)
        self.assertEqual(h.status("vision", now=103.2).state, "OK")        # toparlandi


class PipelineDegradationTest(unittest.TestCase):
    def setUp(self):
        self.pipe = MultiSensorPipeline(load_profile(ROOT / "config/research/campus_perimeter_profile.json"))
        self.t0 = 1000.0

    def test_stale_event_is_dropped(self):
        r = self.pipe.process(vision_event=ev("vision", self.t0 - 5.0), now=self.t0)
        self.assertIn("vision", r.stale_sources)
        self.assertFalse(r.fused_event.target_detected)

    def test_fresh_event_is_used(self):
        r = self.pipe.process(vision_event=ev("vision", self.t0 - 0.2), now=self.t0)
        self.assertTrue(r.fused_event.target_detected)
        self.assertEqual(r.stale_sources, [])

    def test_heartbeat_timeout_triggers_link_loss_mode(self):
        r = self.pipe.process(vision_event=ev("vision", self.t0 - 0.1), now=self.t0,
                              sensor_status={"radar": "STALE", "vision": "OK"})
        self.assertEqual(r.resilience_mode, "LOCAL_SENSOR_HOLD")
        self.assertEqual(r.fused_event.metadata["resilience_trigger"], "heartbeat_timeout")
        self.assertIn("radar", r.fused_event.metadata["degraded_sources"])

    def test_keyword_trigger_still_works_with_fresh_radar(self):
        radar = ev("radar", self.t0 - 0.1, raw="ILETISIM KESINTISI!")
        r = self.pipe.process(radar_event=radar, vision_event=ev("vision", self.t0 - 0.1), now=self.t0)
        self.assertEqual(r.resilience_mode, "LOCAL_SENSOR_HOLD")
        self.assertEqual(r.fused_event.metadata["resilience_trigger"], "keyword")

    def test_stale_keyword_does_not_hold_alarm_forever(self):
        radar = ev("radar", self.t0 - 60.0, raw="ILETISIM KESINTISI!")
        r = self.pipe.process(radar_event=radar, vision_event=ev("vision", self.t0 - 0.1), now=self.t0)
        self.assertEqual(r.resilience_mode, "NORMAL")

    def test_camera_fault_is_reported_not_hidden(self):
        r = self.pipe.process(acoustic_event=ev("acoustic", self.t0 - 0.1), now=self.t0,
                              sensor_status={"vision": "FAULT", "acoustic": "OK"})
        self.assertIn("vision", r.command["degraded_sources"])
        self.assertTrue(r.fused_event.target_detected)    # akustikle izleme surer


class RadarBridgeTimestampTest(unittest.TestCase):
    def test_old_log_event_gets_old_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "radar.log"
            log.write_text("[WARN] ANALITIK RISK: Delta=3350.00 > 0!\n", encoding="utf-8")
            old = time.time() - 120
            os.utime(log, (old, old))
            bridge = RadarBridge(text_log_path=str(log))
            event = bridge.load_recent_events_from_text(limit=5)[-1]
            self.assertAlmostEqual(event.timestamp, old, delta=1.0)
            self.assertIsNone(bridge.last_heartbeat_ts())              # heartbeat satiri yok -> bilinmiyor
            log.write_text("[INFO] HEARTBEAT\n", encoding="utf-8")
            self.assertIsNotNone(bridge.last_heartbeat_ts())


class AnalyzerFaultTest(unittest.TestCase):
    def test_microphone_error_is_visible(self):
        try:
            from acoustic_engine import analyzer
        except Exception as exc:
            self.skipTest(f"analyzer import edilemedi: {exc}")
        def boom(*a, **k):
            raise OSError("mikrofon yok")
        analyzer.sd.rec = boom
        motor = analyzer.AkustikMotor()
        threats, spec = motor.coklu_analiz_et()
        self.assertEqual(threats, [])
        self.assertIn("mikrofon yok", motor.last_error)


class RadarLineFormatTest(unittest.TestCase):
    ROS_LINE = "[WARN] [1791306831.296023452] [radar]: ANALITIK RISK: Delta=3330.00 > 0! ILETISIM KESINTISI!"

    def test_ros_timestamp_is_read_and_no_angle_is_invented(self):
        ev_ = RadarBridge().parse_text_line(self.ROS_LINE)
        self.assertAlmostEqual(ev_.timestamp, 1791306831.296, places=2)
        self.assertEqual(ev_.metadata["timestamp_source"], "line")
        self.assertIsNone(ev_.angle_deg)                       # Delta bir yol farki degil
        self.assertEqual(ev_.metadata["delta_value"], 3330.0)
        self.assertEqual(ev_.metadata["delta_meaning"], "line_hyperbola_discriminant")

    def test_legacy_delta_angle_is_opt_in(self):
        ev_ = RadarBridge(delta_is_path_difference=True).parse_text_line(self.ROS_LINE)
        self.assertAlmostEqual(ev_.angle_deg, 39.4, delta=0.2)

    def test_line_timestamp_beats_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "radar.log"
            log.write_text(self.ROS_LINE + "\n", encoding="utf-8")        # dosya simdi yazildi
            event = RadarBridge(text_log_path=str(log)).load_recent_events_from_text(limit=3)[-1]
            self.assertAlmostEqual(event.timestamp, 1791306831.296, places=2)   # mtime degil

    def test_heartbeat_time_comes_from_line(self):
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "radar.log"
            log.write_text("[INFO] [1791306800.500000000] [radar]: HEARTBEAT\n[WARN] [1791306900.0] [radar]: x\n",
                           encoding="utf-8")
            self.assertAlmostEqual(RadarBridge(text_log_path=str(log)).last_heartbeat_ts(), 1791306800.5, places=2)

    def test_constant_radar_message_expires_with_real_timestamps(self):
        """Ekran goruntusundeki durum: ayni mesaj surekli basiliyor. Satir zamanina gore bayatlayinca alarm birakilmali."""
        pipe = MultiSensorPipeline(load_profile(ROOT / "config/research/campus_perimeter_profile.json"))
        radar = RadarBridge().parse_text_line(self.ROS_LINE)
        fresh = pipe.process(radar_event=radar, now=radar.timestamp + 0.5)
        stale = pipe.process(radar_event=radar, now=radar.timestamp + 30.0)
        self.assertEqual(fresh.fused_event.metadata["resilience_trigger"], "keyword")   # taze mesaj: simulasyon mesajina tepki
        self.assertNotEqual(fresh.resilience_mode, "NORMAL")
        self.assertEqual(stale.resilience_mode, "NORMAL")
        self.assertIn("radar", stale.stale_sources)


class SimulatorTest(unittest.TestCase):
    def test_simulated_log_goes_silent(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from simulate_radar_log import build_lines
        lines = build_lines(1000.0, 5, True)
        self.assertEqual(len([l for l in lines if "HEARTBEAT" in l[1]]), 5)
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "r.log"
            log.write_text("\n".join(l[1] for l in lines) + "\n", encoding="utf-8")
            b = RadarBridge(text_log_path=str(log))
            hb = b.last_heartbeat_ts()
            self.assertAlmostEqual(hb, 1004.0, places=1) if hb < 5000 else None
            mon = SensorHealthMonitor()
            mon.heartbeat("radar", now=hb)
            self.assertEqual(mon.status("radar", now=hb + 2).state, "OK")
            self.assertEqual(mon.status("radar", now=hb + 8).state, "STALE")   # 5 sn timeout asildi


if __name__ == "__main__":
    unittest.main(verbosity=2)
