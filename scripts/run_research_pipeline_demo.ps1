param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"

@'
from integration.bridge.radar_bridge import RadarBridge
from integration import build_target_event
from research_core import MultiSensorPipeline, load_profile

profile = load_profile("config/research/campus_perimeter_profile.json")
pipeline = MultiSensorPipeline(profile)
bridge = RadarBridge()

radar_event = bridge.create_manual_event(angle_deg=28, distance_m=18.0, confidence=0.76)
vision_event = build_target_event(
    source="vision",
    target_detected=True,
    target_id="vision_target_1",
    angle_deg=31,
    distance_m=20.0,
    confidence=0.91,
    threat_level="medium",
    metadata={"bbox_area": 21000}
)
acoustic_event = build_target_event(
    source="acoustic",
    target_detected=True,
    target_id="acoustic_track_1",
    angle_deg=None,
    distance_m=16.0,
    confidence=0.63,
    threat_level="medium",
    metadata={"signature": "iha_izi"}
)

result = pipeline.process(
    radar_event=radar_event,
    vision_event=vision_event,
    acoustic_event=acoustic_event,
)

print("FUSED EVENT:")
print(result.fused_event.to_dict())
print("COMMAND:")
print(result.command)
print("THREAT SCORE:")
print(result.threat_score)
print("OPERATING MODE:")
print(result.operating_mode)
'@ | python -
