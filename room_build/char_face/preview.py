"""reference | before | after at the fitted cameras. python preview.py <glb> <cams.json> <texture.png|-> <out.jpg> [glb_after]"""
import json, sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
from rend import Renderer

GLB, CAMS, TEX, OUT = sys.argv[1:5]
GLB2 = sys.argv[5] if len(sys.argv) > 5 else GLB
REFS = Path(__file__).resolve().parents[2] / 'docs/design/char-tripo/refs'
cams = json.load(open(CAMS))
S = 512


def lab(im, t):
    im = Image.fromarray(im) if isinstance(im, np.ndarray) else im
    d = ImageDraw.Draw(im); d.rectangle([0, 0, len(t) * 6 + 10, 16], fill=(0, 0, 0)); d.text((5, 3), t, fill=(255, 255, 255)); return im


def shots(r):
    out = {}
    for name, c in cams.items():
        W, H = c['W'], c['H']
        cam = {k: np.array(v) if k in ('K', 'R', 't') else v for k, v in c.items() if k in ('K', 'R', 't', 'ortho')}
        if 'ortho' in c:
            photo = np.asarray(Image.open(REFS / f'{name}.png').convert('RGB'))
            m = photo.astype(int).sum(2) > 45; ys, xs = np.nonzero(m); top, bot = ys.min(), ys.max()
            hh = int(0.16 * (bot - top)); hp = int(xs[ys < top + 0.12 * (bot - top)].mean())
            crop = [max(hp - hh // 2, 0), max(top - hh // 6, 0), hh, hh]
            rgb, _ = r.view(cam, W, H, pos=False, crop=crop)
            ref = photo[crop[1]:crop[1] + hh, crop[0]:crop[0] + hh]
        else:
            rgb, _ = r.view(cam, W, H, pos=False); ref = np.asarray(Image.open(REFS / f'{name}.png').convert('RGB'))
        out[name] = (ref, rgb)
    return out


r = Renderer(GLB); before = shots(r); r.close()
r = Renderer(GLB2)
for spec in TEX.split(','):                      # path or slot=path
    if spec == '-': continue
    slot, path = spec.split('=') if '=' in spec else ('map', spec)
    r.set_texture(path, slot)
after = shots(r); r.close()
rows = list(cams)
sheet = Image.new('RGB', (3 * S, S * len(rows)))
for i, n in enumerate(rows):
    ref, b = before[n]; _, a = after[n]
    for j, (im, t) in enumerate(((ref, f'reference {n}'), (b, 'before'), (a, 'after'))):
        sheet.paste(lab(Image.fromarray(im).resize((S, S)), t), (j * S, i * S))
sheet.save(OUT, quality=90)
