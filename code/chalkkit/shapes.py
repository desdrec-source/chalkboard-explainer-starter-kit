"""Chalk shape library. Each shape is drawn in local coordinates around an anchor and returns
a list of stroke specs (points, width, jitter, double_pass). Layout code translates/scales the
points and turns them into Strokes. Add your own with @shape('name').

Anchors: body_* -> neck point (top of torso); situp -> centre of the floor line;
icons -> icon centre (about 120 px wide at scale 1); arrow is built by layout between figures."""
import math
import numpy as np
from .board import catmull, circle

SHAPES = {}
def shape(name):
    def deco(fn): SHAPES[name] = fn; return fn
    return deco

def S(pts, w=7, jit=1.6, double=True): return (np.asarray(pts, float), w, jit, double)

def _mirror(R):
    return R + [(-x, y) for x, y in reversed(R)][1:]

@shape('body_fat')
def body_fat():
    R = [(13, 0), (50, 16), (74, 36), (112, 100), (156, 158), (150, 174), (138, 168), (100, 110), (66, 62), (66, 88),
         (90, 112), (104, 146), (92, 184), (66, 212), (60, 245), (56, 295), (52, 340), (58, 356), (18, 356), (16, 300),
         (10, 238), (0, 228)]
    return [S(circle(0, -38, 36, 90, 450)), S(catmull(_mirror(R), 10))]

@shape('body_slim')
def body_slim():
    R = [(13, 0), (44, 14), (60, 34), (72, 100), (80, 168), (74, 182), (64, 174), (58, 104), (48, 58), (40, 88), (38, 140),
         (42, 185), (42, 215), (42, 280), (40, 340), (46, 356), (14, 356), (12, 300), (8, 228), (0, 218)]
    return [S(circle(0, -38, 36, 90, 450)), S(catmull(_mirror(R), 10))]

@shape('situp')
def situp():
    """stick figure mid-crunch; local (0,0) = centre of floor line (390 px wide)"""
    P = lambda pts: [(x - 280, y) for x, y in pts]
    return [S(P([(85, 0), (475, 0)]), 5),
            S(circle(128 - 280, -170, 30), 6),
            S(P([(148, -145), (236, -18)]), 7),
            S(P([(236, -18), (325, -112), (405, -6), (440, -6)]), 7),
            S(P([(165, -118), (225, -138), (285, -128)]), 6, 1.0)]

def cross_out(box):
    """big X over a box (x0,y0,x1,y1) in absolute px"""
    x0, y0, x1, y1 = box
    return [S([(x0, y0), (x1, y1)], 10, 2.2), S([(x1, y0), (x0, y1)], 10, 2.2)]

# ---------------- icons (centre anchor) ----------------
@shape('plate')
def plate():
    return [S(circle(14, 0, 46), 6), S(circle(14, 0, 30, -80, 280), 4, 1.0, False),
            S([(-56, 48), (-55, -8)], 6),
            S(catmull([(-68, -46), (-68, -20), (-56, -8), (-44, -20), (-44, -46)], 8), 5, 1.0, False),
            S([(-56, -46), (-56, -14)], 4, 0.6, False)]

@shape('protein')
def protein():
    return [S(circle(0, 0, 44, -120, 245), 7), S(circle(-12, -14, 14, 200, 290), 4)]

@shape('dumbbell')
def dumbbell():
    return [S([(-38, 0), (38, 0)], 7),
            S([(-38, -30), (-38, 30), (-54, 30), (-54, -30), (-38, -30)], 6), S([(-60, -18), (-60, 18)], 6),
            S([(38, -30), (38, 30), (54, 30), (54, -30), (38, -30)], 6), S([(60, -18), (60, 18)], 6)]

@shape('footprints')
def footprints():
    out = []
    sole = [(0, -30), (12, -24), (15, -5), (10, 15), (11, 30), (1, 42), (-10, 32), (-10, 12), (-13, -8), (-11, -25)]
    for dx, dy, sg in ((-24, 16, 1), (24, -16, -1)):
        out.append(S(catmull([(dx + px * sg * 1.15, dy + py * 1.15) for px, py in sole], 10, closed=True), 5, 0.8, False))
        for tx, ty, r in ((-9, -45, 4.5), (3, -49, 4), (13, -45, 3.5)):
            out.append(S(circle(dx + tx * sg * 1.15, dy + ty * 1.15 + 2, r), 3, 0.2, False))
    return out

@shape('moon')
def moon():
    r1, r2 = 46, 40; c2 = np.array([22., -12.]); dd = np.linalg.norm(c2)
    a = (r1 * r1 - r2 * r2 + dd * dd) / (2 * dd); h = math.sqrt(r1 * r1 - a * a); u = c2 / dd; pp = np.array([-u[1], u[0]])
    P1 = a * u + h * pp; P2 = a * u - h * pp
    def arcpts(c, r, ta, tb, want_far):
        best = None
        for sweep in ((tb - ta) % 360, (tb - ta) % 360 - 360):
            mid = math.radians(ta + sweep / 2); m = c + r * np.array([math.cos(mid), math.sin(mid)])
            score = np.linalg.norm(m - c2) if want_far else -np.linalg.norm(m)
            if best is None or score > best[0]: best = (score, sweep)
        ang = np.radians(np.linspace(ta, ta + best[1], 60))
        return np.stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)], 1)
    deg = lambda v: math.degrees(math.atan2(v[1], v[0]))
    outer = arcpts(np.zeros(2), r1, deg(P1), deg(P2), True)
    inner = arcpts(c2, r2, deg(P2 - c2), deg(P1 - c2), False)
    return [S(np.vstack([outer, inner]), 6), S([(38, -50), (38, -30)], 4, 0.4, False), S([(28, -40), (48, -40)], 4, 0.4, False)]

# a few generic extras for new topics
@shape('check')
def check(): return [S(catmull([(-40, 0), (-12, 30), (44, -38)], 8), 8)]

@shape('cross')
def cross(): return [S([(-36, -36), (36, 36)], 8), S([(36, -36), (-36, 36)], 8)]

@shape('star')
def star():
    pts = [(46 * (1 if i % 2 == 0 else 0.42) * math.cos(math.radians(-90 + 36 * i)),
            46 * (1 if i % 2 == 0 else 0.42) * math.sin(math.radians(-90 + 36 * i))) for i in range(11)]
    return [S(pts, 6)]

@shape('heart')
def heart():
    t = np.linspace(0, 2 * np.pi, 80)
    x = 16 * np.sin(t) ** 3; y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    return [S(np.stack([x, y], 1) * 2.8, 6)]

@shape('water')
def water():
    return [S([(-30, -42), (30, -42), (24, 46), (-24, 46), (-30, -42)], 6), S([(-27, -8), (27, -8)], 4, 1.0, False)]

def build_custom(spec):
    """{'shape':'custom','strokes':[[[x,y],...],...],'width':7,'smooth':true} in local px"""
    w = spec.get('width', 7); out = []
    for pts in spec['strokes']:
        P = catmull(pts, 10) if spec.get('smooth', True) and len(pts) > 2 else pts
        out.append(S(P, w))
    return out
