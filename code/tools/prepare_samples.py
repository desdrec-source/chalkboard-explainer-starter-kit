"""Rebuild the processed chalk sound assets (assets/sfx/scratch_pool.wav, tap.wav) from the
original CC0 Freesound recordings. Only needed if you want to change the processing; the kit
already ships the processed files.

  python tools/prepare_samples.py            # downloads public HQ previews into assets/sfx/originals/
  python tools/prepare_samples.py --no-download   # use files already in assets/sfx/originals/

Processing: 200 Hz high-pass, stationary spectral-gate denoise (noisereduce, profile = quietest 15%),
keep only active scratch energy (>=150 ms chunks), equal-power crossfade into one bed, 500 Hz
high-pass, transient softening (x2) and slow-envelope levelling. Tap: short 1.8 kHz high-passed
onset from the third recording with a 12 ms decay."""
import sys, subprocess, urllib.request
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

KIT = Path(__file__).resolve().parents[2]
ORIG = KIT / 'assets' / 'sfx' / 'originals'; OUT = KIT / 'assets' / 'sfx'
SR = 48000
SOURCES = {  # id: (preview url, role)
    '264944': ('https://cdn.freesound.org/previews/264/264944_4838185-hq.mp3', 'bed'),
    '751870': ('https://cdn.freesound.org/previews/751/751870_10368455-hq.mp3', 'bed'),
    '447925': ('https://cdn.freesound.org/previews/447/447925_9159316-hq.mp3', 'tap'),
}

def hp(x, f): return sosfilt(butter(4, f, btype='high', fs=SR, output='sos'), x)

def load(sid):
    mp3 = ORIG / f'{sid}.mp3'
    if not mp3.exists():
        if '--no-download' in sys.argv: raise SystemExit(f'missing {mp3}')
        ORIG.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SOURCES[sid][0], headers={'User-Agent': 'Mozilla/5.0'})
        mp3.write_bytes(urllib.request.urlopen(req).read())
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp3), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)

def clean_source(x):
    import noisereduce as nr
    x = hp(x, 200)
    env = np.sqrt(np.convolve(x ** 2, np.ones(2400) / 2400, 'same'))
    y = nr.reduce_noise(y=x, sr=SR, y_noise=x[env < np.percentile(env, 15)], stationary=True,
                        prop_decrease=1.0, n_std_thresh_stationary=1.8)
    return hp(y, 200)

def active_chunks(x, minlen=0.12):
    env = np.sqrt(np.convolve(x ** 2, np.ones(960) / 960, 'same'))
    m = env > max(np.percentile(env, 20) * 8, env.max() * 0.03); out = []; i = 0
    while i < len(m):
        if m[i]:
            j = i
            while j < len(m) and m[j]: j += 1
            if (j - i) / SR >= minlen: out.append(x[i:j])
            i = j
        else: i += 1
    return out

def xfade_concat(cs, ov=int(0.06 * SR)):
    out = cs[0].copy()
    for c in cs[1:]:
        if len(c) < 2 * ov or len(out) < ov: continue
        w = np.linspace(0, np.pi / 2, ov)
        out[-ov:] = out[-ov:] * np.cos(w) + c[:ov] * np.sin(w); out = np.concatenate([out, c[ov:]])
    return out

def soften_transients(x, ratio=1.4):
    fast = np.sqrt(np.convolve(x ** 2, np.ones(96) / 96, 'same'))
    slow = np.sqrt(np.convolve(x ** 2, np.ones(2400) / 2400, 'same'))
    g = np.convolve(np.minimum(1, ratio * slow / np.maximum(fast, 1e-9)), np.ones(240) / 240, 'same')
    return x * g

def main():
    chunks = []
    for sid, (_, role) in SOURCES.items():
        if role != 'bed': continue
        for c in active_chunks(clean_source(load(sid))):
            chunks.append(c / (np.sqrt((c ** 2).mean()) + 1e-9))
    chunks = [c for c in chunks if len(c) > int(0.15 * SR)]
    pool = hp(xfade_concat(chunks), 500)
    for _ in range(2): pool = soften_transients(pool)
    slow = np.sqrt(np.convolve(pool ** 2, np.ones(4800) / 4800, 'same'))
    pool = pool / np.maximum(slow, np.percentile(slow, 30)); pool /= np.abs(pool).max()
    t = hp(load('447925'), 250)
    on = int(np.argmax(np.abs(t) > np.abs(t).max() * 0.3)); tap = t[max(0, on - 48):on + int(0.07 * SR)]
    tap = hp(tap, 1800) * np.exp(-np.arange(len(tap)) / (0.012 * SR)); tap /= np.abs(tap).max()
    fi = int(0.002 * SR); tap[:fi] *= np.linspace(0, 1, fi)
    sf.write(OUT / 'scratch_pool.wav', (pool * 0.97).astype(np.float32), SR, subtype='PCM_24')
    sf.write(OUT / 'tap.wav', (tap * 0.97).astype(np.float32), SR, subtype='PCM_24')
    print(f'scratch_pool.wav {len(pool) / SR:.1f}s from {len(chunks)} chunks; tap.wav {len(tap) / SR * 1000:.0f} ms')

if __name__ == '__main__':
    main()
