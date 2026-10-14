"""Schedules the hand through the element timeline (pen-up travel between strokes/elements,
letter-by-letter wipe for text) and renders frames. Also exposes the chalk-contact track
used to sync the sound effects."""
import math, subprocess
import numpy as np
from PIL import Image, ImageDraw
from . import board
from .board import chalkify, ease
from .hand import Hand

TRAVEL_K = 0.7    # pen-up travel inside a drawing costs this fraction of its distance
BREAK = 2.5       # line break inside text costs this many "characters" of time


class Animator:
    def __init__(s, els, bg, grain, duration=25.0, fps=30, hand_scale=0.8, seed=11):
        s.els, s.bg, s.grain, s.dur, s.fps = els, bg, grain, duration, fps
        s.W, s.H = board.W, board.H
        s.rng = np.random.default_rng(seed)
        s.entry = np.array([s.W * 1.25, s.H * 1.2]); s.exit = np.array([s.W * 1.34, s.H * 1.27])
        s.hand = Hand(s.W, s.H, hand_scale)
        s.cache = {}
        s._schedule()

    # ---- element geometry ----
    def segs(s, o):
        if not hasattr(o, '_segs'):
            segs = []; prev = None
            for st in o.strokes:
                if prev is not None:
                    a, b = prev.p1[-1], st.p1[0]; dist = np.linalg.norm(b - a)
                    if dist > 4: segs.append(('travel', dist * TRAVEL_K + 8, a, b))
                segs.append(('stroke', st.len, st, None)); prev = st
            o._segs = segs; o._tot = sum(x[1] for x in segs)
        return o._segs

    def drawing_render(s, o, p):
        s.segs(o)
        im = Image.new('L', (s.W, s.H), 0); d = ImageDraw.Draw(im)
        tgt = p * o._tot; acc = 0; tip = None; lift = 0.0
        for kind, L, a, b in o._segs:
            if tgt <= acc: break
            f = min(1, (tgt - acc) / L)
            if kind == 'stroke':
                t = a.draw(d, f); tip = np.array(t) if t is not None else tip; lift = 0.0
            else:
                ff = f * f * (3 - 2 * f); tip = a + (b - a) * ff; lift = 0.45 * math.sin(math.pi * f)
            acc += L
        return chalkify(np.asarray(im, np.float32) / 255), tip, lift

    @staticmethod
    def text_tip(o, li, xr):
        ln, lx, ly, w, b = o.lines[li]; h = b[3] - b[1]
        return np.array([xr, ly + (b[1] + b[3]) / 2 + 0.22 * h * math.sin(xr * 0.11)])

    def text_render(s, o, p, mask=True):
        n = len(o.lines); total = sum(len(l[0]) for l in o.lines) + BREAK * (n - 1)
        chars = p * total; out = np.zeros((s.H, s.W), np.float32) if mask else None
        tip = None; lift = 0.0; contact = False
        cols = np.arange(s.W, dtype=np.float32)
        for li, (ln, lx, ly, w, b) in enumerate(o.lines):
            if chars <= 0: break
            y0 = int(max(0, ly + b[1] - 12)); y1 = int(min(s.H, ly + b[3] + 14))
            if chars >= len(ln):
                xr = lx + b[2] + 20; chars -= len(ln); tip = s.text_tip(o, li, lx + b[2])
                if li < n - 1 and chars > 0:
                    f = min(1, chars / BREAK); chars -= BREAK
                    a = s.text_tip(o, li, lx + b[2]); nl = o.lines[li + 1]; bb = s.text_tip(o, li + 1, nl[1] + nl[4][0])
                    ff = f * f * (3 - 2 * f); tip = a + (bb - a) * ff; lift = 0.45 * math.sin(math.pi * f)
            else:
                i = int(chars); fr = chars - i
                xa = lx + o.font.getlength(ln[:i]); xb = lx + o.font.getlength(ln[:i + 1])
                xr = xa + (xb - xa) * fr; chars = 0; tip = s.text_tip(o, li, xr); contact = True
            if mask:
                out[y0:y1] = np.maximum(out[y0:y1], o.mask[y0:y1] * np.clip((xr - cols) / 10, 0, 1)[None, :])
        return out, tip, lift, contact

    def render_el(s, k, o, p):
        return s.text_render(o, p)[:3] if k == 'text' else s.drawing_render(o, p)

    def ends(s, k, o):
        if k == 'text':
            ln, lx, ly, w, b = o.lines[0]; st = s.text_tip(o, 0, lx + b[0])
            ln, lx, ly, w, b = o.lines[-1]; en = s.text_tip(o, len(o.lines) - 1, lx + b[2])
            return st, en
        return o.strokes[0].p1[0].copy(), o.strokes[-1].p1[-1].copy()

    def _schedule(s):
        s.sched = []; prev_pt, prev_t = s.entry, 0.0
        diag = math.hypot(s.W, s.H)
        for (t0, t1, k, o) in s.els:
            st, en = s.ends(k, o)
            g = float(np.clip(np.linalg.norm(st - prev_pt) / (1700 * diag / 2203), 0.18, 0.6))
            ts = min(max(t0, prev_t + g), t1 - 0.45 * (t1 - t0))
            s.sched.append(dict(tp=prev_t, ts=ts, t1=t1, a=prev_pt, s=st, k=k, o=o))
            prev_pt, prev_t = en, t1
        s.end_t = prev_t; s.end_pt = prev_pt; s.exit_dur = 0.9

    # ---- frames ----
    def frame(s, t):
        cur = np.zeros((s.H, s.W), np.float32); tip = None; lift = 0.0; drawing = False
        for i, sd in enumerate(s.sched):
            if t >= sd['t1']:
                if i not in s.cache: s.cache[i] = s.render_el(sd['k'], sd['o'], 1.0)[0]
                cur = np.maximum(cur, s.cache[i])
            elif t >= sd['ts']:
                p = ease((t - sd['ts']) / (sd['t1'] - sd['ts'])); m, tip, lift = s.render_el(sd['k'], sd['o'], p)
                cur = np.maximum(cur, m); drawing = lift < 0.05
            elif t >= sd['tp'] and tip is None:
                u = (t - sd['tp']) / max(1e-6, sd['ts'] - sd['tp']); uu = u * u * (3 - 2 * u)
                a, b = sd['a'], sd['s']; mid = (a + b) / 2 + np.array([40, -30]) * min(1, np.linalg.norm(b - a) / 400)
                tip = (1 - uu) ** 2 * a + 2 * (1 - uu) * uu * mid + uu ** 2 * b; lift = math.sin(math.pi * u)
                if sd is s.sched[0]: lift = max(lift, 1 - u)
        if tip is None and t >= s.end_t:
            u = min(1, (t - s.end_t) / s.exit_dur); uu = u * u * (3 - 2 * u)
            if u < 1: tip = s.end_pt + (s.exit - s.end_pt) * uu; lift = min(1, u * 2.5)
        a = cur * s.grain
        img = s.bg * (1 - a[..., None]) + board.CHALK * a[..., None]
        if tip is not None:
            tx, ty = float(tip[0]), float(tip[1])
            if drawing:   # falling dust specks at the tip
                for _ in range(5):
                    dx, dy = s.rng.normal(0, 8, 2); px, py = int(tx + dx), int(ty + abs(dy))
                    if 0 <= px < s.W - 2 and 0 <= py < s.H - 2: img[py:py + 2, px:px + 2] = img[py:py + 2, px:px + 2] * 0.4 + 235 * 0.6
            img = s.hand.composite(img, tip, lift, t, drawing)
        return np.clip(img, 0, 255).astype(np.uint8)

    def encode(s, out_path, log_every=60):
        nf = int(round(s.dur * s.fps))
        ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                               '-s', f'{s.W}x{s.H}', '-r', str(s.fps), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                               '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', str(out_path)],
                              stdin=subprocess.PIPE)
        for f in range(nf):
            ff.stdin.write(s.frame(f / s.fps).tobytes())
            if log_every and f % log_every == 0: print(f'  frame {f}/{nf}', flush=True)
        ff.stdin.close()
        if ff.wait() != 0: raise SystemExit('ffmpeg encode failed')

    # ---- chalk contact track for sfx ----
    def contact_intervals(s, FS=240, jump_px=40):
        """[(t0, t1, speed_fn)], [is_text] for every continuous chalk-contact run"""
        ts = np.arange(0, s.dur, 1 / FS); contact = np.zeros(len(ts), bool); pos = np.zeros((len(ts), 2)); kind = np.zeros(len(ts), int)
        for sd in s.sched:
            o, k = sd['o'], sd['k']
            if k != 'text': s.segs(o)
            for i in np.where((ts >= sd['ts']) & (ts < sd['t1']))[0]:
                p = ease((ts[i] - sd['ts']) / (sd['t1'] - sd['ts']))
                if k == 'text':
                    _, tip, _, c = s.text_render(o, p, mask=False)
                    if c: contact[i] = True; pos[i] = tip; kind[i] = 1
                else:
                    tgt = p * o._tot; acc = 0
                    for kd, L, a, b in o._segs:
                        if tgt < acc + L:
                            if kd == 'stroke':
                                kk = int(round((tgt - acc) / L * (a.n - 1))); contact[i] = True; pos[i] = a.p1[kk]
                            break
                        acc += L
        sp = np.r_[0, np.linalg.norm(np.diff(pos, axis=0), axis=1) * FS]; sp[~contact] = 0
        sp = np.convolve(sp, np.ones(9) / 9, 'same')
        spfn = lambda tt: np.interp(tt, ts, sp)
        iv, flags = [], []; i = 0
        while i < len(ts):
            if not contact[i]: i += 1; continue
            j = i
            while j < len(ts) and contact[j]: j += 1
            seg = i
            for q in range(i + 1, j + 1):
                if q == j or np.linalg.norm(pos[q] - pos[q - 1]) > jump_px:
                    iv.append((ts[seg], ts[q - 1] + 1 / FS, spfn)); flags.append(kind[seg] == 1); seg = q
            i = j
        return iv, flags
