"""Turn a content config + one aspect layout into a timeline of drawable elements.

Returns a list of (t_start, t_end, kind, obj) with kind 'text' (Text) or 'draw' (Drawing)."""
import numpy as np
from PIL import ImageFont
from . import board
from .board import Stroke, Drawing, Text, catmull, wrap
from .shapes import SHAPES, build_custom, cross_out


def _place(specs, x, y, s=1.0):
    return [Stroke(np.asarray(p) * s + np.array([x, y]), w, j, d) for p, w, j, d in specs]


def _shape_specs(spec):
    if spec['shape'] == 'custom': return build_custom(spec)
    if spec['shape'] not in SHAPES:
        raise SystemExit(f"unknown shape '{spec['shape']}'. Available: {', '.join(sorted(SHAPES))}, custom")
    return SHAPES[spec['shape']]()


def _arrow(a, b, s):
    """curved arrow from figure a's head to figure b's head (a, b = (x, y) neck anchors)"""
    ax, bx, y = a[0] + 37 * s, b[0] - 12 * s, min(a[1], b[1])
    fx = [0, .211, .516, .845, 1]; fy = [-80, -150, -172, -148, -110]
    pts = [(ax + (bx - ax) * u, y + v * s) for u, v in zip(fx, fy)]
    ex, ey = pts[-1]
    head = [(ex - 33 * s, ey - 18 * s), (ex + 2 * s, ey + 6 * s), (ex + 10 * s, ey - 36 * s)]
    return [Stroke(catmull(pts, 14), 7), Stroke(head, 7)]


def build(cfg, aspect, kit_root):
    L = cfg['layouts'][aspect]
    fonts = {k: str(kit_root / v) for k, v in cfg['fonts'].items()}
    F = lambda role, size: ImageFont.truetype(fonts[role], int(size))
    emb = set(cfg.get('embolden_fonts', ['body']))
    T = lambda lines, role, size, x, y, align='left', lh=1.15: Text(lines, F(role, size), x, y, align, lh, role in emb)
    els = []

    if 'title' in cfg:
        c, l = cfg['title'], L['title']
        els.append((*c['time'], 'text', T(wrap(c['text'], F('title', l['size']), l.get('max_width')), 'title',
                                         l['size'], l['x'], l['y'], 'center')))

    placed = []
    for i, c in enumerate(cfg.get('figures', [])):
        l = L['figures'][i]
        if c['shape'] == 'arrow':
            a, b = c.get('between', [0, 1]); pa, pb = placed[a], placed[b]
            strokes = _arrow(pa[:2], pb[:2], pa[2]); placed.append(None)
        else:
            s = l.get('scale', 1.0); strokes = _place(_shape_specs(c), l['x'], l['y'], s); placed.append((l['x'], l['y'], s))
        els.append((*c['time'], 'draw', Drawing(strokes)))

    if 'caption' in cfg:
        c, l = cfg['caption'], L['caption']; f = F('body', l['size'])
        els.append((*c['time'], 'text', T(wrap(c['text'], f, l.get('max_width')), 'body', l['size'], l['x'], l['y'],
                                         l.get('align', 'center'), l.get('line_height', 1.15))))

    if 'sketch' in cfg:
        c, l = cfg['sketch'], L['sketch']; s = l.get('scale', 1.0)
        els.append((*c['time'], 'draw', Drawing(_place(_shape_specs(c), l['x'], l['y'], s))))
        if c.get('cross_out'):
            x, y = l['x'], l['y']
            box = (x - 205 * s, y - 255 * s, x + 205 * s, y + 25 * s)
            els.append((*c['cross_out'], 'draw', Drawing(_place(cross_out(box), 0, 0))))

    if cfg.get('list'):
        l = L['list']; f = F('body', l['size'])
        for k, it in enumerate(cfg['list']):
            t0, t1 = it['time']; yc = l['y'][k]; tm = t0 + (t1 - t0) * 0.4
            if it.get('icon'):
                els.append((t0 + 0.05, tm, 'draw',
                            Drawing(_place(_shape_specs({'shape': it['icon']}), l['icon_x'], yc, l.get('icon_scale', 1.0)))))
            lines = wrap(it['text'], f, l.get('max_width'))
            ty = yc - (len(lines) * l['size'] * 1.15) / 2 + l.get('text_dy', -10)
            els.append((tm if it.get('icon') else t0, t1 - 0.1, 'text', T(lines, 'body', l['size'], l['text_x'], ty, 'left', 1.12)))

    if 'closing' in cfg:
        c, l = cfg['closing'], L['closing']
        bc = T(wrap(c['text'], F('title', l['size']), l.get('max_width')), 'title', l['size'], l['x'], l['y'], 'center')
        els.append((*c['time'], 'text', bc))
        b = bc.bbox()[-1]; cx = (b[0] + b[2]) / 2
        lines = [[(b[0] - 10, b[3] + 30), (cx, b[3] + 26), (b[2] + 10, b[3] + 32)],
                 [(b[0] + 20, b[3] + 62), (cx, b[3] + 58), (b[2] - 15, b[3] + 63)]]
        for tt, pts in zip(c.get('underlines', []), lines):
            els.append((*tt, 'draw', Drawing([Stroke(catmull(pts, 20), 8)])))
    return els


def check_bounds(els, margin=None):
    """warn about anything outside the inner board area"""
    m = margin if margin is not None else board.FRAME_PX + 4; bad = []
    for t0, t1, k, o in els:
        if k == 'text': boxes = o.bbox()
        else:
            P = np.vstack([s.p1 for s in o.strokes]); boxes = [(P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max())]
        for x0, y0, x1, y1 in boxes:
            if x0 < m or y0 < m or x1 > board.W - m or y1 > board.H - m:
                bad.append((t0, k, (round(x0), round(y0), round(x1), round(y1))))
    return bad
