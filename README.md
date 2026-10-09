DroneHunter: Bozulma Modu Ekran Görüntüsü Değerlendirmesi
9 Ekim 2026 · Orkestratör ve hologram ekranlarının değerlendirmesi
Sonuç
Bozulma modu çalışıyor. Sol panelde Radar tracks: 0 ve hologramda RADAR: IDLE görünüyor. Sistem akustik destekli moda geçmiş, alttaki not da buna uyuyor: rf bozulmasi var; akustik destekli güvenli izleme aktif.
Bir düzeltme: daha önce iki mod söylemiştim (LOCAL_SENSOR_HOLD, SAFE_ALERT), ama üçüncü bir mod da var. Kamera hedef görmüyor ama akustik izi varsa ACOUSTIC_RESILIENCE seçiliyor. Yani ekran, kodun tasarımına uygun davranmış.
Bu görüntülerin kanıtlamadığı şeyler
• Geçişi göstermiyorlar. Simülatörün son heartbeat'i yaklaşık 09:48'de yazıldı, sessizlik 09:49'da bitti, görüntüler 09:50'de alındı. Yani bozulma sonrası durum yakalanmış. "Önce NORMAL, sonra bozulma, sonra toparlanma" dizisine hâlâ ihtiyaç var.
• Neyin tetiklediği ekranda görünmüyor. Simülatörün log'unda "iletişim kesintisi" yazısı yok, yani en büyük ihtimalle tetikleyici heartbeat zaman aşımı. Ama ekran bunu göstermiyor, bu yüzden kesin değil.
Mentörlere göstermeden önce bilinmesi gerekenler
1. AZIMUTH 035 DEG ve Command angle: 35 ölçülmüş bir yön değil. Tek mikrofonla yön bulunamıyor. Bu açı, tespit edilen frekans bandına atanmış sabit bir değer. Mesafe ("çok yakın temas") de enerjiden formülle üretiliyor. Biri "bu açıyı nasıl buluyorsun" derse: "Akustikte şu an yalnızca sektör bilgisi var. Gerçek yön için TDOA modülünü yazdım ama çok mikrofonlu donanım henüz yok."
2. Kamera karesi gelmiyor görünüyor. Sol panelde kilit simgesi ve Vision count: 0 var. Büyük ihtimalle Windows kamera izni kapalı ya da başka bir uygulama kamerayı kullanıyor, ama bu kesin değil. Ayarlar > Gizlilik > Kamera'dan masaüstü uygulamalarına izin verildiğine bakılmalı, Teams ve Zoom gibi uygulamalar kapatılmalı. Kamera düzelirse sistem LOCAL_SENSOR_HOLD moduna geçebilir, bunu da göstermek iyi olur.
3. Sensör sağlığı ekranda görünmüyor. Kamera arızası (FAULT) şu an yalnızca iç veride tutuluyor. Hologramdaki IDLE / ACTIVE, "hedef var mı" demek, "sensör sağlıklı mı" demek değil. Mentörlerin "veri gelmezse ne olur" sorusunu ekranda göstermek için OK / STALE / FAULT durumlarını SENSOR LINKS paneline eklemek mantıklı olur.
Şimdi yapılacaklar
1. Kamerayı düzelt.
2. Orkestratörü aç.
3. Simülatörü --beat 30 --silence 30 ile başlat.
4. Üç ekran görüntüsü al: normal, bozulma, toparlanma.
Sensör sağlığının ekrana eklenmesi istenirse, küçük bir değişiklikle yapılabilir.
