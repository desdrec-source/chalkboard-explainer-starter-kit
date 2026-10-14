"""Chalkboard background, chalk grain, and drawable primitives (Stroke, Drawing, Text).

Call board.init(W, H, seed) once before creating any Stroke/Text; everything else reads the
module-level canvas size. Kept deliberately simple (numpy + Pillow + scipy only)."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, zoom, grey_dilation

W = H = None
rng = None
CHALK = np.array([238, 240, 232], np.float32)
BOARD_GREEN = (0x2f, 0x4f, 0x3a)
FRAME_PX = 26


def init(width, height, seed=7):
    global W, H, rng
    W, H = int(width), int(height)
    rng = np.random.default_rng(seed)


def noise(scale, shape=None):
    h, w = shape or (H, W)
    sh = (max(2, h // scale + 2), max(2, w // scale + 2))
    n = rng.random(sh)
    return zoom(n, (h / sh[0] * 1.0001, w / sh[1] * 1.0001), order=3)[:h, :w]


def make_background():
    """Dark green board with noise, eraser smudges, old dust, vignette and a wooden frame."""
    bg = np.ones((H, W, 3), np.float32) * np.array(BOARD_GREEN, np.float32)
    bg += ((noise(3) - 0.5) * 6 + (noise(40) - 0.5) * 10 + (noise(200) - 0.5) * 12)[..., None]
    k = math.sqrt(W * H / (1080 * 1920))           # keep smudge size proportional
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for _ in range(14):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H); r = rng.uniform(150, 420) * k
        a0 = rng.uniform(0, 360)
        d.arc([cx - r, cy - r * 0.5, cx + r, cy + r * 0.5], a0, a0 + rng.uniform(60, 160),
              fill=int(rng.uniform(40, 90)), width=int(rng.uniform(50, 110) * k))
    for _ in range(8):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        d.ellipse([x - 160 * k, y - 60 * k, x + 160 * k, y + 60 * k], fill=int(rng.uniform(20, 50)))
    sm = gaussian_filter(np.asarray(im, np.float32) / 255, 25) * (0.6 + 0.8 * noise(6))
    bg += sm[..., None] * np.array([22, 26, 22], np.float32)
    sp = gaussian_filter((rng.random((H, W)) > 0.9985).astype(np.float32), 1.0) * 3
    bg += np.clip(sp, 0, 1)[..., None] * 25
    yy, xx = np.mgrid[0:H, 0:W]
    vr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    bg *= (1 - 0.38 * np.clip(vr - 0.45, 0, 1) ** 1.5)[..., None]
    # wooden frame with streaks along each side and a bevel
    FR = FRAME_PX
    fr = np.zeros((H, W), bool); fr[:FR, :] = fr[-FR:, :] = True; fr[:, :FR] = fr[:, -FR:] = True
    horiz = (yy < FR) | (yy >= H - FR)
    st = np.where(horiz, zoom(rng.random((6, W // 3 + 1)), (H / 6 * 1.001, 3.0), order=1)[:H, :W],
                  zoom(rng.random((H // 3 + 1, 6)), (3.0, W / 6 * 1.001), order=1)[:H, :W])
    woodc = np.array([118, 78, 44], np.float32)[None, None, :] * (0.75 + 0.45 * st[..., None])
    dist = np.minimum.reduce([xx, yy, W - 1 - xx, H - 1 - yy]).astype(np.float32)
    t = np.clip(dist / FR, 0, 1)
    shade = np.where(dist < FR, 0.75 + 0.35 * t * (1 - t) * 4, 1)
    bg = np.where(fr[..., None], woodc * shade[..., None], bg)
    inner = np.clip(1 - (dist - FR) / 18, 0, 1) * (dist >= FR)
    bg *= (1 - 0.45 * inner)[..., None]
    return np.clip(bg, 0, 255)


def make_grain():
    g = 0.55 * noise(1) + 0.25 * noise(3) + 0.2 * noise(12)
    return 0.25 + 0.75 * np.clip((g - 0.28) * 2.3, 0.0, 1.0)


# ---------- geometry ----------
def catmull(pts, n=12, closed=False):
    P = np.array(pts, float)
    P = np.vstack([P[-1], P, P[0], P[1]]) if closed else np.vstack([P[0], P, P[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


def resample(P, step=3.0):
    P = np.asarray(P, float)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    if L[-1] < 1e-6: return P[:1]
    s = np.arange(0, L[-1] + 1e-9, step)
    if s[-1] < L[-1]: s = np.append(s, L[-1])
    return np.stack([np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])], 1)


def smooth_noise(n, amp, corr=12):
    k = gaussian_filter(rng.normal(0, 1, n + corr * 6), corr, mode='wrap')[corr * 3:corr * 3 + n]
    return np.clip(k / (0.35 / np.sqrt(corr)), -2.2, 2.2) * amp


def circle(cx, cy, r, a0=-90, a1=270, ry=None):
    ry = ry or r
    a = np.radians(np.linspace(a0, a1, max(8, int(abs(a1 - a0) / 4))))
    return np.stack([cx + r * np.cos(a), cy + ry * np.sin(a)], 1)


class Stroke:
    """A jittered chalk polyline (optionally a second thinner pass), revealed progressively."""
    def __init__(s, pts, w=7, jit=1.6, double=True):
        s.double = double
        P = resample(pts, 3.0); n = len(P)
        dP = np.gradient(P, axis=0) if n > 1 else np.array([[1.0, 0.0]])
        nrm = np.stack([-dP[:, 1], dP[:, 0]], 1); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        s.p1 = P + nrm * smooth_noise(n, jit)[:, None]
        s.p2 = P + nrm * (smooth_noise(n, jit * 1.2) + rng.choice([-1, 1]) * 1.8)[:, None]
        s.w1 = np.clip(w * (1 + smooth_noise(n, 0.18, 8)), 2, None)
        s.w2 = np.clip(w * 0.5 * (1 + smooth_noise(n, 0.3, 8)), 1.5, None)
        s.n = n; s.len = n * 3.0

    def draw(s, d, frac):
        if frac <= 0: return None
        k = int(round(frac * (s.n - 1)))
        passes = ((s.p1, s.w1, 255), (s.p2, s.w2, 200)) if s.double else ((s.p1, s.w1, 255),)
        for pp, ww, val in passes:
            for i in range(k):
                x0, y0 = pp[i]; x1, y1 = pp[i + 1]; wi = ww[i]
                d.line([x0, y0, x1, y1], fill=val, width=int(round(wi)))
                r = wi / 2; d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=val)
        return tuple(s.p1[k])


class Drawing:
    """Several strokes drawn one after another."""
    def __init__(s, strokes):
        s.strokes = strokes; s.total = sum(x.len for x in strokes) + 1e-9


class Text:
    """Font text rasterised once to a roughened chalk mask; revealed left-to-right by a wipe."""
    def __init__(s, lines, font, x, y, align='left', lh=1.15, embolden=False):
        s.lines = []; cy = y
        for ln in lines:
            b = font.getbbox(ln); w = b[2] - b[0]
            lx = x - w / 2 - b[0] if align == 'center' else x - b[0]
            s.lines.append((ln, lx, cy, w, b)); cy += font.size * lh
        s.font = font
        im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
        for ln, lx, ly, w, b in s.lines: d.text((lx, ly), ln, font=font, fill=255)
        m = np.asarray(im, np.float32) / 255
        if embolden: m = grey_dilation(m, size=(3, 3))
        rough = gaussian_filter(m, 1.2) + (noise(2) - 0.5) * 0.5
        s.mask = np.clip(np.clip((rough - 0.25) * 2.2, 0, 1) * np.clip(m * 1.5 + gaussian_filter(m, 0.7), 0, 1), 0, 1)

    def bbox(s):
        return [(lx + b[0], ly + b[1], lx + b[2], ly + b[3]) for ln, lx, ly, w, b in s.lines]


def wrap(text, font, max_width):
    """Greedy word wrap; an explicit '\\n' always breaks."""
    out = []
    for para in text.split('\n'):
        cur = ''
        for word in para.split():
            trial = (cur + ' ' + word).strip()
            if cur and max_width and font.getlength(trial) > max_width:
                out.append(cur); cur = word
            else:
                cur = trial
        out.append(cur)
    return out


def chalkify(m):
    return np.clip(gaussian_filter(m, 0.8) * 1.15, 0, 1)


def ease(x):
    x = min(1, max(0, x)); return x * x * (3 - 2 * x) * 0.3 + x * 0.7
