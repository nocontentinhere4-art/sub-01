"""Phone at the ear (call clips): slide it off his cheek along its screen normal, in 5 mm steps, until no head
vertex is inside it on any sampled frame. Rewrites the clip JSON (props[hand].pos, phone_shift_cm).
python3 -I fit_phone.py <char.glb> <clip.json>..."""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body, mat, PH
B = Body(sys.argv[1])
for f in sys.argv[2:]:
    c = json.load(open(f)); side = c['hand']; pr = c['props'][side]
    if not pr.get('call'): continue
    Wj, wm = B.joints(c); hand = wm(f'mixamorig:{side}Hand'); fr = range(0, c['frames'], 6)
    heads = [B.skin(Wj, i)[0][B.reg == 'head'] for i in fr]
    R = np.array(pr['quat']); n_local = None
    for k in range(0, 41):
        pos = np.array(pr['pos']) - k * 0.005 * (mat(np.zeros(3), R, np.ones(3))[:3, 0])   # back off along -screen normal
        loc = mat(pos / 0.01, R, np.array([100., 100, 100]))
        hit = 0
        for i, hv in zip(fr, heads):
            inv = np.linalg.inv(hand[i] @ loc); hl = (inv[:3, :3] @ hv.T).T + inv[:3, 3]
            hit += int(np.all(np.abs(hl) < PH / 2 + 0.002, axis=1).sum())
        if hit == 0: break
    pr['pos'] = pos.tolist(); pr['phone_shift_cm'] = k * 0.5
    json.dump(c, open(f, 'w')); print(c['set'], 'shift', k * 0.5, 'cm', 'left inside' if hit else 'clear')
