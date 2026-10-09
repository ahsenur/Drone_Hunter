import csv
from datetime import datetime
import os

class VeriKaydedici:
    def __init__(self, dosya_adi="savunma_log.csv"):
        self.dosya_adi = dosya_adi
        if not os.path.exists(self.dosya_adi):
            with open(self.dosya_adi, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Zaman", "Tip", "ID", "Mesafe", "Saniye"])

    def kaydet(self, tip, id_no, mesafe, saniye):
        zaman = datetime.now().strftime("%H:%M:%S")
        with open(self.dosya_adi, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([zaman, tip, id_no, mesafe, saniye])