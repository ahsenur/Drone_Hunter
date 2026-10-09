import sys, pathlib, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from acoustic_engine.tdoa import estimate_bearing, SPEED_OF_SOUND_MS


def fractional_delay(x, delay_s, fs):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    return np.fft.irfft(X * np.exp(-2j * np.pi * f * delay_s), n=n)


def make_pair(angle_deg, d, fs, snr_db, rng, tonal=True, dur=0.5):
    n = int(fs * dur)
    t = np.arange(n) / fs
    if tonal:  # rotor benzeri: temel 180 Hz + harmonikler + genis bant
        src = sum(np.sin(2 * np.pi * 180 * k * t + rng.uniform(0, 6.28)) / k for k in range(1, 12))
        src = src + 0.3 * rng.standard_normal(n)
    else:
        src = rng.standard_normal(n)
    tau = d * np.sin(np.radians(angle_deg)) / SPEED_OF_SOUND_MS   # B'ye gecikme (pozitif aci -> A'ya yakin)
    a = src
    b = fractional_delay(src, tau, fs)
    p = np.mean(src ** 2)
    sigma = np.sqrt(p / (10 ** (snr_db / 10)))
    return a + sigma * rng.standard_normal(n), b + sigma * rng.standard_normal(n)


class TdoaTest(unittest.TestCase):
    def test_clean_broadband(self):
        rng = np.random.default_rng(1)
        for ang in (-60, -30, 0, 20, 45, 60):
            a, b = make_pair(ang, 0.2, 22050, 40, rng, tonal=False)
            est = estimate_bearing(a, b, 22050, 0.2)["angle_deg"]
            self.assertLess(abs(est - ang), 3.0, f"{ang} -> {est}")

    def test_tonal_noisy_median_error(self):
        rng = np.random.default_rng(2)
        errs = []
        for ang in (-60, -40, -20, 0, 20, 40, 60):
            for _ in range(10):
                a, b = make_pair(ang, 0.2, 22050, 10, rng, tonal=True)
                errs.append(abs(estimate_bearing(a, b, 22050, 0.2)["angle_deg"] - ang))
        print(f"\n[tdoa] tonal, SNR=10 dB, d=0.2 m: medyan hata {np.median(errs):.2f} derece, "
              f"%90 hata {np.percentile(errs, 90):.2f} derece")
        self.assertLess(np.median(errs), 6.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
