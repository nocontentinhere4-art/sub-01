"""Seated: resting hands down ON his thighs. The Sims performers' hands hover over their (slimmer) laps; on him they
float 10-12 cm over the trousers. Per frame and hand: where the hand is over a thigh (the nearest thigh vertex within
`reach` and its normal pointing up), the wrist moves along that normal until the hand's lowest vertex is `gap` (3 mm)
off the trouser surface (down if it floats, out if it is inside), two-bone IK, the hand keeps its world orientation,
smoothed over 0.3 s. A raised hand (gesture) is left alone. Run before kimodo/mx_fit.py (which carries the wrists with
him onto our seat). Rewrites the clip JSON (rot, rest_fit). python3 -I fit_rest.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
from fit_hands import apply, smooth_max
GAP, REACH = 0.003, 0.15

def track(B, c, side, step=2):
    Wj, wm = B.joints(c); n = c['frames']; fr = list(range(0, n, step)); G, N, ON = [], [], []
    for f in fr:
        p, nn = B.skin(Wj, f)
        legs = B.reg == 'legs'; tree = cKDTree(p[legs]); hv = p[B.reg == side + 'Hand']
        d, i = tree.query(hv); q = p[legs][i]; qn = nn[legs][i]
        s = np.einsum('ij,ij->i', hv - q, qn)                 # signed: + over the trousers, - inside
        k = s.argmin(); on = d[k] < REACH and qn[k, 1] > 0.5
        G.append(s[k]); N.append(qn[k]); ON.append(on)
    G = np.interp(np.arange(n), fr, G); ON = np.interp(np.arange(n), fr, np.array(ON, float)) > 0.5
    N = np.stack([np.interp(np.arange(n), fr, np.array(N)[:, j]) for j in range(3)], 1)
    return G, N, ON

if __name__ == '__main__':
    B = Body(sys.argv[1], vstep=2)
    for f in sys.argv[2:]:
        c = json.load(open(f)); rep = {}
        for side in ('Left', 'Right'):
            G0, N, ON = track(B, c, side)
            for it in range(2):
                G, N, ON = track(B, c, side) if it else (G0, N, ON)
                mv = np.where(ON, G - GAP, 0.0)                    # + : move down onto the thigh, - : out of it
                k = 5; mv = np.convolve(np.pad(mv, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
                nrm = np.stack([np.convolve(np.pad(N[:, j], k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid') for j in range(3)], 1)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
                if np.abs(mv).max() < 1e-3: break
                apply(B, c, side, -nrm * mv[:, None])
            G1, _, ON1 = track(B, c, side)
            rep[side] = dict(resting_frames=int(ON.sum()), gap_before_cm=[round(float(G0[ON].min() * 100), 1), round(float(G0[ON].max() * 100), 1)] if ON.any() else None,
                             gap_after_cm=[round(float(G1[ON1].min() * 100), 1), round(float(G1[ON1].max() * 100), 1)] if ON1.any() else None)
        c['rest_fit'] = rep; json.dump(c, open(f, 'w')); print(c['set'], rep, flush=True)
