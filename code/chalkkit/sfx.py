"""Chalk sound effects synced to the hand's contact track.

Per stroke group: a scratch cut from the processed CC0 bed at a random offset, pitch jitter
0.92-1.08, gain jitter +-1.5 dB, louder/brighter with tip speed, 30 ms fade-in / 50 ms fade-out,
gentle expander. Strokes separated by lifts < 120 ms are merged into one continuous scratch with a
soft dip; minimum length 120 ms (very short strokes quieter). Light high-passed taps only after a
>= 250 ms pause and at most one per 0.5 s. True digital silence between strokes. Mastered to
-16 LUFS with a true-peak limiter (<= -2 dBTP before AAC so the encoded file stays <= -1 dBTP)."""
import subprocess, warnings
import numpy as np, soundfile as sf, pyloudnorm as pyln
from scipy.signal import butter, sosfilt, resample_poly
from scipy.ndimage import maximum_filter1d, uniform_filter1d

SR = 48000
MERGE_GAP = 0.12; MIN_LEN = 0.12
TAP_MIN_GAP = 0.25; TAP_MIN_SPACING = 0.5; TAP_DB = -13
TARGET_LUFS = -16.0


def hp(x, f): return sosfilt(butter(4, f, btype='high', fs=SR, output='sos'), x)


class ChalkSFX:
    def __init__(s, sfx_dir, duration, seed=5):
        s.rng = np.random.default_rng(seed)
        s.N = int(SR * duration)
        s.pool, sr1 = sf.read(sfx_dir / 'scratch_pool.wav'); s.tap, sr2 = sf.read(sfx_dir / 'tap.wav')
        assert sr1 == sr2 == SR, 'processed samples must be 48 kHz'
        s.stats = {}

    def scratch(s, n, speed, text_mod=False, dip=None, short_gain=1.0):
        rng = s.rng; pitch = rng.uniform(0.92, 1.08)
        need = int(n * pitch) + 10
        if need >= len(s.pool) - 1:   # very long stroke: loop the bed
            s.pool = np.concatenate([s.pool, s.pool[::-1]])
        off = int(rng.integers(0, len(s.pool) - need - 1)); seg = s.pool[off:off + need]
        y = np.interp(np.arange(n) * pitch, np.arange(len(seg)), seg)
        f = np.convolve(np.clip(speed / 800, 0, 1.4), np.ones(1440) / 1440, 'same')
        y = y * (0.75 - 0.25 * f) + hp(y, 2500) * (0.25 + 0.5 * f)
        g = (0.45 + 0.55 * f) * 10 ** (rng.uniform(-1.5, 1.5) / 20) * short_gain
        if text_mod:
            t = np.arange(n) / SR; g = g * (0.85 + 0.15 * np.sin(2 * np.pi * rng.uniform(3.5, 5) * t + rng.uniform(0, 6)))
        if dip is not None: g = g * dip
        y = y * g
        e = np.sqrt(np.convolve(y ** 2, np.ones(960) / 960, 'same')); thr = np.sqrt((y ** 2).mean()) * 0.12
        y = y * np.clip(e / thr, 0, 1) ** 0.6
        fi = min(n // 2, int(0.03 * SR)); fo = min(n // 2, int(0.05 * SR))
        y[:fi] *= np.sin(np.linspace(0, np.pi / 2, fi)) ** 2; y[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo)) ** 2
        return y

    def render(s, intervals, text_flags=None):
        items = sorted([(a, b, sp, (text_flags[k] if text_flags else False)) for k, (a, b, sp) in enumerate(intervals)],
                       key=lambda x: x[0])
        groups = []
        for it in items:
            if groups and it[0] - groups[-1][-1][1] < MERGE_GAP: groups[-1].append(it)
            else: groups.append([it])
        out = np.zeros(s.N); last_tap = -9; prev_end = -9; ntap = 0
        for gp in groups:
            t0 = gp[0][0]; t1 = max(gp[-1][1], t0 + MIN_LEN); real = sum(b - a for a, b, _, _ in gp)
            a_ = int(t0 * SR); b_ = min(s.N, int(t1 * SR)); n = b_ - a_
            if n <= 16: continue
            tt = t0 + np.arange(n) / SR; sp = np.zeros(n); dip = np.full(n, 0.3)
            for (a, b, spf, _) in gp:
                m = (tt >= a) & (tt < b); sp[m] = spf(tt[m]); dip[m] = 1.0
            if gp[-1][1] < t1:
                m = tt >= gp[-1][1]; dip[m] = 1.0; sp[m] = sp[~m][-1] if (~m).any() else 400
            dip = np.convolve(dip, np.ones(1920) / 1920, 'same')
            out[a_:b_] += s.scratch(n, sp, any(x[3] for x in gp), dip, float(np.clip(real / 0.25, 0.45, 1.0)))
            if t0 - prev_end >= TAP_MIN_GAP and t0 - last_tap >= TAP_MIN_SPACING:
                tp = s.tap * 10 ** (TAP_DB / 20) * 0.55 * 10 ** (s.rng.uniform(-1.5, 1.5) / 20)
                m = min(len(tp), s.N - a_); out[a_:a_ + m] += tp[:m]; last_tap = t0; ntap += 1
            prev_end = t1
        s.stats.update(strokes=len(items), scratches=len(groups), taps=ntap)
        return out


def true_peak(x): return np.abs(resample_poly(x, 4, 1)).max()


def limiter(x, ceil):
    env = np.abs(resample_poly(x, 4, 1)).reshape(-1, 4).max(1)[:len(x)]
    w = int(0.003 * SR); pk = maximum_filter1d(env, size=2 * w + 1)
    g = np.minimum(uniform_filter1d(np.minimum(1, ceil / np.maximum(pk, 1e-9)), w), ceil / np.maximum(pk, 1e-9))
    return x * g


def master(x, target=TARGET_LUFS):
    warnings.filterwarnings('ignore', message='Possible clipped samples')   # intermediate gain stage; the limiter handles it
    meter = pyln.Meter(SR)
    y = pyln.normalize.loudness(x, meter.integrated_loudness(x), target)
    for _ in range(25):
        y = limiter(y, 10 ** (-2.4 / 20)); y = pyln.normalize.loudness(y, meter.integrated_loudness(y), target)
        if true_peak(y) <= 10 ** (-2.0 / 20): break
    y[np.abs(y) < 10 ** (-96 / 20)] = 0.0
    return y, meter.integrated_loudness(y), 20 * np.log10(true_peak(y))


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a', '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def gap_floor(path, iv, margin=0.06):
    """RMS / peak (dBFS) of the decoded audio outside chalk contact"""
    a = decode(path); m = np.ones(len(a), bool)
    for t0, t1, _ in iv: m[max(0, int((t0 - margin) * SR)):int((t1 + margin + 0.03) * SR)] = False
    g = a[m]; rms = np.sqrt((g ** 2).mean()) if len(g) else 0
    return 20 * np.log10(rms + 1e-12), 20 * np.log10(np.abs(g).max() + 1e-12) if len(g) else -240, len(g) / SR


def make_sfx(animator, sfx_dir, video_in, video_out, wav_out):
    iv, flags = animator.contact_intervals()
    fx = ChalkSFX(sfx_dir, animator.dur)
    y, L, tpk = master(fx.render(iv, flags))
    sf.write(wav_out, y.astype(np.float32), SR, subtype='FLOAT')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video_in), '-i', str(wav_out), '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '1', '-shortest',
                    '-movflags', '+faststart', str(video_out)], check=True)
    g = gap_floor(video_out, iv)
    return dict(**fx.stats, lufs=round(float(L), 2), true_peak_dbtp=round(float(tpk), 2), gap_rms_dbfs=round(float(g[0]), 1),
                gap_peak_dbfs=round(float(g[1]), 1), gap_seconds=round(float(g[2]), 1))
