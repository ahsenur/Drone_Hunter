"""
Iki mikrofonlu TDOA (varis zamani farki) ile yon kestirimi.

Yontem: GCC-PHAT ile iki mikrofon arasindaki gecikme (tau) bulunur, sonra uzak alan
varsayimiyla  sin(theta) = c * tau / d  formulunden yon hesaplanir.
(hiperbolik konumlama ailesinin iki sensorlu, tek dogrultu veren hali)

Durum: algoritma yalnizca sentetik sinyal ile dogrulandi (tests/test_tdoa.py).
Gercek iki mikrofonlu donanimda test edilmedi.

Bilinen sinirlar:
- Iki mikrofon on/arka belirsizligini cozemez; yalnizca -90..+90 derece arasi verir.
- Mesafe vermez, yalnizca yon verir.
- Cok yakin mikrofon aralikta aci cozunurlugu duser.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

SPEED_OF_SOUND_MS = 343.0


def gcc_phat(sig: np.ndarray, ref: np.ndarray, fs: float, max_tau: float | None = None, interp: int = 16):
    """sig, ref'e gore ne kadar GEC geldi (saniye). Pozitif tau: sig daha gec."""
    sig = np.asarray(sig, dtype=float)
    ref = np.asarray(ref, dtype=float)
    n = sig.shape[0] + ref.shape[0]
    spec = np.fft.rfft(sig, n=n) * np.conj(np.fft.rfft(ref, n=n))
    spec /= np.abs(spec) + 1e-12
    cc = np.fft.irfft(spec, n=n * interp)

    max_shift = int(interp * n / 2)
    if max_tau is not None:
        max_shift = min(int(interp * fs * max_tau), max_shift)
    cc = np.concatenate((cc[-max_shift:], cc[: max_shift + 1]))
    shift = int(np.argmax(np.abs(cc))) - max_shift
    return shift / float(interp * fs), cc


def estimate_bearing(
    sig_a: np.ndarray,
    sig_b: np.ndarray,
    fs: float,
    mic_distance_m: float,
    c: float = SPEED_OF_SOUND_MS,
) -> Dict[str, float]:
    """
    Mikrofon A referans, B ikinci mikrofon. Aci, dizinin dik ekseninden (broadside) olculur;
    pozitif aci kaynagin A tarafinda oldugu anlamina gelir.

    Donen 'confidence' sezgiseldir (korelasyon tepesinin ortalamaya orani), kalibre edilmis
    bir olasilik degildir.
    """
    max_tau = mic_distance_m / c
    tau, cc = gcc_phat(sig_b, sig_a, fs, max_tau=max_tau)
    ratio = float(np.clip(c * tau / mic_distance_m, -1.0, 1.0))
    angle_deg = float(np.degrees(np.arcsin(ratio)))

    mag = np.abs(cc)
    psr = float(mag.max() / (mag.mean() + 1e-12))
    confidence = float(np.clip((psr - 3.0) / 12.0, 0.0, 1.0))
    return {"angle_deg": angle_deg, "tau_s": float(tau), "peak_ratio": psr, "confidence": confidence}


def bearing_to_fusion_deg(angle_deg: float) -> float:
    """
    Fuzyon ve kamera 0-180 derece kullaniyor (sol=0, sag=180). Dizi dik ekseni kamera eksenine
    hizali ve mikrofon A solda ise  fuzyon_acisi = 90 + angle  olur. Bu hizalama kurulumda
    elle dogrulanmalidir.
    """
    return 90.0 + float(angle_deg)
