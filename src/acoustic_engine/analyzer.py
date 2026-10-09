import time

import numpy as np
import librosa
import sounddevice as sd


class AkustikMotor:
    def __init__(self):
        self.sr = 22050
        # Sensor sagligi: son basarili okuma ve son hata. "hedef yok" ile "mikrofon bozuk"
        # ayrimi icin kullanilir (eskiden ikisi de [] donuyordu).
        self.last_ok_ts = None
        self.last_error = None
        self.saniye = 0.5
        self.freq_araliklari = [
            {"name": "vehicle_engine", "label": "ARABA", "f_min": 80, "f_max": 420, "risk": "low"},
            {"name": "human_voice", "label": "INSAN", "f_min": 420, "f_max": 1100, "risk": "low"},
            {"name": "rotary_uav", "label": "IHA", "f_min": 1100, "f_max": 3200, "risk": "medium"},
            {"name": "rocket_like_high_energy", "label": "ROKET_BENZERI", "f_min": 3200, "f_max": 7000, "risk": "high"},
        ]

    def coklu_analiz_et(self):
        try:
            kayit = sd.rec(int(self.saniye * self.sr), samplerate=self.sr, channels=1)
            sd.wait()
            audio_data = kayit.flatten()
            if np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))

            S = np.abs(librosa.stft(audio_data))
            freqs = librosa.fft_frequencies(sr=self.sr)
            spektrum_ozeti = np.mean(S, axis=1)

            if audio_data.size == 0:
                raise RuntimeError("mikrofondan bos kayit geldi")

            tehditler = []
            for i, band in enumerate(self.freq_araliklari):
                f_min = band["f_min"]
                f_max = band["f_max"]
                idx = np.where((freqs >= f_min) & (freqs <= f_max))[0]
                if len(idx) == 0:
                    continue
                enerji = np.mean(S[idx, :])
                tutarlilik = np.std(S[idx, :])
                dominant_idx = idx[np.argmax(spektrum_ozeti[idx])]
                dominant_freq = float(freqs[dominant_idx])

                # AR-GE: Harmonik Kararlılık Kontrolü
                if enerji > 0.005:
                    mesafe = int(np.clip(50 - (enerji * 450), 2, 50))
                    saniye = round(float(mesafe / 20), 2)

                    # Drone sesleri daha 'dar bantlı' ve 'stabil'dir
                    tip = "IHA_IZI" if tutarlilik < 0.055 else "SINYAL"
                    if tip == "IHA_IZI" and band["label"] in {"UAV_HARMONIC", "SMALL_DRONE_SIGNATURE"}:
                        tip = "IHA_MOTORU"

                    tehditler.append({
                        'id': f"HEDEF-{i + 1}",
                        'band_name': band["name"],
                        'band_label': band["label"],
                        'frekans_min': f_min,
                        'frekans_max': f_max,
                        'dominant_freq': dominant_freq,
                        'enerji': enerji,
                        'saniye': saniye,
                        'metre': mesafe,
                        'tip': tip,
                        'risk': band["risk"],
                    })
            self.last_ok_ts = time.time()
            self.last_error = None
            return tehditler, spektrum_ozeti
        except Exception as exc:
            # Sessizce yutma: hata saklanir, cagiran taraf sensor arizasini gorebilir.
            self.last_error = f"{type(exc).__name__}: {exc}"
            return [], None
