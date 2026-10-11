# Calisma kaydi ve analiz

Orchestrator her calistirmada `data/records/dronehunter.db` (SQLite) dosyasina bir calisma (run) yazar.
Kapatmak icin `config/research/orchestrator_config.json` icinde `"recording": {"enabled": false}`.

| Tablo | Icerik |
|---|---|
| `runs` | her calistirma icin bir satir |
| `events` | sensorlerden gelen olaylar: kaynak, aci, mesafe, guven, olay zamani |
| `sensor_health` | sensor durum degisiklikleri: OK / STALE / FAULT / UNKNOWN, yas, neden |
| `decisions` | fuzyon karari: mod, tetikleyici, tehdit skoru, bozulan ve bayat kaynaklar (en az 0.2 sn aralikla, mod degisince hemen) |

## Analiz

    $env:PYTHONPATH = "src"
    python scripts\analyze_run.py            # son calisma
    python scripts\analyze_run.py --run 3

Cikti: modlarda gecen sure, mod gecisleri ve tetikleyicileri, sensor kesintileri (son saglikli veriden
tespite, karara ve toparlanmaya kadar gecen sure).

## Sinirlar

- Zamanlar orchestrator dongusunun hizina baglidir; dongu yavassa tespit gecikmesi zaman asimindan buyuk olur.
- `tests/test_recorder.py` simule saatle calisir (mantik testi). Gercek gecikme icin orchestrator'u calistirip
  `analyze_run.py` ciktisina bakin.
- Radar saglik bilgisi yalnizca radar log'unda `HEARTBEAT` satiri varsa uretilir (`scripts/simulate_radar_log.py`).
