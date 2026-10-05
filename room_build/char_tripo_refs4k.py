# python room_build/char_tripo_refs4k.py <out dir> : the four body views at 4096 px for Tripo (v3). Lanczos 2x upscale of the
# same images, then a mild unsharp mask on the head region only (feathered edge). Nothing is painted or moved.
from PIL import Image, ImageFilter
import numpy as np, os, sys
R = os.path.join(os.path.dirname(__file__), '..', 'docs/design/char-tripo/refs') + '/'; O = sys.argv[1] + '/'
os.makedirs(O, exist_ok=True)
for n in ['body_front', 'body_side_left', 'body_back', 'body_side_right']:
    im = Image.open(R + n + '.png').convert('RGB'); a = np.asarray(im).sum(2) > 60; ys, xs = np.nonzero(a)
    top = ys.min(); h = int((ys.max() - top) * 0.15); cx = int(xs[ys < top + h].mean())
    big = im.resize((4096, 4096), Image.LANCZOS)
    box = tuple(int(v * 2) for v in (cx - h * 0.8, top - h * 0.1, cx + h * 0.8, top + h * 1.25))
    face = big.crop(box).filter(ImageFilter.UnsharpMask(radius=2.5, percent=70, threshold=2))
    yy, xx = np.mgrid[0:face.size[1], 0:face.size[0]]
    d = np.minimum.reduce([xx, yy, face.size[0] - 1 - xx, face.size[1] - 1 - yy]).astype(np.float32)
    big.paste(face, box[:2], Image.fromarray((np.clip(d / 40, 0, 1) * 255).astype(np.uint8)))
    big.save(O + n + '.png', optimize=True); print(n, box)
