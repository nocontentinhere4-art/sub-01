"""Project the reference photos onto the head's base colour (per-texel facing weights, visibility, feathered masks).
python bake.py <glb> <mesh dump dir> <cams.json> <out dir>"""
import json, sys, numpy as np, cv2
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from rend import Renderer
from lm import landmarks

GLB, MD, CAMS, OUT = sys.argv[1:5]
MD, OUT = Path(MD), Path(OUT); OUT.mkdir(exist_ok=True, parents=True)
REFS = Path(__file__).resolve().parents[2] / 'docs/design/char-tripo/refs'
Image.MAX_IMAGE_PIXELS = None

pos = np.fromfile(MD / 'pos.f32', np.float32).reshape(-1, 3)
nrm = np.fromfile(MD / 'nrm.f32', np.float32).reshape(-1, 3)
uv = np.fromfile(MD / 'uv.f32', np.float32).reshape(-1, 2)
idx = np.fromfile(MD / 'idx.u32', np.uint32).reshape(-1, 3)
base = np.asarray(Image.open(MD / 'base.jpeg').convert('RGB')).astype(np.float32) / 255
T = base.shape[0]

# ---- texel -> world position / normal for the head (UV-space rasterisation of the head triangles) ----
HEAD_Y = 0.80
tri = idx[(pos[idx][:, :, 1] > HEAD_Y).all(1)]
print('head triangles', len(tri))
P = np.zeros((T, T, 3), np.float32); N = np.zeros((T, T, 3), np.float32); M = np.zeros((T, T), bool)
for a, b, c in tri:
    t = uv[[a, b, c]] * T - 0.5                         # texel centres at integer coords (glTF uv: v down = image row)
    x0, y0 = np.floor(t.min(0)).astype(int); x1, y1 = np.ceil(t.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, T - 1), min(y1, T - 1)
    if x1 < x0 or y1 < y0: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    v0, v1 = t[1] - t[0], t[2] - t[0]
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) < 1e-12: continue
    px, py = gx - t[0, 0], gy - t[0, 1]
    l1 = (px * v1[1] - v1[0] * py) / den; l2 = (v0[0] * py - px * v0[1]) / den; l0 = 1 - l1 - l2
    inside = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
    if not inside.any(): continue
    yy, xx = gy[inside], gx[inside]
    w = np.stack([l0[inside], l1[inside], l2[inside]], 1)
    P[yy, xx] = w @ pos[[a, b, c]]; N[yy, xx] = w @ nrm[[a, b, c]]; M[yy, xx] = True
N /= np.linalg.norm(N, axis=2, keepdims=True) + 1e-9
ty, tx = np.nonzero(M)
Xw, Nw = P[ty, tx].astype(np.float64), N[ty, tx].astype(np.float64)
print('head texels', len(ty))

# ---- per view: project, visibility, weights, masks ----
cams = json.load(open(CAMS))
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150,
             136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
EYES = [[33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
        [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]]
R_ = Renderer(GLB)


def soft(mask, r):
    return cv2.GaussianBlur(mask.astype(np.float32), (0, 0), r)


def lum(img):
    return img @ np.array([0.299, 0.587, 0.114])


views = {}
for name, c in cams.items():
    photo_path = REFS / f'{name}.png'
    photo = np.asarray(Image.open(photo_path).convert('RGB')).astype(np.float32) / 255
    H, W = photo.shape[:2]
    R, t = np.array(c['R']), np.array(c['t'])
    Xc = Xw @ R.T + t
    if 'ortho' in c:
        l, r, tp, bt = c['ortho']
        # camera coords: x right, y down (OpenCV); ortho box is in three's camera space (y up)
        u = (Xc[:, 0] - l) / (r - l) * W; v = (tp - (-Xc[:, 1])) / (tp - bt) * H
        dirc = np.tile(-R[2], (len(Xw), 1))            # towards the camera
        cam = {'ortho': c['ortho'], 'R': R, 't': t}
    else:
        K = np.array(c['K']); pr = Xc @ K.T
        u, v = pr[:, 0] / pr[:, 2], pr[:, 1] / pr[:, 2]
        C = -R.T @ t; dirc = C - Xw; dirc /= np.linalg.norm(dirc, axis=1, keepdims=True)
        cam = {'K': K, 'R': R, 't': t}
    ui, vi = np.round(u - 0.5).astype(int), np.round(v - 0.5).astype(int)
    inb = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    ui, vi = np.clip(ui, 0, W - 1), np.clip(vi, 0, H - 1)
    x0, y0 = ui[inb].min(), vi[inb].min(); x1, y1 = ui[inb].max() + 1, vi[inb].max() + 1
    _, Pv = R_.view(cam, W, H, crop=[x0, y0, x1 - x0, y1 - y0])
    hit = np.zeros((len(ui), 4), np.float32)
    hit[inb] = Pv[vi[inb] - y0, ui[inb] - x0]
    scale = 0.002 if 'ortho' not in c else 0.004
    vis = inb & (hit[:, 3] > 0) & (np.linalg.norm(hit[:, :3] - Xw, axis=1) < scale)
    cosf = (Nw * dirc).sum(1)
    wf = np.clip((cosf - 0.2) / 0.8, 0, 1) ** 2
    # photo-space mask
    if 'ortho' in c:
        sk = photo.copy(); L = lum(sk)
        r_, g_, b_ = sk[..., 0], sk[..., 1], sk[..., 2]
        skin = (L > 0.25) & (r_ > g_) & (g_ >= b_ * 0.9)
        pm = soft(cv2.erode(skin.astype(np.uint8), np.ones((11, 11))), 3) * 0.6   # profiles: lower trust (small, soft)
        eyes = np.zeros((H, W), np.float32)
    else:
        lp = landmarks(str(photo_path))
        oval = np.zeros((H, W), np.uint8); cv2.fillPoly(oval, [lp[FACE_OVAL].astype(np.int32)], 1)
        oval = cv2.erode(oval, np.ones((15, 15)))
        notdark = np.clip((lum(photo) - 0.12) / 0.15, 0, 1)
        pm = np.clip(soft(cv2.erode(oval, np.ones((25, 25))), 22) * 1.15, 0, 1) * soft(notdark, 2)
        eyes = np.zeros((H, W), np.uint8)
        for e in EYES: cv2.fillPoly(eyes, [lp[e].astype(np.int32)], 1)
        eyes = soft(cv2.dilate(eyes, np.ones((9, 9))), 3)
        pm = np.maximum(pm, eyes * soft(oval, 10))
    col = cv2.remap(photo, u.astype(np.float32) - 0.5, v.astype(np.float32) - 0.5, cv2.INTER_LINEAR)[:, 0] \
        if False else photo[vi, ui]
    w = wf * vis * pm[vi, ui] * {'face_front': 1.0}.get(name, 0.8)
    if 'ortho' in c:   # profiles add skin only (no stray hair strands painted over the ears and temples)
        Lc = lum(col); w = w * np.clip((Lc - 0.3) / 0.1, 0, 1) * np.clip((lum(base[ty, tx]) - 0.25) / 0.08, 0, 1)
    views[name] = dict(col=col, w=w, eye=eyes[vi, ui] * vis)
    print(name, 'visible', int(vis.sum()), 'weighted', int((w > 0.05).sum()))
R_.close()

# ---- colour-match: the 3/4 views to the front, then the profiles to the blend of the three close-ups ----
PROFILE_W = float(__import__('os').environ.get('PROFILE_W', '0'))
ref = views['face_front']
for name in ('face_3q_a', 'face_3q_b'):
    vw = views[name]; both = (vw['w'] > 0.2) & (ref['w'] > 0.2)
    if both.sum() > 500:
        gain = np.clip(ref['col'][both].mean(0) / (vw['col'][both].mean(0) + 1e-6), 0.7, 1.4); vw['col'] = np.clip(vw['col'] * gain, 0, 1)
        print(name, 'gain', gain.round(3), int(both.sum()))
close = ['face_front', 'face_3q_a', 'face_3q_b']
wc = sum(views[n]['w'] for n in close) + 1e-9
cc = sum(views[n]['col'] * views[n]['w'][:, None] for n in close) / wc[:, None]
for name in ('body_side_left', 'body_side_right'):
    vw = views[name]; both = (vw['w'] > 0.1) & (wc > 0.2)
    gain = np.clip(cc[both].mean(0) / (vw['col'][both].mean(0) + 1e-6), 0.7, 1.4) if both.sum() > 300 else np.ones(3)
    vw['col'] = np.clip(vw['col'] * gain, 0, 1); vw['w'] = vw['w'] * PROFILE_W
    print(name, 'gain', gain.round(3), int(both.sum()))

ws = sum(v['w'] for v in views.values()) + 1e-9
photo_col = sum(v['col'] * v['w'][:, None] for v in views.values()) / ws[:, None]
x_ = np.clip(ws / 0.6, 0, 1); cover = x_ * x_ * (3 - 2 * x_)       # smoothstep: a soft edge into the old skin
eye = np.clip(sum(v['eye'] for v in views.values()), 0, 1)

old = base[ty, tx]
Lo, Lp = lum(old), lum(photo_col)
# keep the mesh's hair: a dark texel (hair) does not take a light photo colour, except in the eyes
hairkeep = np.clip((0.22 - Lo) / 0.08, 0, 1) * np.clip((Lp - 0.25) / 0.1, 0, 1) * (1 - eye)
a = cover * (1 - hairkeep)

# ---- tone: bring the rest of the skin (neck, ears, body) towards the photo's skin ----
skin_old = (Lo > 0.35) & (old[:, 0] > old[:, 1]) & (cover > 0.8)
gain_all = np.clip(photo_col[skin_old].mean(0) / (old[skin_old].mean(0) + 1e-6), 0.8, 1.25)
print('skin tone gain for the rest of the skin', gain_all.round(3), int(skin_old.sum()))
L_all = lum(base); r_, g_, b_ = base[..., 0], base[..., 1], base[..., 2]
skin_all = np.clip((L_all - 0.3) / 0.1, 0, 1) * ((r_ > g_ * 1.05) & (g_ >= b_ * 0.95))
skin_all = soft(skin_all, 2)[..., None]
newbase = base * (1 - skin_all) + np.clip(base * gain_all, 0, 1) * skin_all

new = newbase[ty, tx] * (1 - a[:, None]) + photo_col * a[:, None]
newbase[ty, tx] = new
# chart borders: texels just outside the rasterised head charts take the nearest baked value (8 px), so filtering
# and mipmaps at UV seams do not pick up the old colour
def bleed(img, mask, px=8):
    img = img.copy(); m = mask.astype(np.uint8)
    acc = img * m[..., None]
    for _ in range(px):
        k = np.ones((3, 3), np.float32)
        s_ = cv2.filter2D(acc, -1, k, borderType=cv2.BORDER_CONSTANT); c_ = cv2.filter2D(m.astype(np.float32), -1, k, borderType=cv2.BORDER_CONSTANT)
        new = (c_ > 0) & (m == 0)
        acc[new] = s_[new] / c_[new][:, None]; m = m | new.astype(np.uint8)
    out = img.copy(); grown = (m > 0) & ~mask
    out[grown] = acc[grown]; return out
# atlas coverage of every triangle (cv2 fill at texel resolution, 1 px grown): only empty atlas space is filled
cover_all = np.zeros((T, T), np.uint8)
tuv = (uv[idx] * T - 0.5)
cv2.fillPoly(cover_all, [t_.round().astype(np.int32) for t_ in tuv], 1)
cover_all = cv2.dilate(cover_all, np.ones((3, 3), np.uint8)) > 0
filled = bleed(newbase, M)
empty = ~cover_all
newbase[empty] = filled[empty]
Image.fromarray((np.clip(newbase, 0, 1) * 255 + 0.5).astype(np.uint8)).save(OUT / 'base_baked.png')
am = np.zeros((T, T), np.float32); am[ty, tx] = a
Image.fromarray((am * 255).astype(np.uint8)).save(OUT / 'alpha.png')
dom = np.zeros((T, T, 3), np.float32)
dom[ty, tx, 0] = views['face_front']['w'] / ws * a; dom[ty, tx, 1] = (views['face_3q_a']['w'] + views['face_3q_b']['w']) / ws * a
dom[ty, tx, 2] = (views['body_side_left']['w'] + views['body_side_right']['w']) / ws * a
Image.fromarray((dom * 255).astype(np.uint8)).save(OUT / 'dom.png')
np.save(OUT / 'texels.npy', np.stack([ty, tx]))
print('done', OUT)

# ---- shading: flat normals on the head's skin (the normal map's creases read as age and turn the eyes grey),
#      skin roughness 0.5 and no metalness everywhere ----
nb = newbase
Ln = lum(nb); rr, gg, bb = nb[..., 0], nb[..., 1], nb[..., 2]
skin_new = np.clip((Ln - 0.25) / 0.1, 0, 1) * ((rr > gg * 1.03) & (gg >= bb * 0.9))
headm = np.zeros((T, T), np.float32); headm[ty, tx] = 1
eyes_t = np.zeros((T, T), np.float32); eyes_t[ty, tx] = eye
flat_w = np.clip(soft(np.maximum(skin_new * headm, eyes_t), 3) * 1.3, 0, 1)
nm = np.asarray(Image.open(MD / 'normal.png').convert('RGB')).astype(np.float32) / 255 * 2 - 1
flat = np.array([0, 0, 1.0], np.float32)
nm2 = nm * (1 - flat_w[..., None]) + flat * flat_w[..., None]
nm2 /= np.linalg.norm(nm2, axis=2, keepdims=True) + 1e-9
Image.fromarray(((nm2 * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(OUT / 'normal_baked.png')
orm = np.asarray(Image.open(MD / 'orm.jpeg').convert('RGB')).astype(np.float32) / 255
sk = np.clip(soft(np.maximum(skin_new, eyes_t), 2) * 1.2, 0, 1)
orm[..., 1] = orm[..., 1] * (1 - sk) + 0.5 * sk
orm[..., 2] = orm[..., 2] * (1 - sk)
Image.fromarray((orm * 255 + 0.5).astype(np.uint8)).save(OUT / 'orm_baked.png')
print('normals flattened on', int((flat_w > 0.5).sum()), 'texels; skin roughness set on', int((sk > 0.5).sum()))
