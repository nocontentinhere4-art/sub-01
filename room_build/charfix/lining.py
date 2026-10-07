# the hood's inner lining for v5, following the hood's own inner wall: for each angle round the neck, from the hood's top
# rim down the inside of its wall (OFF inside it, facing the neck) to its lip, then down to the neck DROP below the lip
from lib import *
from radial import crossings
import sys
B = load('v5', 'tripo_node_6bf04053-_0'); H = load('v5', 'tripo_node_6bf04053-_1'); PB, PH = world_v5(B), world_v5(H)
NT, OFF, DROP = 120, 0.003, float(sys.argv[1]) if len(sys.argv) > 1 else 0.025
c0 = np.array([0.0017, 0, -0.0109])
def sub(P, T, y0, y1, rmax):              # the triangles in the collar's box
    v = P[T]; m = (v[:, :, 1].max(1) > y0) & (v[:, :, 1].min(1) < y1) & (np.hypot(v[:, :, 0] - c0[0], v[:, :, 2] - c0[2]).min(1) < rmax)
    return T[m]
TB, TH = sub(PB, B['idx'], 1.37, 1.56, 0.20), sub(PH, H['idx'], 1.38, 1.56, 0.12)
ys = np.round(np.arange(1.400, 1.545, 0.002), 3)
def dense(A, i):
    w = np.zeros(79)
    for j, x in zip(A['JOINTS_0'][i].astype(int), A['WEIGHTS_0'][i]): w[j] += x
    return w
from scipy.spatial import cKDTree
kB, kH = cKDTree(PB), cKDTree(PH)
profiles = []
for b in range(NT):
    th = (b + 0.5) / NT * 2 * np.pi
    _, cb = crossings(PB, TB, c0, th, list(ys)); _, ch = crossings(PH, TH, c0, th, list(ys))
    neck = {y: (max(ch[y]) if ch[y] else None) for y in ys}            # (the neck's surface: its outermost crossing)
    wall = {}
    for y in ys:
        rn = neck[y] if neck[y] else 0.05
        rs = [r for r in cb[y] if r > rn + 0.004 and r < 0.16]
        if rs: wall[y] = min(rs)
    if not wall: profiles.append(None); continue
    # the hood's wall near the neck, from the top down: the highest height it reaches near the neck, then down to its lip
    # (its innermost point); below the lip it falls away (the bowl), where the lining leaves it for the neck
    yt = max(wall); ylip = min(wall, key=lambda y: (wall[y], -y))
    prof = [(wall[yt] - 0.0015, yt - 0.0005)] + [(wall[y] - OFF, y) for y in sorted(wall, reverse=True) if y >= ylip]   # (over the rim's own edge first)
    # (at the back the reference's lining is a thick roll hugging the nape: there the lining meets the neck just under its
    # lip, arching up between them; at the front, the groove 2.5 cm down; w goes 0 at the front to 1 at the back)
    w = (1 - np.cos(th)) / 2; drop = DROP - (DROP - 0.006) * w
    yj = max(1.415, ylip - drop)
    rnj = neck.get(min(ys, key=lambda y: abs(y - yj))) or 0.05
    # from the lip to the neck, 6 steps: sagging into the groove at the front, arching into a roll at the back
    rl, yl = prof[-1]; rc, yc = 0.5 * (rl + rnj), (1 - w) * (min(yl, yj) - 0.004) + w * (max(yl, yj) + 0.008)
    for i in range(1, 7):
        u = i / 6; prof.append(((1 - u) ** 2 * rl + 2 * u * (1 - u) * rc + u ** 2 * (rnj - 0.002), (1 - u) ** 2 * yl + 2 * u * (1 - u) * yc + u ** 2 * yj))
    profiles.append((th, prof))
ok = [p for p in profiles if p]; print('angles with a hood wall', len(ok), 'of', NT)
# resample each profile to K points by length, then join neighbours into a band (missing angles: from their neighbours)
K = 24
def resample(prof):
    a = np.array(prof); d = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]; t = np.linspace(0, d[-1], K)
    return np.c_[np.interp(t, d, a[:, 0]), np.interp(t, d, a[:, 1])]
R = [resample(p[1]) if p else None for p in profiles]
for b in range(NT):
    if R[b] is None:
        l = next(R[(b - k) % NT] for k in range(1, NT) if R[(b - k) % NT] is not None); r = next(R[(b + k) % NT] for k in range(1, NT) if R[(b + k) % NT] is not None)
        R[b] = 0.5 * (l + r)
R = np.array(R)
for k in range(2): R = (np.roll(R, 1, 0) + 2 * R + np.roll(R, -1, 0)) / 4          # (smoothed round the neck)
th = (np.arange(NT) + 0.5) / NT * 2 * np.pi
V = np.array([c0 + np.array([np.cos(th[b]) * R[b, i, 0], R[b, i, 1], np.sin(th[b]) * R[b, i, 0]]) for b in range(NT) for i in range(K)])
idx = []
for b in range(NT):
    b2 = (b + 1) % NT
    for i in range(K - 1): a, bb, cc, dd = b * K + i, b2 * K + i, b2 * K + i + 1, b * K + i + 1; idx += [[a, dd, bb], [bb, dd, cc]]
idx = np.array(idx)
f = np.cross(V[idx[:, 1]] - V[idx[:, 0]], V[idx[:, 2]] - V[idx[:, 0]])
# facing the neck (inward): flip if the faces point away from the axis on average
cen = V[idx].mean(1); out = cen - c0; out[:, 1] = 0
if (f * out).sum(1).mean() > 0: idx = idx[:, [0, 2, 1]]; f = -f
Nn = np.zeros_like(V)
for k in range(3): np.add.at(Nn, idx[:, k], f)
Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
# UVs in metres of fabric over the patch's size (PATCH m a tile; the material mirrors it): round the neck, and down the profile
PATCH = 0.076
Vg = V.reshape(NT, K, 3); along = np.r_[np.zeros((1, K)), np.cumsum(np.linalg.norm(np.diff(np.r_[Vg, Vg[:1]], axis=0), axis=2), 0)][:NT]
down = np.c_[np.zeros((NT, 1)), np.cumsum(np.linalg.norm(np.diff(Vg, axis=1), axis=2), 1)]
UV = np.c_[along.ravel(), down.ravel()] / PATCH
# weights: each point from the nearest of the hood's vertices (top part) or the neck's (from the lip down: blended)
Wd = []
for b in range(NT):
    for i in range(K):
        p = V[b * K + i]; _, ib = kB.query(p); _, ih = kH.query(p); u = max(0.0, (i - (K - 7)) / 6)
        Wd.append((1 - u) * dense(B, ib) + u * dense(H, ih))
Wd = np.array(Wd); Jt = np.argsort(-Wd, 1)[:, :4]; Wt = np.take_along_axis(Wd, Jt, 1); Wt /= Wt.sum(1, keepdims=True)
np.savez('lining.npz', P=V.astype(np.float32), N=Nn.astype(np.float32), UV=UV.astype(np.float32), J=Jt.astype(np.uint16), W=Wt.astype(np.float32), I=idx.astype(np.uint32))
print('lining', len(V), 'verts', len(idx), 'tris; top y', R[:, 0, 1].min().round(3), R[:, 0, 1].max().round(3), 'bottom y', R[:, -1, 1].min().round(3), R[:, -1, 1].max().round(3))
