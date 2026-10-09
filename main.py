import cv2
import os
import threading
import time
import numpy as np
from ultralytics import YOLO
from src.acoustic_engine.analyzer import AkustikMotor
from src.fusion_core.blackbox import SavunmaKaraKutu

aktif_tehditler = []
gorsel_tespitler = []
canli_spektrum = None
kara_kutu = SavunmaKaraKutu()


def stratejik_radar_ciz(akustik, gorsel):
    radar = np.zeros((500, 500, 3), dtype=np.uint8) + 255
    merkez = (250, 250)
    for r in [50, 100, 150, 200, 240]:
        cv2.circle(radar, merkez, r, (235, 235, 235), 1)

    cv2.putText(radar, "KOMUTA MERKEZI - AR-GE PROTO_V1", (20, 40), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 0), 2)

    # Görsel Tespitler (Yeşil Merkez)
    for i, obj in enumerate(set(gorsel)):
        cv2.circle(radar, (merkez[0], merkez[1] - 10), 8, (0, 200, 0), -1)
        cv2.putText(radar, f"DOST: {obj.upper()}", (20, 80 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 0), 1)

    # Akustik Tespitler (Kırmızı Radar İzleri)
    for i, t in enumerate(akustik):
        aci = (i * 45 + time.time() * 25) % 360 * (np.pi / 180)
        r_px = int(t['metre'] * 4.8)
        x = int(merkez[0] + r_px * np.cos(aci))
        y = int(merkez[1] + r_px * np.sin(aci))

        cv2.circle(radar, (x, y), 7, (0, 0, 255), -1)
        cv2.putText(radar, f"ID:{t['id']}", (x + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # Binary Dosyaya Mühürle
        kara_kutu.veriyi_muhurle(int(t['id'][-1]), t['metre'], t['saniye'])

    return radar


def sistemi_baslat():
    global aktif_tehditler, canli_spektrum, gorsel_tespitler
    model = YOLO("yolov8n.pt")
    motor = AkustikMotor()

    def ses_loop():
        global aktif_tehditler, canli_spektrum
        while True:
            aktif_tehditler, canli_spektrum = motor.coklu_analiz_et()
            time.sleep(0.01)

    threading.Thread(target=ses_loop, daemon=True).start()
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    print("[INFO] Sistem Aktif. Çıkış için 'q' tuşuna basın.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        results = model(frame, conf=0.4, verbose=False)
        gorsel_tespitler = [model.names[int(box.cls[0])] for r in results for box in r.boxes]

        for r in results:
            for box in r.boxes:
                label = model.names[int(box.cls[0])]
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

        radar_ekrani = stratejik_radar_ciz(aktif_tehditler, gorsel_tespitler)

        # Radar Wave Çizimi
        if canli_spektrum is not None:
            gh, gw = 70, 150
            graph_bg = np.zeros((gh, gw, 3), dtype=np.uint8) + 30
            vals = np.clip(canli_spektrum[:gw] * 600, 0, gh - 5)
            for i in range(len(vals) - 1):
                cv2.line(graph_bg, (i, gh - int(vals[i])), (i + 1, gh - int(vals[i + 1])), (0, 255, 0), 1)
            frame[400:470, 10:160] = graph_bg

        cv2.imshow("RADAR HARITASI", radar_ekrani)
        cv2.imshow("TAKTIK AKIS", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()
    # PROGRAM KAPANIRKEN RAPOR VER
    kara_kutu.gorev_sonu_raporu()


if __name__ == "__main__":
    sistemi_baslat()