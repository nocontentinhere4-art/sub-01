"""bed_phone_lift (IN BED 03 A) for OUR bed: the performer lies back ACROSS a bed with the feet on the floor, so laid
along our mattress his calves hang 31-33 cm down into it. The upper body (the phone lift) stays; the legs take
sleep_back's lying legs (each bone's median), and both thighs turn about the pelvis's side axis, per frame, until the
lowest leg joint less RAD (calf/heel) is level with his lowest torso point: the legs lie on the mattress.
python3 -I refit_lift.py <char.glb decoded> <lift clip.json> <sleep_back clip.json> <out clip.json>"""
import json, sys, os
import numpy as np
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
RAD, STEP = 0.09, 10
LEG = ['UpLeg', 'Leg', 'Foot', 'ToeBase']
B = Body(sys.argv[1], vstep=8); c = json.load(open(sys.argv[2])); sb = json.load(open(sys.argv[3])); n = c['frames']
for s in ('Left', 'Right'):
    for b in LEG:
        nm = f'mixamorig:{s}{b}'; v = np.array(sb['rot'][nm]); v *= np.sign(v @ v[0])[:, None]; m = np.median(v, 0)
        c['rot'][nm] = np.tile(m / np.linalg.norm(m), (n, 1)).tolist()
base = {s: np.array(c['rot'][f'mixamorig:{s}UpLeg']) for s in ('Left', 'Right')}
fr = list(range(0, n, STEP)) + ([n - 1] if (n - 1) % STEP else []); TH = []
jn = [j.split(':')[1] for j in B.jn]; I = {k: i for i, k in enumerate(jn)}
low_j = [I[f'{s}{b}'] for s in ('Left', 'Right') for b in ('Leg', 'Foot', 'ToeBase', 'Toe_End')]
def legs_low(cc, f):
    W, _ = B.joints(dict(cc, frames=1, rot={k: [v[f]] for k, v in cc['rot'].items()}, hips=[cc['hips'][f]]))
    return W[0, low_j, 1, 3].min() - RAD, W[0]
for f in fr:
    W, _ = B.joints(dict(c, frames=1, rot={k: [v[f]] for k, v in c['rot'].items()}, hips=[c['hips'][f]]))
    p, _ = B.skin(W, 0); T = p[B.reg == 'torso'][:, 1].min()
    Hr = W[0, I['Hips'], :3, :3] / np.linalg.norm(W[0, I['Hips'], :3, 0]); ax = Hr[:, 0] / np.linalg.norm(Hr[:, 0])   # pelvis side axis, world
    best = None
    for th in np.arange(-90, 90.5, 1.0):
        R = Hr.T @ Rot.from_rotvec(np.radians(th) * ax).as_matrix() @ Hr    # a world turn about ax, in the pelvis frame
        cc = dict(c, rot=dict(c['rot']))
        for s in ('Left', 'Right'): cc['rot'][f'mixamorig:{s}UpLeg'] = [(Rot.from_matrix(R) * Rot.from_quat(base[s][f])).as_quat().tolist()] * n
        lo, _ = legs_low(cc, f); e = abs(lo - T)
        if best is None or e < best[0]: best = (e, th)
    TH.append(best[1])
TH = np.interp(np.arange(n), fr, TH)
for f in range(n):
    W, _ = B.joints(dict(c, frames=1, rot={k: [v[f]] for k, v in c['rot'].items()}, hips=[c['hips'][f]]))
    Hr = W[0, I['Hips'], :3, :3] / np.linalg.norm(W[0, I['Hips'], :3, 0]); ax = Hr[:, 0] / np.linalg.norm(Hr[:, 0])
    R = Hr.T @ Rot.from_rotvec(np.radians(TH[f]) * ax).as_matrix() @ Hr
    for s in ('Left', 'Right'): c['rot'][f'mixamorig:{s}UpLeg'][f] = (Rot.from_matrix(R) * Rot.from_quat(base[s][f])).as_quat().tolist()
c['legs_refit'] = dict(source='sleep_back legs (median)', thigh_pitch_deg=[round(float(TH.min()), 1), round(float(TH.max()), 1)])
json.dump(c, open(sys.argv[4], 'w')); print(c['set'], c['legs_refit'], flush=True)
