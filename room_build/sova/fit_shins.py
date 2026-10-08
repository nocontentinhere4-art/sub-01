"""Seated: the Sims performers tuck their feet back under the seat (ankles 10-16 cm behind the knees); on our chair the
calves then go into its front and base. Per frame and side, where the ankle is more than `back` (3 cm, the Mixamo
seated idle's 2.4 cm) behind the knee along his forward direction, the shin turns about the knee (axis: the thigh x shin
normal) until it is exactly that far back; the foot keeps its world orientation. Nothing changes where the shin is
already forward of that. Rewrites the clip JSON (rot, shins_fit_deg). python3 -I fit_shins.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
from retarget import m2q
from s4skel import qmul, qnorm, qrot
qinv = lambda q: q * np.array([-1, -1, -1, 1.])
rotq = lambda m: m2q(m[..., :3, :3] / np.linalg.norm(m[..., :3, 0], axis=-1)[..., None, None])
BACK = 0.03
B = Body(sys.argv[1], vstep=64)
for f in sys.argv[2:]:
    c = json.load(open(f)); Wj, wm = B.joints(c); n = c['frames']; rep = {}
    qh = rotq(wm('mixamorig:Hips')); fwd = qrot(qh, np.array([0, 0, 1.])); fwd[:, 1] = 0; fwd /= np.linalg.norm(fwd, axis=1, keepdims=True)
    for S in ('Left', 'Right'):
        Mu, Ml, Mf = (wm(f'mixamorig:{S}{b}') for b in ('UpLeg', 'Leg', 'Foot'))
        hip, knee, ank = Mu[:, :3, 3], Ml[:, :3, 3], Mf[:, :3, 3]
        th, sh = knee - hip, ank - knee; L = np.linalg.norm(sh, axis=1)
        ax = np.cross(th, sh); ax /= np.linalg.norm(ax, axis=1, keepdims=True)
        back = -np.einsum('ni,ni->n', sh, fwd)                                  # how far the ankle is behind the knee
        ang = np.zeros(n)
        for i in np.where(back > BACK)[0]:                                       # solve the turn about ax for back == BACK
            lo, hi_ = 0.0, np.pi / 2; s0 = sh[i]
            def b(t):
                q = np.concatenate([ax[i] * np.sin(t / 2), [np.cos(t / 2)]]); return -qrot(q[None], s0[None])[0] @ fwd[i]
            sgn = 1.0 if b(0.05) < b(0) else -1.0
            for _ in range(40):
                mid = (lo + hi_) / 2
                if b(sgn * mid) > BACK: lo = mid
                else: hi_ = mid
            ang[i] = sgn * (lo + hi_) / 2
        k = 5; ang = np.convolve(np.pad(ang, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
        dq = np.concatenate([ax * np.sin(ang / 2)[:, None], np.cos(ang / 2)[:, None]], 1)
        qu, ql, qf = rotq(Mu), rotq(Ml), rotq(Mf)
        ql2 = qnorm(qmul(dq, ql))
        for b_, new in ((f'mixamorig:{S}Leg', qnorm(qmul(qinv(qu), ql2))), (f'mixamorig:{S}Foot', qnorm(qmul(qinv(ql2), qf)))):
            new = np.where((np.abs(ang) > 1e-6)[:, None], new, np.array(c['rot'][b_]))
            for i in range(1, n):
                if np.dot(new[i], new[i - 1]) < 0: new[i] = -new[i]
            c['rot'][b_] = new.round(6).tolist()
        rep[S] = dict(back_before_cm=round(float(back.max() * 100), 1), turn_deg_max=round(float(np.degrees(np.abs(ang).max())), 1), frames=int((np.abs(ang) > 1e-3).sum()))
    c['shins_fit'] = rep; json.dump(c, open(f, 'w')); print(c['set'], rep, flush=True)
