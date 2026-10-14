#!/usr/bin/env python3
"""Chalkboard explainer renderer (hand-drawn chalk + animated hand + optional chalk SFX).

  python code/render.py config/belly_fat.json --aspect 9x16 --sfx
  python code/render.py config/belly_fat.json --aspect both --sfx --sheet
  python code/render.py config/belly_fat.json --aspect 16x9 --stills 5 12.3   # quick PNG checks

Outputs go to output/<name>/ (relative to the kit) unless --out is given."""
import argparse, json, sys, time
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw, ImageFont
from chalkkit import board, layout
from chalkkit.animate import Animator


def contact_sheet(frames, times, path, font_path):
    w, h = frames[0].size; s = 960 / max(w, h)
    tw, th = int(w * s), int(h * s); pad = 20
    cols = 4 if h > w else 2; rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw + (cols + 1) * pad, rows * (th + 50) + pad), (24, 24, 24))
    d = ImageDraw.Draw(sheet); f = ImageFont.truetype(font_path, 30)
    for i, (im, t) in enumerate(zip(frames, times)):
        x = pad + (i % cols) * (tw + pad); y = pad + (i // cols) * (th + 50)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 40)); d.text((x, y), f'{t:g}s', font=f, fill=(240, 240, 230))
    sheet.save(path)


def render_aspect(cfg, aspect, args, outdir):
    if aspect not in cfg['layouts']: raise SystemExit(f'config has no layout for {aspect}')
    L = cfg['layouts'][aspect]; W, H = L['size']
    t0 = time.time(); print(f'[{aspect}] {W}x{H} building board ...', flush=True)
    board.init(W, H, cfg.get('seed', 7))
    bg = board.make_background(); grain = board.make_grain()
    els = layout.build(cfg, aspect, KIT)
    for t, k, box in layout.check_bounds(els): print(f'  WARNING: {k} at t={t}s extends outside the board: {box}')
    anim = Animator(els, bg, grain, cfg.get('duration', 25.0), cfg.get('fps', 30), L.get('hand_scale', 0.8))
    stem = f"{cfg['name']}_{aspect}"
    if args.stills:
        for t in args.stills:
            p = outdir / f'{stem}_{t:g}s.png'; Image.fromarray(anim.frame(t)).save(p); print('  still', p)
        return
    times = L.get('preview_times', [5, 10, 17, 24])
    silent = outdir / f'{stem}.mp4'
    if not args.no_video:
        print(f'  encoding {silent.name} ...', flush=True); anim.encode(silent)
    if args.sheet:
        frames = [Image.fromarray(anim.frame(t)) for t in times]
        contact_sheet(frames, times, outdir / f'{stem}_contact_sheet.png', str(KIT / cfg['fonts']['title']))
        print('  sheet', outdir / f'{stem}_contact_sheet.png')
    if args.sfx:
        if not silent.exists(): raise SystemExit('--sfx needs the silent video (drop --no-video)')
        from chalkkit.sfx import make_sfx
        r = make_sfx(anim, KIT / 'assets' / 'sfx', silent, outdir / f'{stem}_sfx.mp4', outdir / f'{stem}_sfx.wav')
        print(f'  sfx: {r}')
    print(f'[{aspect}] done in {time.time() - t0:.0f}s', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('config'); ap.add_argument('--aspect', default='9x16', choices=['9x16', '16x9', 'both'])
    ap.add_argument('--sfx', action='store_true', help='also write <name>_<aspect>_sfx.mp4 with chalk sound')
    ap.add_argument('--sheet', action='store_true', help='write a contact sheet at the layout preview_times')
    ap.add_argument('--stills', type=float, nargs='+', help='only render PNG stills at these times (seconds)')
    ap.add_argument('--no-video', action='store_true', help='skip the mp4 (e.g. with --sheet)')
    ap.add_argument('--out', help='output directory (default output/<name>/)')
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute() and not cfg_path.exists(): cfg_path = KIT / cfg_path
    cfg = json.loads(cfg_path.read_text())
    outdir = Path(args.out) if args.out else KIT / 'output' / cfg['name']; outdir.mkdir(parents=True, exist_ok=True)
    for a in (['9x16', '16x9'] if args.aspect == 'both' else [args.aspect]): render_aspect(cfg, a, args, outdir)


if __name__ == '__main__':
    main()
