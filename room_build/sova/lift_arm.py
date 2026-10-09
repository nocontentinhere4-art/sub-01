"""bed_phone_lift v2, after refit_lift.py: the phone arm lowered by his side sinks deeper than his back (up to 3.3 cm
under the torso's resting level). On those frames only the wrist is lifted (two-bone IK, the hand keeps its turn, the
phone with it) until the arm lies no lower than the torso, eased over ~0.3 s; then the hand is cleared out of his
torso (fit_hands.clear). Fingers untouched. python3 -I lift_arm.py <char.glb decoded> <clip.json in/out>"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
import fit_hands
B = Body(sys.argv[1], vstep=2); c = json.load(open(sys.argv[2])); n = c['frames']; side = 'Left'
arm = np.isin(B.bone, [side + 'Arm', side + 'ForeArm', side + 'Hand'])
def lows():
    W, _ = B.joints(c); fr = list(range(0, n, 2)); t, a = [], []
    for f in fr:
        p, _ = B.skin(W, f); t.append(p[B.reg == 'torso'][:, 1].min()); a.append(p[arm][:, 1].min())
    return np.interp(np.arange(n), fr, t), np.interp(np.arange(n), fr, a)
T, A = lows(); plane = T.min(); before = float(plane - A.min())
for it in range(3):
    need = np.maximum(0.0, plane - A + 0.002)
    if need.max() < 1e-3: break
    k = 5; amt = np.convolve(np.pad(fit_hands.smooth_max(need, k), k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    fit_hands.apply(B, c, side, np.outer(amt, [0, 1, 0])); T, A = lows()
after = float(plane - A.min())
h = c['hand']; c['hand'] = None; clear = fit_hands.clear(B, c); c['hand'] = h
c['arm_lift'] = dict(below_torso_cm_before=round(before * 100, 1), after=round(after * 100, 1), clear=clear)
json.dump(c, open(sys.argv[2], 'w')); print(c['arm_lift'], flush=True)
