# external/ - ROS2 radar simulasyonu (WSL, ROS2 Humble)

Iki ROS2 paketinden olusur; ikisi de **turtlesim uzerinde simulasyondur**, gercek radar sensoru yoktur.

| Paket | Dosya | Ne yapar |
|---|---|---|
| `iha_savunma_sistemi` (`radar_clone/`) | `hiperbolik_kontrol.py` | Avci kaplumbagayi hedef kaplumbagalara yonlendirir, "analiz suresi" sayar, hedefi etkisiz hale getirir. "Hiperbolik kacis manevrasi" yalnizca bir hareket adidir, konumlama yapmaz. |
| `iha_radar_sistemi` | `src/radar.cpp` (derlenen) | turtle1 ve turtle2 poz mesajlarini dinler. turtle2'nin yon dogrusu ile **sabit bir hiperbol** (x²/a² - y²/b² = 1, a=2, b=1.5, merkez=arena koordinat orijini) arasindaki kesisim diskriminantini hesaplar (`Delta`). `Delta > 0` ise "ANALITIK RISK ... ILETISIM KESINTISI!" yazar. |
| | `src/radar_filtresi.cpp` | CMake'e eklenmemis, derlenmiyor (eski surum). |

## Delta ne anlama gelir, ne anlama gelmez

`Delta = 4a²b²(n² + b² - a²m²)`, burada `m = tan(theta)`, `n = y - m·x` hedefin yon dogrusunun (y = mx + n) katsayilaridir. Bu, dogru ile hiperbolun kesisim denkleminin diskriminantidir (sayisal olarak dogrulandi).

- `Delta > 0` yalnizca "hedefin yon dogrusu bu sabit hiperbolu iki noktada kesiyor" demektir. Dogru sonsuz uzunluk varsayilir, yani hedef hiperbole dogru gidiyor olmak zorunda degildir.
- Hiperbolun odaklari (±2.5, 0), 2a = 4: iki alicinin (±2.5, 0) konumunda oldugu ve yol farkinin 4 birim olduguna karsilik gelen bir egridir. Ancak kod olculmus bir gecikme/yol farki kullanmaz; yalnizca hedef pozuyla sabit egriyi karsilastirir. Bu bir **konumlama** degil, geometrik bir **kesisim testidir**.
- Mesajdaki "ILETISIM KESINTISI" ifadesi RF'ten veya bir baglanti olcumunden gelmez, `Delta > 0` kosulunun etiketidir.
- turtlesim'de hedefler `theta = 0` ile baslar; bu durumda yon dogrusu yataydir ve `Delta = 36·(n² + 2.25)` her zaman pozitiftir. turtle2 icin (9.5, 9.5) baslangicinda `Delta = 3330.00` (loglarda gorulen deger). Hedef vuruldugunda poz guncellenmeyince, son poz turtle1 mesajlariyla (~60 Hz) tekrar tekrar degerlendirilir; bu yuzden ayni satir saniyede onlarca kez basilir.

Sonuc: bu simulasyonda "ILETISIM KESINTISI" mesaji neredeyse her zaman aktiftir ve gercek bir bozulma senaryosunu temsil etmez. Bozulma deneyleri icin kontrollu bir tetikleyici (`scripts/simulate_radar_log.py` ya da radar kodunda heartbeat) kullanilmalidir.

## Derleme (WSL)

```
cd ~/inufest_ws && colcon build --packages-select iha_savunma_sistemi iha_radar_sistemi
source install/setup.bash && ros2 launch iha_savunma_sistemi savunma_sistemi.launch.py
```
