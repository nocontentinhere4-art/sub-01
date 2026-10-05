"""Reshape the face to the reference photos: mediapipe landmarks on the photos (front, 3q_a, 3q_b) are triangulated with
the fitted cameras; the mesh's own landmarks (from renders at the same cameras) are moved onto them, and the move is
spread over the head with a Gaussian RBF that falls to zero away from the face (hair, ears, neck stay put).
python warp.py <glb> <mesh dump dir> <cams.json> <out dir> [strength]"""
import json, sys, numpy as np, cv2
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rend import Renderer
from lm import landmarks

GLB, MD, CAMS, OUT = sys.argv[1:5]
STRENGTH = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
MD, OUT = Path(MD), Path(OUT); OUT.mkdir(parents=True, exist_ok=True)
REFS = Path(__file__).resolve().parents[2] / 'docs/design/char-tripo/refs'
pos = np.fromfile(MD / 'pos.f32', np.float32).reshape(-1, 3).astype(np.float64)
idx = np.fromfile(MD / 'idx.u32', np.uint32).reshape(-1, 3)
cams = json.load(open(CAMS))
VIEWS = ['face_front', 'face_3q_a', 'face_3q_b']
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150,
             136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]

R_ = Renderer(GLB)
Xs, Ps, Pm = {}, {}, {}
for v in VIEWS:
    c = cams[v]; K, R, t = (np.array(c[k]) for k in ('K', 'R', 't')); W, H = c['W'], c['H']
    rgb, P = R_.view({'K': K, 'R': R, 't': t}, W, H)
    lr = landmarks(rgb); lp = landmarks(str(REFS / f'{v}.png'))
    ij = np.clip(lr.round().astype(int), 0, [W - 1, H - 1])
    X = P[ij[:, 1], ij[:, 0]]
    Xs[v] = np.where(X[:, 3:] > 0, X[:, :3], np.nan); Pm[v] = lp
    Ps[v] = K @ np.hstack([R, t[:, None]])
R_.close()

# the mesh's landmark points: the front render's, or the mean of the views that agree with it
Xf = Xs['face_front']
Xall = np.stack([Xs[v] for v in VIEWS])
agree = np.linalg.norm(Xall - Xf, axis=2) < 0.004
Xm = np.nanmean(np.where(agree[..., None], Xall, np.nan), axis=0)
Xm = np.where(np.isnan(Xm), Xf, Xm)

# targets: linear triangulation over the three photos
T = np.zeros_like(Xm)
for i in range(len(Xm)):
    A = []
    for v in VIEWS:
        P = Ps[v]; x, y = Pm[v][i]
        A += [x * P[2] - P[0], y * P[2] - P[1]]
    _, _, Vt = np.linalg.svd(np.array(A)); X = Vt[-1]; T[i] = X[:3] / X[3]
# the oval (silhouette points differ between views): move only in the front camera's image plane
c = cams['face_front']; K, R, t = (np.array(c[k]) for k in ('K', 'R', 't'))
for i in FACE_OVAL:
    Xc = R @ Xm[i] + t; z = Xc[2]
    ray = np.linalg.inv(K) @ np.array([*Pm['face_front'][i], 1.0])
    T[i] = R.T @ (ray * z - t)
D = (T - Xm) * STRENGTH
ok = ~np.isnan(D).any(1)
ok[FACE_OVAL] = False            # silhouette points are not the same surface point in every view: they tore the cheeks
JAW = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323, 454]
JAWCL = float(__import__('os').environ.get('JAWCL', '0.005'))
if '--jaw' in sys.argv:          # ...except the lower jaw, moved in the front image plane only, gently
    ok[JAW] = True
    jm = np.linalg.norm(D[JAW], axis=1); D[JAW] *= np.minimum(1, JAWCL / (jm + 1e-9))[:, None]
mag = np.linalg.norm(D, axis=1)
print('landmark moves (rig units; 1 unit = 1.786 m): median', np.nanmedian(mag).round(4), 'p90', np.nanpercentile(mag, 90).round(4),
      'max', np.nanmax(mag).round(4))
CL = 0.008
D = np.where((mag > CL)[:, None], D * (CL / mag)[:, None], D)   # clamp at 1.4 cm
C, D = Xm[ok], D[ok]
# thin the centres (mediapipe's mesh is dense) and add zero anchors around the face
keep = [0]
for i in range(1, len(C)):
    if np.linalg.norm(C[keep] - C[i], axis=1).min() > 0.003: keep.append(i)
C, D = C[keep], D[keep]
head = np.nonzero(pos[:, 1] > 0.74)[0]
dist = np.array([np.linalg.norm(C - p, axis=1).min() for p in pos[head]])
far = head[dist > 0.012]
rng = np.random.default_rng(0)
anc = pos[rng.choice(far, min(600, len(far)), replace=False)]
Cc = np.vstack([C, anc]); Dc = np.vstack([D, np.zeros((len(anc), 3))])
SIG = 0.010
Kmat = np.exp(-((Cc[:, None] - Cc[None]) ** 2).sum(2) / (2 * SIG ** 2))
Wt = np.linalg.solve(Kmat + 3e-2 * np.eye(len(Cc)), Dc)
# hair stays where it is: vertices whose texture is dark do not move
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
uv = np.fromfile(MD / 'uv.f32', np.float32).reshape(-1, 2)
base = np.asarray(Image.open(MD / 'base.jpeg').convert('L')).astype(np.float32) / 255
Tn = base.shape[0]
vl = base[np.clip((uv[:, 1] * Tn).astype(int), 0, Tn - 1), np.clip((uv[:, 0] * Tn).astype(int), 0, Tn - 1)]
skinv = np.clip((vl - 0.22) / 0.12, 0, 1)
# vertices split along UV seams share a position: give them one value (the largest), or the mesh tears at the seams
_, grp = np.unique(np.round(pos * 1e6).astype(np.int64), axis=0, return_inverse=True)
gmax = np.zeros(grp.max() + 1); np.maximum.at(gmax, grp.ravel(), skinv); skinv = gmax[grp.ravel()]
newpos = pos.copy()
for s in range(0, len(head), 5000):
    hv = head[s:s + 5000]
    k = np.exp(-((pos[hv][:, None] - Cc[None]) ** 2).sum(2) / (2 * SIG ** 2))
    d = k @ Wt
    fall = (np.clip((pos[hv, 1] - 0.77) / 0.03, 0, 1) * skinv[hv])[:, None]   # not below the jaw line, not the hair
    newpos[hv] = pos[hv] + d * fall
moved = np.linalg.norm(newpos - pos, axis=1)
print('vertices moved > 1 mm:', int((moved > 0.00056).sum()), 'max', moved.max().round(4))
newpos.astype(np.float32).tofile(OUT / 'pos_warp.f32')
json.dump({'centres': len(C), 'anchors': len(anc), 'sigma': SIG, 'strength': STRENGTH}, open(OUT / 'warp.json', 'w'))
