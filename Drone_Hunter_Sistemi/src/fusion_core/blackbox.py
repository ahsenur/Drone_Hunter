import struct
import time
import os

class SavunmaKaraKutu:
    def __init__(self, dosya_adi="radar_data.bin"):
        # Dosya main.py ile aynı hizada oluşacak
        self.dosya_adi = dosya_adi
        self.format_yapisi = "dif f" # d:zaman, i:id, f:mesafe, f:saniye

    def veriyi_muhurle(self, hedef_id, mesafe, saniye):
        """Veriyi Binary (İkilik) formatta mühürler."""
        zaman = time.time()
        try:
            # C struct yapısıyla veriyi paketle
            paket = struct.pack(self.format_yapisi, zaman, hedef_id, float(mesafe), float(saniye))
            with open(self.dosya_adi, "ab") as f:
                f.write(paket)
        except Exception as e:
            print(f"KRİTİK HATA: Veri mühürlenemedi: {e}")

    def gorev_sonu_raporu(self):
        """Program kapandığında Binary veriyi analiz eder."""
        if not os.path.exists(self.dosya_adi):
            print("\n[!] Analiz edilecek kayıt bulunamadı.")
            return

        paket_boyutu = struct.calcsize(self.format_yapisi)
        toplam_paket = 0
        en_yakin = 999.0

        with open(self.dosya_adi, "rb") as f:
            while True:
                veri = f.read(paket_boyutu)
                if not veri: break
                toplam_paket += 1
                _, _, mesafe, _ = struct.unpack(self.format_yapisi, veri)
                if mesafe < en_yakin: en_yakin = mesafe

        print("\n" + "█"*45)
        print("   STRATEJİK OPERASYON ANALİZ RAPORU")
        print("█" + "-"*43 + "█")
        print(f" > İşlenen Binary Paket: {toplam_paket}")
        print(f" > En Yakın Temas: {en_yakin:.2f} metre")
        print(f" > Durum: Görev Başarıyla Tamamlandı")
        print("█"*45 + "\n")