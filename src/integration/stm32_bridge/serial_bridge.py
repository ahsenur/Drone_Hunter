from __future__ import annotations

from typing import Dict, List, Optional

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover
    serial = None


class STM32SerialBridge:
    """
    Fusion sonucunu STM32'nin anlayacagi basit komutlara cevirir.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.2) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self._last_payload: List[str] = []
        self._last_send_ts = 0.0

    def connect(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial kurulu degil. `pip install pyserial` calistirin.")
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def disconnect(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def encode_command(self, fused_command: Dict[str, object]) -> List[str]:
        commands: List[str] = []

        angle = fused_command.get("angle_deg")
        if angle is not None:
            commands.append(f"ANGLE:{int(angle):03d}")

        mode = fused_command.get("mode")
        if mode:
            commands.append(f"MODE:{mode}")

        threat_level = str(fused_command.get("threat_level", "low")).lower()
        alarm = 1 if threat_level in {"high", "critical"} else 0
        commands.append(f"ALARM:{alarm}")
        return commands

    def send_command(self, fused_command: Dict[str, object]) -> List[str]:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("Seri baglanti acik degil. Once connect() cagrin.")

        commands = self.encode_command(fused_command)
        if commands == self._last_payload:
            return commands
        for command in commands:
            self._serial.write((command + "\n").encode("ascii"))
        self._last_payload = commands[:]
        return commands
