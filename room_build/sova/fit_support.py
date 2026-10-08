"""Lying / sitting-up clips: one fixed mattress. The retargeted body is thicker than the Sims one, so his lowest torso
point sits at a different height lying back (hood, shoulder blades) and sitting up (buttocks), 12 cm apart in set_5.
Fit: lower the hips each frame by (support(t) - lowest support), smoothed over 0.5 s, so that whichever part he rests
on touches the same plane. Rewrites the clip JSON (hips, support_fit_cm). python3 -I fit_support.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
B = Body(sys.argv[1], vstep=4)
for f in sys.argv[2:]:
    c = json.load(open(f)); Wj, wm = B.joints(c); n = c['frames']
    fr = np.arange(0, n, 3); sup = np.array([B.skin(Wj, i)[0][B.reg == 'torso'][:, 1].min() for i in fr])
    s = np.interp(np.arange(n), fr, sup); k = 15
    s = np.convolve(np.pad(s, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    off = s.min() - s                                   # <= 0: lower him where he rests higher than the lowest support
    h = np.array(c['hips']); h[:, 1] += off / 0.01; c['hips'] = h.round(4).tolist()
    c['support_fit_cm'] = [round(float(off.min() * 100), 1), 0.0]
    json.dump(c, open(f, 'w')); print(c['set'], 'hips lowered by up to', round(-off.min() * 100, 1), 'cm')
