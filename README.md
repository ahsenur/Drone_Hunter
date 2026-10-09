# Drone_Hunter

Cok sensorlu (kamera + akustik + radar) drone tespit ve karar destek prototipi. Tez yonu: **cok sensorlu veri fuzyonunun, tek sensore gore kazancini bozulmus kosullarda (dusuk gorus, gurultu, baglanti kaybi) olcmek.**

Repo iki parcadan olusur:

| Klasor | Icerik | Durum |
|---|---|---|
| [`Drone_Hunter_Sistemi/`](Drone_Hunter_Sistemi/) | Python tarafi: kamera, akustik ve radar (simulasyon) fuzyonu, tehdit skoru, sensor sagligi ve bozulma yonetimi, testler, deney iskeleti | Calisan arastirma prototipi, saha dogrulamasi yok |
| [`Otonom_drone_sistemi/`](Otonom_drone_sistemi/) | STM32F446xE kart yazilimi (CMake projesi) | Temel iskelet: su an yalnizca LED yakip sondurur, PC'den gelen komutlari okumaz |

Iki taraf arasindaki seri koprunun PC tarafi `Drone_Hunter_Sistemi/src/integration/stm32_bridge/` altinda yer alir, varsayilan olarak kapalidir.

## Durum ozeti

Ayrintili "calisiyor / simulasyon / planli" tablosu icin [`Drone_Hunter_Sistemi/README.md`](Drone_Hunter_Sistemi/README.md) dosyasina bakin. Kisaca:

- Kamera hazir bir COCO modeli kullanir, drone sinifi yoktur (drone icin ince ayar planli).
- Radar bir ROS2 turtlesim simulasyonudur, gercek sensor yoktur.
- Akustikte yon bilgisi su an olculmez; TDOA modulu yazildi ve yalnizca sentetik sinyalde dogrulandi.
- Fuzyon kural tabanlidir; zaman senkronizasyonu ve iz eslestirme tezin ana konularidir.

## Hizli baslangic

    cd Drone_Hunter_Sistemi
    pip install -r requirements.txt
    $env:PYTHONPATH = "src"
    python tests\test_degradation.py