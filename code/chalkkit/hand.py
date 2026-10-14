"""Hand compositor: draws the sprite so the chalk tip lands exactly on `tip`, with wobble,
position-dependent forearm angle (always trailing down-right of the hand) and a soft shadow."""
import math
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom
from . import hand_sprite


class Hand:
    def __init__(s, W, H, scale=0.8):
        s.W, s.H, s.SC = W, H, scale
        s.sprite, (s.SX, s.SY), s.ARM = hand_sprite.build()

    def composite(s, img, tip, lift, t, drawing):
        """img float HxWx3; tip (x,y); lift 0..1 (raised off the board); drawing adds fine tremor."""
        W, H = s.W, s.H
        tx, ty = float(tip[0]), float(tip[1])
        psi = 40 + 20 * (tx / W - 0.5) - 14 * (ty / H - 0.5)      # forearm angle varies gently with position
        wob = (2.2 * math.sin(2 * math.pi * 0.55 * t) + 1.1 * math.sin(2 * math.pi * 1.6 * t + 1.3)
               + (0.7 * math.sin(2 * math.pi * 4.3 * t) if drawing else 0))
        phi = math.radians(psi - s.ARM + wob)
        sc = s.SC * (1 + 0.06 * lift)
        c, sn = math.cos(phi), math.sin(phi)
        A = (c / sc, sn / sc, s.SX - (c * tx + sn * ty) / sc, -sn / sc, c / sc, s.SY - (-sn * tx + c * ty) / sc)
        h = np.asarray(s.sprite.transform((W, H), Image.AFFINE, A, resample=Image.BICUBIC), np.float32)
        ha = h[..., 3] / 255
        q = 4; sh = gaussian_filter(ha[::q, ::q], 3 + 3 * lift)
        ox, oy = int((16 + 45 * lift) / q), int((22 + 60 * lift) / q)
        shs = np.zeros_like(sh); shs[oy:, ox:] = sh[:sh.shape[0] - oy, :sh.shape[1] - ox]
        shf = zoom(shs, q, order=1)[:H, :W]
        img = img * (1 - (0.42 - 0.15 * lift) * shf[..., None])
        return img * (1 - ha[..., None]) + h[..., :3] * ha[..., None]
