import time
import os


def monitor_baslat():
    log_dosyasi = "savunma_log.csv"
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== TEKNIK IZLEME TERMINALI BASLATILIYOR ===")

    while True:
        try:
            if os.path.exists(log_dosyasi):
                # Dosyayı "paylaşımlı" modda açıyoruz (main.py yazarken hata vermemesi için)
                with open(log_dosyasi, "r", encoding="utf-8", errors="ignore") as f:
                    satirlar = f.readlines()

                    if len(satirlar) > 1:
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print("=== CANLI AKUSTIK HESAPLAMA MERKEZI ===")
                        print(f"Sistem Saati: {time.strftime('%H:%M:%S')} | Durum: AKIS CANLI")
                        print("-" * 55)
                        print(f"{'ZAMAN':<10} | {'ID':<3} | {'MESAFE':<8} | {'VARIS (SN)'}")
                        print("-" * 50)

                        # Sadece son 15 akustik veriyi göster
                        akustik_liste = [s for s in satirlar if "AKUSTIK" in s]
                        for satir in akustik_liste[-15:]:
                            d = satir.strip().split(",")
                            if len(d) >= 5:
                                print(f"{d[0]:<10} | {d[2]:<3} | {d[3]:<8} | {d[4]}")
                    else:
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print(f"[{time.strftime('%H:%M:%S')}] Veri bekleniyor (Sinyal aranıyor...)...")
            else:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"[{time.strftime('%H:%M:%S')}] Log dosyası oluşturuluyor...")

        except Exception:
            # Dosya o an yazılıyorsa kısa bir saniye bekle
            pass

        time.sleep(0.2)  # Göz yormayan tazeleme hızı


if __name__ == "__main__":
    monitor_baslat()