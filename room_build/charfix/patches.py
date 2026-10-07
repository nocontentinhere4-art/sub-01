# v5's hood has open holes round the collar (open-edge loops of its mesh): each filled with a fan of triangles about its
# centre (a part of its own, hood_patches, in the lining's fabric, two-sided), skinned from the nearest hood vertices.
# The loop along the hood's top rim (y 1.49-1.52) is the rim itself, behind the lining: left open
from bnd import *
from scipy.spatial import cKDTree
import os, sys
B = load('v5', 'tripo_node_6bf04053-_0'); P = world_v5(B)
loops, _, _ = boundary_loops(P, B['idx']); c0 = np.array([0.0017, 0, -0.0109])
sel = [L for L in loops if 1.33 < L.mean(0)[1] < 1.56 and np.hypot(*(L.mean(0) - c0)[[0, 2]]) < 0.2 and not (L[:, 1].min() > 1.49 and len(L) > 100)]
V, I = [], []
for L in sel:
    c = L.mean(0); base = len(V); V += list(L) + [c]; n = len(L)
    for k in range(n): I.append([base + k, base + (k + 1) % n, base + n])
V = np.array(V); I = np.array(I)
f = np.cross(V[I[:, 1]] - V[I[:, 0]], V[I[:, 2]] - V[I[:, 0]]); Nn = np.zeros_like(V)
for k in range(3): np.add.at(Nn, I[:, k], f)
Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-12)
def dense(A, i):
    w = np.zeros(79)
    for j, x in zip(A['JOINTS_0'][i].astype(int), A['WEIGHTS_0'][i]): w[j] += x
    return w
kd = cKDTree(P); dd, ii = kd.query(V, 4); Wd = np.zeros((len(V), 79))
for n in range(4):
    for r in range(len(V)): Wd[r] += dense(B, ii[r, n]) / (dd[r, n] + 1e-4)
Jt = np.argsort(-Wd, 1)[:, :4]; Wt = np.take_along_axis(Wd, Jt, 1); Wt /= Wt.sum(1, keepdims=True)
UV = np.c_[V[:, 0] + V[:, 2], V[:, 1]] / 0.076
od = 'p_patches'; os.makedirs(od, exist_ok=True)
for k, a, t in (('P', V, np.float32), ('N', Nn, np.float32), ('UV', UV, np.float32), ('J', Jt, np.uint16), ('W', Wt, np.float32), ('I', I, np.uint32)): a.astype(t).tofile(f'{od}/{k}.bin')
print(len(sel), 'holes filled:', [len(L) for L in sel], len(I), 'triangles')
