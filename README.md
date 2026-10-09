# DroneHunter

Cok sensorlu (kamera + akustik + radar) drone tespit ve karar destek prototipi. Tez konusu:
**cok sensorlu veri fuzyonunun, tek sensore gore kazancini bozulmus kosullarda (dusuk gorus, gurultu,
baglanti kaybi) olcmek.**

Bu bir arastirma prototipidir; saha dogrulamasi yapilmamistir.

## Mevcut durum (dürüst tablo)

| Bilesen | Durum | Not |
|---|---|---|
| Kamera tespiti | Calisiyor, **drone icin degil** | Hazir COCO YOLOv8n; COCO'da drone sinifi yok. Drone verisiyle ince ayar planli. |
| Akustik siniflandirma | Calisiyor (kaba) | Tek mikrofon, 4 frekans bandi enerjisi. Dogrulanmadi. |
| Akustik mesafe | Yaklasik/uydurma | Enerjiden formulle uretiliyor, fiziksel olcum degil. |
| Akustik yon (TDOA) | **Algoritma var, sentetik testte dogrulandi** | `src/acoustic_engine/tdoa.py` (GCC-PHAT). Iki mikrofonlu donanimda test edilmedi, orchestrator'a bagli degil. |
| Radar | **Simulasyon** | ROS2 turtlesim (`external/`). `Delta`, hedef yon dogrusu ile sabit bir hiperbol arasindaki kesisim diskriminantidir; konumlama degil geometrik testtir. Ayrintilar: `external/README.md`. |
| Fuzyon | Calisiyor (kural tabanli) | Agirlikli aci ortalamasi, taze olay secimi. Veri iliskilendirme yok (aktif her sey tek hedef). |
| Zaman asimi / bayat veri | **Yeni, testli** | Kaynak basina azami olay yasi; asan olay fuzyondan cikar. |
| Sensor sagligi | **Yeni, testli** | OK / STALE / FAULT / UNKNOWN. "Hedef yok" ile "sensor bozuk" ayrilir. |
| RF bozulma modu | Kismen | Tetikleyici 1: radar metninde "ILETISIM KESINTISI" (`Delta>0` etiketi, simulasyonda neredeyse hep aktif, RF olcumu degil). Tetikleyici 2 (yeni): radar heartbeat zaman asimi. Gercek jammer testi yok. |
| Tehdit skoru, dost/dusman | Calisiyor | Elle ayarlanmis agirliklarla kural tabanli, aciklanabilir. |
| Termal | Kod var, kapali | Donanim yok. |
| STM32 | Kopru kodu var, kapali | Karttaki yazilim yalnizca LED yakiyor, komutlari okumuyor. |

## Tez dogrultusunda yapilan degisiklikler

1. **Sessiz hata yutma kaldirildi** (`analyzer.py`): mikrofon bozulursa `last_error` doluyor.
2. **Radar zaman damgasi duzeltildi** (`radar_bridge.py`): olaylar okundugu anda damgalaniyordu, bu yuzden
   eski bir log satiri TTL'e takilmadan sonsuza kadar "taze" kaliyordu. Artik satirdaki ROS epoch damgasi,
   yoksa dosya yazilma zamani kullaniliyor. Sinir: damga WSL saatine aittir; Windows saatiyle farkliysa
   bayatlik hesabi sapar.
   **Delta'dan aci uretilmiyor:** Delta bir yol farki degil diskriminant oldugu icin eski `asin` donusumu
   (her zaman ~39 derece uretiyordu) varsayilan olarak kapatildi (`delta_is_path_difference`). Radar izi artik
   aci tasimiyor; ekranda aci yoksa 90 derece varsayilan olarak cizilir.
3. **Bayat olay eleme** (`fusion_center.drop_stale`, kaynak basina azami yas).
4. **Sensor saglik izleyici** (`research_core/sensor_health.py`) ve orchestrator'a baglanti.
5. **Heartbeat tabanli baglanti kaybi**: radar log'una `HEARTBEAT` satiri yazilirsa, durdugunda
   `LOCAL_SENSOR_HOLD` / `SAFE_ALERT` modlari anahtar kelime olmadan da tetiklenir. Heartbeat satiri hic yoksa
   radar durumu UNKNOWN kalir, yanlis alarm uretilmez.
6. **Secilebilir birlestirme kurali** (`ThreatScorer(aggregation="mean"|"noisy_or")`). Varsayilan hala `mean`.
7. **TDOA yon kestirimi** (`acoustic_engine/tdoa.py`), sentetik testte dogrulandi.
8. **Goreli yollar**: config'teki mutlak `C:/Users/...` yollari kaldirildi.

## Testler

```
PYTHONPATH=src python tests/test_degradation.py
PYTHONPATH=src python tests/test_tdoa.py
```

TDOA testi idealize sentetik sinyal kullanir (yansima, ruzgar, mikrofon farki yok); gercek ortamdaki
dogrulugu gostermez.

## Bozulma deneyi (iskelet)

```
PYTHONPATH=src python experiments/degradation_eval.py
```

**Sentetik ve varsayimsal.** `SENSOR_MODEL` tablosundaki sayilar olculmus degildir; uretilen CSV bir performans
sonucu olarak alintilanmamalidir. Amac, metrik kodunu ve boru hattinin bozulma altindaki davranisini hazir
tutmaktir. Gercek kayitlar gelince `build_stream` benzeri bir fonksiyonla ayni metrikler hesaplanacak.

Iskeletin gosterdigi yapisal bir nokta: `mean` birlestirmede zayif bir sensor eklemek guclu bir tespitin
skorunu dusurebilir. Tezde bu, birlestirme kuralinin karsilastirilmasi icin bir arastirma sorusudur.

## Planli (henuz yok)

- Drone iceren acik veri seti / kendi kayitlariyla kamera modelinin ince ayari
- Cok mikrofonlu dizi ile TDOA'nin gercek donanimda testi
- Iz eslestirme (veri iliskilendirme) ve zaman senkronizasyonu
- Radar kodunda periyodik HEARTBEAT satiri (C++ tarafi; `scripts/simulate_radar_log.py` ayni formati simule eder)
- Radar simulasyonunda kontrollu baglanti kaybi senaryosu (su an "ILETISIM KESINTISI" mesaji hemen her zaman aktif)
- Gercek RF/baglanti bozulmasi ile saha testi
- Gercek kayitlarla tek sensor / fuzyon karsilastirmasi

## Calistirma

```
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\run_orchestrator_demo.ps1
```
