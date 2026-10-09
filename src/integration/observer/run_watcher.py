from __future__ import annotations

import json
import sys
from pathlib import Path

from integration.bridge.radar_bridge import RadarBridge
from integration.observer.event_recorder import EventRecorder
from integration.observer.radar_watcher import RadarWatcher


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_config_path() -> Path:
    return _project_root() / "data" / "integration" / "radar_observer_config.json"


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config bulunamadi: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    config_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else _default_config_path()
    config = _load_config(config_path)

    source = config.get("source", {})
    output = config.get("output", {})
    observer = config.get("observer", {})

    bridge = RadarBridge(
        json_path=source.get("json_path"),
        text_log_path=source.get("text_log_path"),
    )

    records_dir = Path(output.get("records_dir", _project_root() / "data" / "integration" / "records"))
    if not records_dir.is_absolute():
        records_dir = (_project_root() / records_dir).resolve()

    recorder = EventRecorder(output_dir=str(records_dir))
    watcher = RadarWatcher(bridge=bridge, poll_interval=float(observer.get("poll_interval", 0.5)))

    print(f"[observer] config: {config_path}")
    print(f"[observer] records dir: {records_dir}")
    print("[observer] izleme basladi")

    def _handle_event(event):
        path = recorder.record_event(event)
        print(f"[observer] event kaydedildi: {path}")

    watcher.watch_forever(_handle_event)


if __name__ == "__main__":
    main()
