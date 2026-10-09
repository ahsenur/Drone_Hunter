param(
    [string]$ConfigPath = "data/integration/radar_observer_config.json"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"

python "src/integration/observer/run_watcher.py" $ConfigPath
