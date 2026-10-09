"""The back sleeping poses for OUR bed (G14's sleep_duvet_sheet): in sleep_back, sleep_back_idle and the end of
sleep_roll_to_back his head and shoulders are propped up off the bed and his knees are up, so the duvet mounds and the
head sits ~15 cm short of the pillow (the page anchors the hips: a raised torso reaches less far along the bed).
Per frame, about the pelvis's side axis (as refit_lift.py):
  1. the spine (Spine) turns until his upper back (Spine1/Spine2/shoulders skin) lies as low as his buttocks;
  2. the neck (Neck) turns until the back of his head rests on the pillow: PILLOW m over his lowest torso point
     (the pillow's top 0.95 m in the room, the mattress 0.82 m, his back sinks 1.5 cm, the pillow gives GIVE);
  3. the knees: the legs blended toward straight by FLAT, then both thighs turn until the legs lie on the mattress.
sleep_roll_to_back: weighted in only once he is on his back (the pelvis within 25 deg of the back clip's, over 1 s).
python3 -I refit_back.py <char.glb decoded> <clip.json> <back reference clip.json> <out clip.json>"""
import json, sys, os
import numpy as np
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
GIVE = float(os.environ.get('PILLOW_GIVE', 0.02)); PILLOW = (0.95 - 0.82) + 0.015 - GIVE       # over his lowest torso point
FLAT = float(os.environ.get('FLAT', 0.7)); STEP = 6; LEGR = 0.09
SHIFT = float(os.environ.get('SHIFT', 0))   # m toward his head (the frame-0 hips->head axis), weighted in as he lies on his back: the roll ends where the back loops are placed
B = Body(sys.argv[1], vstep=6); c = json.load(open(sys.argv[2])); ref = json.load(open(sys.argv[3])); n = c['frames']
jn = [j.split(':')[1] for j in B.jn]; I = {k: i for i, k in enumerate(jn)}
upper = np.isin(B.bone, ['Spine1', 'Spine2', 'LeftShoulder', 'RightShoulder']); butt = np.isin(B.bone, ['Hips', 'Spine'])
head = np.isin(B.bone, ['Head', 'HeadTop_End'])
shin = np.isin(B.bone, ['LeftLeg', 'RightLeg', 'LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase']); thigh = np.isin(B.bone, ['LeftUpLeg', 'RightUpLeg'])
def at(cc, f): return dict(frames=1, rot={k: [v[f]] for k, v in cc['rot'].items()}, hips=[cc['hips'][f]])
def turn(cc, f, bone, th, ax):                                 # a world turn about ax at the bone, written in its local
    W, _ = B.joints(at(cc, f)); par = W[0, I[{'Spine': 'Hips', 'Neck': 'Spine2', 'LeftUpLeg': 'Hips', 'RightUpLeg': 'Hips'}[bone]], :3, :3]
    par = par / np.linalg.norm(par[:, 0]); R = par.T @ Rot.from_rotvec(np.radians(th) * ax).as_matrix() @ par
    return (Rot.from_matrix(R) * Rot.from_quat(cc['rot']['mixamorig:' + bone][f])).as_quat().tolist()
def pelvis(cc, f):
    W, _ = B.joints(at(cc, f)); H = W[0, I['Hips'], :3, :3]; return H / np.linalg.norm(H[:, 0])
# on his back? (the roll): weight by the pelvis's turn from the back clip's median pelvis
Rref = Rot.from_matrix(np.mean([pelvis(ref, f) for f in range(0, ref['frames'], 10)], 0)).as_matrix()
U, _, Vt = np.linalg.svd(Rref); Rref = U @ Vt
wts = np.array([1.0 if np.degrees(np.arccos(np.clip((np.trace(Rref.T @ pelvis(c, f)) - 1) / 2, -1, 1))) < 25 else 0.0 for f in range(n)])
k = 30; wts = np.convolve(np.pad(wts, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
# legs flatter: toward the rest (straight) local turn
rest = {nm: B.M.lq[B.M.idx[nm]] for nm in B.jn}
for s in ('Left', 'Right'):
    for b in ('UpLeg', 'Leg', 'Foot'):
        nm = f'mixamorig:{s}{b}'; q = np.array(c['rot'][nm]); r0 = rest[nm]; out = []
        for f in range(n):
            w = FLAT * wts[f]; out.append(Rot.from_quat([q[f], r0]).mean([1 - w, w]).as_quat().tolist())
        c['rot'][nm] = out
fr = [f for f in range(0, n, STEP)] + ([n - 1] if (n - 1) % STEP else []); A, Bn, L = [], [], []
def search(f, bone, cost, lo=-70, hi=70):
    best = None
    for step in (5, 1):
        rng = np.arange(lo, hi + 0.1, step) if best is None else np.arange(best[1] - 5, best[1] + 5.1, step)
        for th in rng:
            e = cost(th)
            if best is None or e < best[0]: best = (e, th)
    return best[1]
for f in fr:
    if wts[f] < 1e-3: A.append(0); Bn.append(0); L.append(0); continue
    ax = pelvis(c, f)[:, 0]
    def skin(cc): W, _ = B.joints(at(cc, f)); return B.skin(W, 0)[0]
    p = skin(c); plane = p[butt][:, 1].min()
    def c_spine(th):
        cc = dict(c, rot=dict(c['rot'])); cc['rot']['mixamorig:Spine'] = list(c['rot']['mixamorig:Spine']); cc['rot']['mixamorig:Spine'][f] = turn(c, f, 'Spine', th, ax)
        q = skin(cc); return abs(q[upper][:, 1].min() - plane) + 0.002 * abs(th)
    a = search(f, 'Spine', c_spine); A.append(a)
    c1 = dict(c, rot=dict(c['rot'])); c1['rot']['mixamorig:Spine'] = list(c['rot']['mixamorig:Spine']); c1['rot']['mixamorig:Spine'][f] = turn(c, f, 'Spine', a, ax)
    def c_neck(th):
        cc = dict(c1, rot=dict(c1['rot'])); cc['rot']['mixamorig:Neck'] = list(c1['rot']['mixamorig:Neck']); cc['rot']['mixamorig:Neck'][f] = turn(c1, f, 'Neck', th, ax)
        q = skin(cc); return abs(q[head][:, 1].min() - (plane + PILLOW)) + 0.002 * abs(th)
    b = search(f, 'Neck', c_neck, -60, 60); Bn.append(b)
    c2 = dict(c1, rot=dict(c1['rot'])); c2['rot']['mixamorig:Neck'] = list(c1['rot']['mixamorig:Neck']); c2['rot']['mixamorig:Neck'][f] = turn(c1, f, 'Neck', b, ax)
    lowj = [I[f'{s}{x}'] for s in ('Left', 'Right') for x in ('Leg', 'Foot', 'ToeBase', 'Toe_End')]
    def c_legs(th):
        cc = dict(c2, rot=dict(c2['rot']))
        for s in ('Left', 'Right'):
            nm = f'mixamorig:{s}UpLeg'; cc['rot'][nm] = list(c2['rot'][nm]); cc['rot'][nm][f] = turn(c2, f, f'{s}UpLeg', th, ax)
        q = skin(cc); lo = q[shin][:, 1].min(); th_lo = q[thigh][:, 1].min()          # calves and heels on the mattress,
        return abs(lo - (plane + 0.005)) + 5 * max(0.0, plane - 0.005 - th_lo) + 0.001 * abs(th)   # the thighs not under it
    L.append(search(f, 'UpLeg', c_legs, -60, 60))
A, Bn, L = (np.interp(np.arange(n), fr, x) * wts for x in (A, Bn, L))
for f in range(n):                                             # apply in order: spine, neck, thighs
    ax = pelvis(c, f)[:, 0]
    c['rot']['mixamorig:Spine'][f] = turn(c, f, 'Spine', A[f], ax)
    c['rot']['mixamorig:Neck'][f] = turn(c, f, 'Neck', Bn[f], ax)
    for s in ('Left', 'Right'): c['rot'][f'mixamorig:{s}UpLeg'][f] = turn(c, f, f'{s}UpLeg', L[f], ax)
if SHIFT:                                                      # he moves up the bed as he rolls onto his back
    W, _ = B.joints(at(c, 0)); u = W[0, I['Head'], :3, 3] - W[0, I['Hips'], :3, 3]; u[1] = 0; u /= np.linalg.norm(u)
    Hp = W[0, I['Hips'], :3, :3]; pw = W[0, I['Hips'], :3, 3]          # the hips translation is in its parent's frame: map u there
    par = B.joints(at(c, 0))[1]('mixamorig:Hips')[0] @ np.linalg.inv(np.array(B.M.lq[B.M.idx['mixamorig:Hips']] if False else np.eye(4)))
    h = np.array(c['hips']); M0 = B.joints(at(c, 0))[1]('mixamorig:Hips')[0]
    # the world step per unit of local translation: from two probes
    c2 = dict(at(c, 0)); c2['hips'] = [list(h[0] + [1, 0, 0])]; d1 = B.joints(c2)[0][0, I['Hips'], :3, 3] - pw
    c2['hips'] = [list(h[0] + [0, 0, 1])]; d3 = B.joints(c2)[0][0, I['Hips'], :3, 3] - pw
    c2['hips'] = [list(h[0] + [0, 1, 0])]; d2 = B.joints(c2)[0][0, I['Hips'], :3, 3] - pw
    Jm = np.stack([d1, d2, d3], 1); dl = np.linalg.solve(Jm, u * SHIFT)
    c['hips'] = (h + np.outer(wts, dl)).tolist()
c['back_w'] = np.round(wts, 3).tolist()
c['back_refit'] = dict(shift_m=SHIFT, spine_deg=[round(float(A.min()), 1), round(float(A.max()), 1)], neck_deg=[round(float(Bn.min()), 1), round(float(Bn.max()), 1)],
                       thigh_deg=[round(float(L.min()), 1), round(float(L.max()), 1)], legs_flat=FLAT, on_back_frames=int((wts > 0.5).sum()), pillow_over_back_m=round(PILLOW, 3))
json.dump(c, open(sys.argv[4], 'w')); print(c['set'], c['back_refit'], flush=True)
