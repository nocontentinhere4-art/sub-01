"""Seated: resting hands down ON his thighs. The Sims performers' hands hover over their (slimmer) laps; on him they
float 10-12 cm over the trousers. Per frame and hand: where the hand rests near a thigh (the nearest upward-facing
trouser vertex, across the floor from the palm, within `reach`), the wrist moves across to over it and down until the
hand's lowest vertex is `gap` (3 mm) over it, two-bone IK, the hand keeps its world orientation,
smoothed over 0.3 s. A raised hand (gesture) is left alone. Run before kimodo/mx_fit.py (which carries the wrists with
him onto our seat). Rewrites the clip JSON (rot, rest_fit). python3 -I fit_rest.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
from fit_hands import apply, smooth_max
GAP, REACH = 0.003, 0.15
FORCE = os.environ.get('REST_FORCE') == '1'      # every frame resting (idle clips: no gesture to keep)
PASSES = int(os.environ.get('REST_PASSES', '5'))
REST_FWD = float(os.environ.get('REST_FWD', '-9'))  # rest only on thigh tops this far forward of the hip joints (m): a hand hanging by his hip goes onto the lap, not the armrest
REST_LOW = float(os.environ.get('REST_LOW', '-1'))  # a hand whose lowest point drops under this (body frame, m) rests too: by the seat's edge it meets the chair

def track(B, c, side, step=2):
    """per frame: the move that puts the hand ON the top of his thigh (the nearest trouser vertex facing up, found across
    the floor from the palm's centre): across to over it, down (or up) to its height + GAP; and whether he rests there"""
    Wj, wm = B.joints(c); n = c['frames']; fr = list(range(0, n, step)); MV, ON, G = [], [], []
    for f in fr:
        p, nn = B.skin(Wj, f)
        top = np.isin(B.bone, ['LeftUpLeg', 'RightUpLeg']) & (nn[:, 1] > 0.7) & (p[:, 2] > wm('mixamorig:' + side + 'UpLeg')[f, 2, 3] + REST_FWD); T = p[top]; hv = p[B.reg == side + 'Hand']
        ctr = hv.mean(0); d = np.linalg.norm((T - ctr)[:, [0, 2]], axis=1); k = d.argmin(); t = T[k]
        on = FORCE or (d[k] < REACH and ctr[1] - t[1] < 0.25) or hv[:, 1].min() < REST_LOW
        mv = np.array([t[0] - ctr[0], 0.0, t[2] - ctr[2]]) * 0.8
        mv[1] = t[1] + GAP - hv[:, 1].min()
        MV.append(mv if on else np.zeros(3)); ON.append(on); G.append(hv[:, 1].min() - t[1])
    MV = np.stack([np.interp(np.arange(n), fr, np.array(MV)[:, j]) for j in range(3)], 1)
    ON = np.interp(np.arange(n), fr, np.array(ON, float)) > 0.5; G = np.interp(np.arange(n), fr, G)
    return MV, ON, G

if __name__ == '__main__':
    B = Body(sys.argv[1], vstep=2)
    for f in sys.argv[2:]:
        c = json.load(open(f)); rep = {}
        for side in ('Left', 'Right'):
            MV0, ON0, G0 = track(B, c, side)
            for it in range(PASSES):
                MV, ON, G = track(B, c, side) if it else (MV0, ON0, G0)
                k = 5; mv = np.stack([np.convolve(np.pad(MV[:, j], k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid') for j in range(3)], 1)
                if np.linalg.norm(mv, axis=1).max() < 2e-3: break
                apply(B, c, side, mv)
            MV1, ON1, G1 = track(B, c, side)
            rep[side] = dict(resting_frames=int(ON0.sum()), gap_before_cm=[round(float(G0[ON0].min() * 100), 1), round(float(G0[ON0].max() * 100), 1)] if ON0.any() else None,
                             gap_after_cm=[round(float(G1[ON1].min() * 100), 1), round(float(G1[ON1].max() * 100), 1)] if ON1.any() else None,
                             left_to_move_cm=round(float(np.linalg.norm(MV1, axis=1).max() * 100), 1))
        c['rest_fit'] = rep; json.dump(c, open(f, 'w')); print(c['set'], rep, flush=True)
