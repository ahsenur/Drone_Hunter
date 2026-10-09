# Radar Observer

Bu klasor radar projesine dokunmadan disaridan izleme yapmak icin kullanilir.

## Temel Mantik

- Radar projesi kendi halinde calisir.
- Bu gozlemci radar cikti kanalini disaridan okur.
- Yeni event bulursa `records/` altina ayri JSON kaydi atar.

## Baslatma

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_radar_observer.ps1
```

Isterseniz farkli config dosyasi da verebilirsiniz:

```powershell
python src\integration\observer\run_watcher.py data\integration\radar_observer_config.json
```
