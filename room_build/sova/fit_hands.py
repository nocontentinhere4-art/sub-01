"""Resting hands out of his body (the Sims body is slimmer than his hoodie): per frame, the hand's deepest vertex inside
his torso / head / legs (measure.py's test: nearest body vertex and its normal); where it is more than 5 mm in, the wrist
moves out along that normal by the depth + 5 mm (two-bone IK on Arm -> ForeArm, the hand keeps its world orientation),
smoothed over 0.3 s; nothing moves where the hand is clear. Two passes. Rewrites the clip JSON (rot, hands_fit_cm).
python3 -I fit_hands.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
from retarget import q2m, m2q
from s4skel import qmul, qnorm
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kimodo_g12'))
from rt import two_bone, qbetween

qinv = lambda q: q * np.array([-1, -1, -1, 1.])
def rotq(m): return m2q(m[..., :3, :3] / np.linalg.norm(m[..., :3, 0], axis=-1)[..., None, None])

def depth_track(B, c, side, step=2):
    Wj, wm = B.joints(c); n = c['frames']; fr = list(range(0, n, step)); D, N = [], []
    other = 'Right' if side == 'Left' else 'Left'
    for f in fr:
        p, nn = B.skin(Wj, f)
        body = np.isin(B.reg, ['torso', 'head', 'legs', other + 'Arm']); tree = cKDTree(p[body]); hv = p[B.reg == side + 'Hand']   # the other arm too (crossed arms)
        d, i = tree.query(hv, distance_upper_bound=0.10); ok = np.isfinite(d)
        q = p[body][i[ok]]; qn = nn[body][i[ok]]; dep = -np.einsum('ij,ij->i', hv[ok] - q, qn)
        m = dep > 0.005
        if m.any():
            w = dep[m]; nrm = (qn[m] * w[:, None]).sum(0); D.append(dep.max()); N.append(nrm / np.linalg.norm(nrm))
        else: D.append(0.0); N.append(np.zeros(3))
    D = np.interp(np.arange(n), fr, D); N = np.stack([np.interp(np.arange(n), fr, np.array(N)[:, k]) for k in range(3)], 1)
    return D, N

def gap_track(B, c, side, step=2, regions=('torso', 'head', 'legs'), other_arm=True):
    """per frame: the hand's (fingers too) nearest signed distance to his body (+ outside, - inside), the body normal
    there, and the bone that skin follows; the other arm counts as body (crossed arms)"""
    Wj, wm = B.joints(c); n = c['frames']; fr = list(range(0, n, step)); G, N, R = [], [], []
    other = 'Right' if side == 'Left' else 'Left'
    reg = list(regions) + ([other + 'Arm'] if other_arm else [])
    body = np.isin(B.reg, reg)
    for f in fr:
        p, nn = B.skin(Wj, f)
        tree = cKDTree(p[body]); hv = p[B.reg == side + 'Hand']
        d, i = tree.query(hv); q = p[body][i]; qn = nn[body][i]; s = np.einsum('ij,ij->i', hv - q, qn)
        s = np.where(d > 0.03, np.maximum(s, d), s)          # far from the surface: the distance, not the plane
        k = s.argmin(); G.append(s[k]); N.append(qn[k]); R.append(B.bone[body][i[k]])
    G = np.interp(np.arange(n), fr, G); N = np.stack([np.interp(np.arange(n), fr, np.array(N)[:, k]) for k in range(3)], 1)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    R = [R[min(range(len(fr)), key=lambda j: abs(fr[j] - t))] for t in range(n)]
    return G, N, R

def touch(B, c, side, contact, gap=0.0025, near=0.005):
    """frames where the hand should touch him (contact: bool [n]): where it is more than `near` off, the wrist moves
    along the body normal until its nearest point is `gap` off; smoothed, two passes. Returns gap before/after (cm)"""
    G0, _, _ = gap_track(B, c, side)
    for it in range(3):
        G, N, _ = gap_track(B, c, side) if it else (G0, *gap_track(B, c, side)[1:])
        need = np.where(contact & (G > near), G - gap, 0.0) + np.where(G < 0, G - gap, 0.0); k = 4   # and nothing inside
        amt = np.convolve(np.pad(need, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
        if np.abs(amt).max() < 1e-4: break
        apply(B, c, side, -N * amt[:, None])
    G1, _, _ = gap_track(B, c, side)
    m = contact.astype(bool)
    return dict(frames=int(m.sum()), gap_before_cm=[round(float(G0[m].min() * 100), 1), round(float(G0[m].max() * 100), 1)] if m.any() else None,
                gap_after_cm=[round(float(G1[m].min() * 100), 1), round(float(G1[m].max() * 100), 1)] if m.any() else None)

def smooth_max(x, k):
    pad = np.pad(x, k, mode='edge'); mx = np.array([pad[i:i + 2 * k + 1].max() for i in range(len(x))])
    return np.convolve(np.pad(mx, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')

def apply(B, c, side, off):
    Wj, wm = B.joints(c); n = c['frames']
    nm = lambda b: f'mixamorig:{side}{b}'
    Ms, Ma, Mf, Mh = (wm(nm(b)) for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand'))
    Pa, Pb, Pc = Ma[:, :3, 3], Mf[:, :3, 3], Mh[:, :3, 3]
    l1 = np.linalg.norm(Pb - Pa, axis=1).mean(); l2 = np.linalg.norm(Pc - Pb, axis=1).mean()
    goal = Pc + off
    Pb2, goal = two_bone(Pa, Pb, Pc, goal, l1, l2)
    qs, qa, qf, qh = rotq(Ms), rotq(Ma), rotq(Mf), rotq(Mh)
    q1 = qbetween(Pb - Pa, Pb2 - Pa); qa2 = qnorm(qmul(q1, qa))
    from s4skel import qrot
    q2 = qbetween(qrot(q1, Pc - Pb), goal - Pb2); qf2 = qnorm(qmul(q2, qmul(q1, qf)))
    move = np.linalg.norm(off, axis=1) > 1e-5
    for b, new in (('Arm', qnorm(qmul(qinv(qs), qa2))), ('ForeArm', qnorm(qmul(qinv(qa2), qf2))), ('Hand', qnorm(qmul(qinv(qf2), qh)))):
        old = np.array(c['rot'][nm(b)]); out = np.where(move[:, None], new, old)
        for i in range(1, n):
            if np.dot(out[i], out[i - 1]) < 0: out[i] = -out[i]
        c['rot'][nm(b)] = out.round(6).tolist()

def clear(B, c):
    """both resting hands out of his body (not the phone hand); rewrites c['rot'], returns the report"""
    rep = {}
    for side in ('Left', 'Right'):
        if c.get('hand') == side: continue                       # the phone hand is the grip; it is not resting
        D0, _ = depth_track(B, c, side); tot = np.zeros((c['frames'], 3))
        for it in range(2):
            D, N = depth_track(B, c, side) if it else (D0, depth_track(B, c, side)[1])
            need = np.where(D > 0.005, D + 0.005, 0.0); k = 5
            amt = smooth_max(need, k); nrm = np.stack([np.convolve(np.pad(N[:, j], k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid') for j in range(3)], 1)
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9); off = nrm * amt[:, None]
            if amt.max() < 1e-4: break
            apply(B, c, side, off); tot += off
        D1, _ = depth_track(B, c, side)
        rep[side] = dict(before_cm=round(float(D0.max() * 100), 1), after_cm=round(float(D1.max() * 100), 1),
                         moved_cm=round(float(np.linalg.norm(tot, axis=1).max() * 100), 1), frames_moved=int((np.linalg.norm(tot, axis=1) > 1e-4).sum()))
    return rep

if __name__ == '__main__':
    B = Body(sys.argv[1], vstep=2)
    for f in sys.argv[2:]:
        c = json.load(open(f)); c['hands_fit_cm'] = clear(B, c); json.dump(c, open(f, 'w')); print(c['set'], c['hands_fit_cm'], flush=True)
