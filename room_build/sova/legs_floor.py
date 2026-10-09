"""Legs no deeper than a floor: on the frames where the legs' skin goes under FLOOR (m, relative to his lowest torso
point over the clip), both thighs turn up about the pelvis's side axis just enough; smoothed (max over +-5 frames).
python3 -I legs_floor.py <char.glb decoded> <clip.json in/out> <floor m, e.g. -0.021>"""
import json, sys, os
import numpy as np
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
from fit_hands import smooth_max
B = Body(sys.argv[1], vstep=6); c = json.load(open(sys.argv[2])); FLOOR = float(sys.argv[3]); n = c['frames']
I = {j.split(':')[1]: i for i, j in enumerate(B.jn)}; legs = B.reg == 'legs'; torso = B.reg == 'torso'
def at(f): return dict(frames=1, rot={k: [v[f]] for k, v in c['rot'].items()}, hips=[c['hips'][f]])
W, _ = B.joints(c); plane = min(B.skin(W, f)[0][torso][:, 1].min() for f in range(0, n, 3))
def legs_low(f, th):
    W, _ = B.joints(at(f)); H = W[0, I['Hips'], :3, :3]; H = H / np.linalg.norm(H[:, 0]); R = H.T @ Rot.from_rotvec(np.radians(th) * H[:, 0]).as_matrix() @ H
    cc = at(f)
    for s in ('Left', 'Right'): cc['rot'][f'mixamorig:{s}UpLeg'] = [(Rot.from_matrix(R) * Rot.from_quat(c['rot'][f'mixamorig:{s}UpLeg'][f])).as_quat().tolist()]
    W2, _ = B.joints(cc); return B.skin(W2, 0)[0][legs][:, 1].min() - plane
need = np.zeros(n); sign = 0
for f in range(0, n, 2):
    if legs_low(f, 0) >= FLOOR: continue
    if not sign: sign = 1 if legs_low(f, 3) > legs_low(f, -3) else -1
    th = 0
    while th < 40 and legs_low(f, sign * th) < FLOOR: th += 1
    need[f] = th
need = smooth_max(np.maximum.accumulate(need[::-1])[::-1] * 0 + need, 5)
for f in range(n):
    if need[f] < 1e-3: continue
    W, _ = B.joints(at(f)); H = W[0, I['Hips'], :3, :3]; H = H / np.linalg.norm(H[:, 0]); R = H.T @ Rot.from_rotvec(np.radians(sign * need[f]) * H[:, 0]).as_matrix() @ H
    for s in ('Left', 'Right'): c['rot'][f'mixamorig:{s}UpLeg'][f] = (Rot.from_matrix(R) * Rot.from_quat(c['rot'][f'mixamorig:{s}UpLeg'][f])).as_quat().tolist()
c['legs_floor'] = dict(floor_m=FLOOR, frames=int((need > 1e-3).sum()), max_deg=round(float(need.max()), 1))
json.dump(c, open(sys.argv[2], 'w')); print(c['set'], c['legs_floor'], flush=True)
