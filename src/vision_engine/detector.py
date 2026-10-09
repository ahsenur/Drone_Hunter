import cv2
from ultralytics import YOLO
import torch


def start_vision():
    # 1. Modeli Yukle (Nano surumu - RAM dostu)
    print("Yapay zeka modeli yukleniyor, lutfen bekleyin...")
    model = YOLO("yolov8n.pt")

    # 2. Kamerayi Baslat
    # Eger harici kamera kullaniyorsan 0 yerine 1 dene
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("HATA: Kamera acilamadi! Baglantiyi kontrol edin.")
        return

    print("Sistem Aktif! Kapatmak icin 'q' tusuna basin.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 3. Yapay Zeka Tahmini (Guven esigi %40)
        results = model(frame, conf=0.4)

        # 4. Sonuclari Kareye Ciz
        annotated_frame = results[0].plot()

        # 5. Ekranda Goster
        cv2.imshow("Drone Hunter - Yapay Zeka Gozu", annotated_frame)

        # 'q' tusuna basilinca donguden cik
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Kaynaklari serbest birak
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_vision()