"""Transient / 'drumminess' check for rendered chalk audio.

  python code/tools/onset_check.py output/belly_fat/belly_fat_9x16_sfx.mp4 [more files]

Reports sharp attacks per second (>15 dB rise in 10 ms), spectral-flux onsets per second,
crest-style transient peaks per second and the share of energy below 300 Hz. Lower is smoother;
the shipped settings give about 1.2-1.3 sharp attacks/s, ~0.05 transient peaks/s and <1% energy below 300 Hz."""
import subprocess, sys
import numpy as np
from scipy.signal import stft, find_peaks

SR = 48000

def load(f):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-map', '0:a', '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

def metrics(a):
    dur = len(a) / SR; h = 240
    db = 20 * np.log10(np.sqrt(np.convolve(a ** 2, np.ones(h) / h, 'same'))[::h] + 1e-9)
    pk, _ = find_peaks(db[2:] - db[:-2], height=15, distance=10)
    f, t, Z = stft(a, SR, nperseg=1024, noverlap=768); M = np.log1p(np.abs(Z) * 100)
    flux = np.maximum(0, np.diff(M, axis=1)).sum(0)
    fpk, _ = find_peaks(flux, height=np.percentile(flux, 99) * 0.5 if flux.max() > 0 else 1, distance=8)
    low = np.abs(Z[f < 300]).sum() / max(np.abs(Z).sum(), 1e-9)
    fast = np.sqrt(np.convolve(a ** 2, np.ones(96) / 96, 'same'))[::48]
    slow = np.sqrt(np.convolve(a ** 2, np.ones(2400) / 2400, 'same'))[::48]
    r = np.where(slow > 10 ** (-45 / 20), 20 * np.log10((fast + 1e-12) / (slow + 1e-12)), 0)
    cp, _ = find_peaks(r, height=9, distance=50)
    return len(pk) / dur, len(fpk) / dur, len(cp) / dur, 100 * low

if __name__ == '__main__':
    for f in sys.argv[1:]:
        s, fl, c, lo = metrics(load(f))
        print(f'{f}: sharp attacks/s {s:.2f} | flux onsets/s {fl:.2f} | transient peaks/s {c:.2f} | energy <300 Hz {lo:.1f}%')
