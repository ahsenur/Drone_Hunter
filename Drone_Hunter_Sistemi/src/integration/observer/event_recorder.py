from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from integration import TargetEvent


class EventRecorder:
    """
    Integration katmaninda toplanan event'leri ayri bir klasore kaydeder.

    Bu kayitlar radar projesinin icine yazilmaz.
    """

    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_event(self, event: TargetEvent, prefix: str = "radar_event") -> Path:
        safe_ts = str(event.timestamp).replace(".", "_")
        filename = f"{prefix}_{safe_ts}.json"
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump(event.to_dict(), handle, ensure_ascii=False, indent=2)
        return path

    def record_many(self, events: Iterable[TargetEvent], prefix: str = "radar_event") -> None:
        for event in events:
            self.record_event(event, prefix=prefix)
