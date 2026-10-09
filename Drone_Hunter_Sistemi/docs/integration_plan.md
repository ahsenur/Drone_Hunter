# Integration Plan

Bu dosyalar mevcut radar projesine dokunmadan kullanilmak uzere olusturuldu.

## Uygulama Sirasi

1. `schemas/target_event.example.json`
   Ortak veri formatini referans al.
2. `bridge/radar_bridge.py`
   Radar verisini bu formata cevir.
3. `fusion/fusion_center.py`
   Radar + kamera + ses verisini birlestir.
4. `stm32_bridge/serial_bridge.py`
   Son karari STM32'ye yolla.

## Test Sirasi

1. `RadarBridge.create_manual_event()` ile test event'i olustur.
2. `FusionCenter.fuse()` ile tek radar event'ini fuse et.
3. `FusionCenter.build_command()` ile STM32 komutunu uret.
4. STM32 bagliyken `STM32SerialBridge.send_command()` ile seri cikisi dene.
