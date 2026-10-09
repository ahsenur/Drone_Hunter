import math


class DroneTakipMantigi:
    def __init__(self, ekran_genislik=640, ekran_yukseklik=480):
        # Ekranın orta noktaları
        self.merkez_x = ekran_genislik // 2
        self.merkez_y = ekran_yukseklik // 2

        # Karar toleransı (Küçük titremeleri engellemek için)
        self.tolerans = 35

        # İdeal hedef büyüklüğü (Mesafe tahmini için)
        self.ideal_alan = 25000

    def manevra_belirle(self, h_x, h_y, alan):
        """
        Hedefin merkezden sapmasına göre (SAG, SOL, ASAGI, YUKARI)
        ve kutu büyüklüğüne göre (YAKLAS, UZAKLAS) komut üretir.
        """
        dx = h_x - self.merkez_x
        dy = h_y - self.merkez_y

        komutlar = []

        # Yatay Kontrol
        if abs(dx) > self.tolerans:
            komutlar.append("SAG" if dx > 0 else "SOL")

        # Dikey Kontrol
        if abs(dy) > self.tolerans:
            komutlar.append("ASAGI" if dy > 0 else "YUKARI")

        # Mesafe Kontrolü (Alan üzerinden derinlik tahmini)
        if alan < self.ideal_alan - 8000:
            komutlar.append("YAKLAS")
        elif alan > self.ideal_alan + 8000:
            komutlar.append("UZAKLAS")

        return " | ".join(komutlar) if komutlar else "KILITLENDI"

    def tehdit_skoru_hesapla(self, h_x, h_y, alan):
        """
        Radar Filtresi: Hedef ne kadar büyük (yakın) ve
        merkeze ne kadar yakınsa skor o kadar yükselir.
        """
        # Merkeze olan Öklid uzaklığı
        mesafe_merkez = math.sqrt((h_x - self.merkez_x) ** 2 + (h_y - self.merkez_y) ** 2)

        # Alan (yakınlık) ve Merkez (nişangah) faktörlerinin birleşimi
        alan_faktor = alan / 1000
        merkez_faktor = mesafe_merkez / 10

        skor = alan_faktor - merkez_faktor
        return round(skor, 2)