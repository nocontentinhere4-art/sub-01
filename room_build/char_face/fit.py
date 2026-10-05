"""Fit a camera to each reference photo so the mesh lines up with it.
Face close-ups: mediapipe landmarks on the photo and on a render of the mesh (3D from the position buffer), then
PnP with a scan over focal length. Profiles (body side photos): orthographic, fitted to the head silhouette."""
import json, sys, numpy as np, cv2
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from rend import Renderer, lookat
from lm import landmarks

HERE = Path(__file__).parent
REFS = Path(__file__).resolve().parents[2] / 'docs/design/char-tripo/refs'
GLB = sys.argv[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / 'cams.json'
F = 0.89                                               # face height in rig units (mesh 0.98 tall, faces +X)
GUESS = {'face_front': (1, 0), 'face_3q_a': (0.71, -0.71), 'face_3q_b': (0.71, 0.71)}

R_ = Renderer(GLB)
print(R_.info)
cams = {}
FOC = float(__import__('os').environ.get('FOC', 'nan')); FOC = None if FOC != FOC else FOC
for name, (dx, dz) in GUESS.items():
    photo = np.asarray(Image.open(REFS / f'{name}.png').convert('RGB'))
    H, W = photo.shape[:2]
    lp = landmarks(str(REFS / f'{name}.png'))
    # render the mesh from a guess and take 3D landmarks from it
    d = 0.6
    K0 = np.array([[W * 2.2, 0, W / 2], [0, W * 2.2, H / 2], [0, 0, 1]])
    R0, t0 = lookat([d * dx, F, d * dz], [0, F, 0])
    best = None
    for it in range(2):
        rgb, P = R_.view({'K': K0, 'R': R0, 't': t0}, W, H)
        lr = landmarks(rgb)
        if lr is None:
            if best is None: sys.exit(f'{name}: no face found in the render')
            print(name, 'no face in the refit render; keeping the previous fit'); break
        ij = np.clip(lr.round().astype(int), 0, [W - 1, H - 1])
        X = P[ij[:, 1], ij[:, 0], :3]; ok = P[ij[:, 1], ij[:, 0], 3] > 0
        X, x = X[ok].astype(np.float64), lp[ok].astype(np.float64)
        prev = best; best = None
        for f in (np.geomspace(W * 0.8, W * 8, 40) if FOC is None else [FOC * W]):
            K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
            rv0 = cv2.Rodrigues(R0)[0]; tv0 = t0.reshape(3, 1).astype(np.float64)
            s, rv, tv = cv2.solvePnP(X, x, K, None, rv0.copy(), tv0.copy(), True, flags=cv2.SOLVEPNP_ITERATIVE)
            pr = cv2.projectPoints(X, rv, tv, K, None)[0][:, 0]
            e = np.sqrt(((pr - x) ** 2).sum(1)).mean()
            if best is None or e < best[0]: best = (e, f, rv, tv, K)
        e, f, rv, tv, K = best
        if prev is not None and prev[0] < e: e, f, rv, tv, K = prev; best = prev; print(name, 'refit worse; keep'); break
        R0, t0, K0 = cv2.Rodrigues(rv)[0], tv[:, 0], K   # re-render from the fit and refit (landmarks on a matching view)
        print(name, 'iter', it, 'reproj px', round(e, 2), 'f/W', round(f / W, 2), 'n', len(X))
    if name == 'face_front' and FOC is None: FOC = K0[0, 0] / W      # the close-ups share a lens: reuse the front's focal length
    cams[name] = {'K': K0.tolist(), 'R': R0.tolist(), 't': t0.tolist(), 'err': e, 'W': W, 'H': H}
    rgb, _ = R_.view({'K': K0, 'R': R0, 't': t0}, W, H, pos=False)
    Image.fromarray(np.concatenate([photo, rgb, (photo * 0.5 + rgb * 0.5).astype(np.uint8)], 1)).resize((1536, 512)).save(HERE / f'fit_{name}.jpg')

# profiles: orthographic, camera on his left (-Z) or right (+Z), fitted to the whole-figure silhouette (at 1/4 size)
for name, side in (('body_side_left', -1), ('body_side_right', 1)):
    photo = np.asarray(Image.open(REFS / f'{name}.png').convert('RGB')); H, W = photo.shape[:2]
    q = 4; h4, w4 = H // q, W // q
    m = cv2.resize((photo.astype(int).sum(2) > 45).astype(np.uint8), (w4, h4), interpolation=cv2.INTER_AREA) > 0
    ys, xs = np.nonzero(m); top, bot = ys.min(), ys.max()
    R0, t0 = lookat([0, 0.49, side * 3.0], [0, 0.49, 0])
    ren = lambda span, cx, cy, ww, hh, **k: R_.view({'ortho': [cx - span, cx + span, cy + span, cy - span], 'R': R0, 't': t0}, ww, hh, **k)
    span, cx, cy = 0.6, 0.0, 0.0
    for it in range(4):
        _, P = ren(span, cx, cy, w4, h4); ry, rx = np.nonzero(P[..., 3] > 0); ppu = h4 / (2 * span)
        span = h4 / (2 * ((bot - top) / ((ry.max() - ry.min()) / ppu)))
        _, P = ren(span, cx, cy, w4, h4); ry, rx = np.nonzero(P[..., 3] > 0); ppu = h4 / (2 * span)
        cy -= (ry.min() - top) / ppu
        hp = xs[ys < top + 0.12 * (bot - top)].mean(); hr = rx[ry < ry.min() + 0.12 * (ry.max() - ry.min())].mean()
        cx += (hr - hp) / ppu
    _, P = ren(span, cx, cy, w4, h4); mm = P[..., 3] > 0
    print(name, 'silhouette IoU', round((mm & m).sum() / (mm | m).sum(), 3))
    cams[name] = {'ortho': [cx - span, cx + span, cy + span, cy - span], 'R': R0.tolist(), 't': t0.tolist(), 'W': W, 'H': H}
    c0, r0, hh = int(hp * q), top * q, int(0.16 * (bot - top) * q)
    crop = [max(c0 - hh // 2, 0), max(r0 - hh // 6, 0), hh, hh]
    # refine on the head alone: scale and shift that best overlap the head silhouettes in the crop (full resolution)
    pmask = photo[crop[1]:crop[1] + hh, crop[0]:crop[0] + hh].astype(int).sum(2) > 45
    best = (-1, span, cx, cy)
    for k in np.linspace(0.92, 1.08, 9):
        sp = span / k
        _, P = ren(sp, cx, cy, W, H, crop=crop); rm = (P[..., 3] > 0).astype(np.uint8)
        ppu = H / (2 * sp)
        for dy in range(-30, 31, 3):
            for dx in range(-30, 31, 3):
                sh = np.roll(np.roll(rm, dy, 0), dx, 1) > 0
                iou = (sh & pmask).sum() / (sh | pmask).sum()
                if iou > best[0]: best = (iou, sp, cx - dx / ppu, cy + dy / ppu)
    iou, span, cx, cy = best
    print(name, 'head IoU', round(iou, 3))
    cams[name]['ortho'] = [cx - span, cx + span, cy + span, cy - span]
    rgb, _ = ren(span, cx, cy, W, H, pos=False, crop=crop)
    pc = photo[crop[1]:crop[1] + hh, crop[0]:crop[0] + hh]
    Image.fromarray(np.concatenate([pc, rgb, (pc * 0.5 + rgb * 0.5).astype(np.uint8)], 1)).save(HERE / f'fit_{name}.jpg')

json.dump(cams, open(OUT, 'w'), indent=1)
R_.close()
