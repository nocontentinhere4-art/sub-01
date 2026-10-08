"""Hands, measured per frame on our character: are the fingers and wrists anatomically plausible?
python3 -I hand_qa.py <char.glb (decoded)> <clip.glb | clip.json>...  -> a JSON line per clip (and <clip>.frames.json with -f)
Clip GLBs go through kimodo_g12/exp.mjs (any GLB the page loads: mh_mx, desk/, bed/). Per hand, over the clip:
  - side bend: PIP/DIP joints are hinges; the angle of a segment out of the plane of its parent segment and the palm's
    flexion direction (degrees; a real finger ~0-5). MCP: spread (abduction) in the palm plane off the rest pose (real ±20).
  - twist: each finger bone's roll about its own axis, off the rest pose (real ~0; >15 reads as a twisted finger).
  - wrist (hand vs forearm, off the rest pose): roll about the hand axis (pronation/supination belongs in the forearm,
    a roll here wrings the wrist), flexion/extension (real ±70) and radial/ulnar deviation (real -30/+20), and the
    forearm's roll vs the upper arm (real ±80-90).
  - speed: fingers' and wrist's angular speed (deg/s), the 95th percentile and the max."""
import json, sys, os, subprocess, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body

H = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(H, '..', 'kimodo_g12', 'exp.mjs')
FING = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')

def load_clip(path, fps=30):
    if path.endswith('.json'): return json.load(open(path))
    out = tempfile.mktemp(suffix='.json'); subprocess.run(['node', EXP, path, out], check=True, capture_output=True)
    j = json.load(open(out)); os.remove(out); N = j['nodes']; a = j['anims'][0]
    T = max(max(c['t']) for c in a['ch']); n = int(round(T * fps)) + 1; tt = np.arange(n) / fps; rot, hips = {}, None
    for c in a['ch']:
        nm = N[c['node']]['name']; t = np.array(c['t']); k = 4 if c['path'] == 'rotation' else 3
        if c['path'] not in ('rotation', 'translation'): continue
        v = np.array(c['v']).reshape(-1, k)
        if k == 4:
            for i in range(1, len(v)):
                if np.dot(v[i], v[i - 1]) < 0: v[i] = -v[i]
        r = np.stack([np.interp(tt, t, v[:, d]) for d in range(k)], 1)
        if k == 4: rot[nm] = (r / np.linalg.norm(r, axis=1, keepdims=True)).tolist()
        elif nm == 'mixamorig:Hips': hips = r.tolist()
    if hips is None: hips = [[0, 0, 0]] * n
    return dict(name=a.get('name') or os.path.basename(path), fps=fps, frames=n, rot=rot, hips=hips)

def ang(R):
    return np.degrees(np.arccos(np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1)))

def swing_twist(D, axis):
    """D [n,3,3] rotations, axis (3,) unit in the same frame -> twist angle about axis (deg, signed), swing rotvec [n,3]"""
    from scipy.spatial.transform import Rotation as Rot
    q = Rot.from_matrix(D).as_quat()                           # xyzw
    p = (q[:, :3] @ axis)[:, None] * axis; tw = np.concatenate([p, q[:, 3:]], 1)
    tw /= np.linalg.norm(tw, axis=1, keepdims=True) + 1e-12
    tw[tw[:, 3] < 0] *= -1
    twist = 2 * np.degrees(np.arctan2(tw[:, :3] @ axis, tw[:, 3]))
    sw = (Rot.from_quat(q) * Rot.from_quat(tw).inv()).as_rotvec()
    return twist, np.degrees(sw)

def stats(x):
    x = np.abs(np.asarray(x)); return [round(float(np.median(x)), 1), round(float(np.percentile(x, 95)), 1), round(float(x.max()), 1)]

def hand_metrics(B, c, side):
    W, _ = B.joints(c); jn = B.jn; I = {n.split(':')[1]: i for i, n in enumerate(jn)}; fps = c['fps']
    rest = dict(frames=1, rot={}, hips=[list(B.M.lt[B.M.idx['mixamorig:Hips']])]); W0, _ = B.joints(rest)
    R = W[:, :, :3, :3]; P = W[:, :, :3, 3]; R0 = W0[0, :, :3, :3]; P0 = W0[0, :, :3, 3]
    R = R / np.linalg.norm(R, axis=-2, keepdims=True); R0 = R0 / np.linalg.norm(R0, axis=-2, keepdims=True)  # scale out
    h = I[side + 'Hand']; fa = I[side + 'ForeArm']; ua = I[side + 'Arm']
    def local(i, p):                                           # rotation of i in its parent's frame, delta off rest
        L = np.einsum('nji,njk->nik', R[:, p], R[:, i]); L0 = R0[p].T @ R0[i]; return np.einsum('ji,njk->nik', L0, L)
    def axis_in(i, child):                                     # the bone's direction in its own rest frame
        v = R0[i].T @ (P0[child] - P0[i]); return v / np.linalg.norm(v)
    # palm frame (rest, in the hand's frame): a = wrist -> middle knuckle, n = palm normal, l = across the palm
    a = axis_in(h, I[side + 'HandMiddle1'])
    n = R0[h].T @ np.cross(P0[I[side + 'HandIndex1']] - P0[h], P0[I[side + 'HandPinky1']] - P0[h]); n /= np.linalg.norm(n)
    n -= (n @ a) * a; n /= np.linalg.norm(n); l = np.cross(a, n)
    out = {}
    # wrist: hand vs forearm off rest, in the hand's rest frame
    Dw = local(h, fa); tw, sw = swing_twist(Dw, a)
    out['wrist_roll_deg'] = stats(tw); out['wrist_flex_deg'] = stats(sw @ l); out['wrist_dev_deg'] = stats(sw @ n)
    Df = local(fa, ua); twf, _ = swing_twist(Df, axis_in(fa, h)); out['forearm_roll_deg'] = stats(twf)
    out['wrist_speed_dps'] = stats(ang(np.einsum('nji,njk->nik', Dw[:-1], Dw[1:])) * fps)[1:]
    side_b, spread, twist, speed, per = [], [], [], [], {}
    nw = np.einsum('nij,j->ni', R[:, h], n); lw = np.einsum('nij,j->ni', R[:, h], l)          # palm normal / lateral, world
    for f in FING:
        b = [I[f'{side}Hand{f}{k}'] for k in range(1, 5)]; s = [P[:, b[k + 1]] - P[:, b[k]] for k in range(3)]
        s = [v / np.linalg.norm(v, axis=1, keepdims=True) for v in s]
        fb = []
        for k in (1, 2):                                       # PIP, DIP: out of the hinge plane
            hx = lw - np.sum(lw * s[k - 1], 1, keepdims=True) * s[k - 1]; hx /= np.linalg.norm(hx, axis=1, keepdims=True)
            if f == 'Thumb':                                   # the thumb's hinge: across its own first segment's flexion
                hx = np.cross(s[k - 1], nw); hx /= np.linalg.norm(hx, axis=1, keepdims=True); hx = np.cross(hx, s[k - 1])
            fb.append(np.degrees(np.arcsin(np.clip(np.sum(s[k] * hx, 1), -1, 1))))
        # rest baseline of the same measure (Mixamo's rest fingers are not perfectly planar)
        s0 = [(P0[b[k + 1]] - P0[b[k]]) / np.linalg.norm(P0[b[k + 1]] - P0[b[k]]) for k in range(3)]
        base = []
        for k in (1, 2):
            l0 = R0[h] @ l; n0 = R0[h] @ n; hx = l0 - (l0 @ s0[k - 1]) * s0[k - 1]; hx /= np.linalg.norm(hx)
            if f == 'Thumb': hx = np.cross(s0[k - 1], n0); hx /= np.linalg.norm(hx); hx = np.cross(hx, s0[k - 1])
            base.append(np.degrees(np.arcsin(np.clip(s0[k] @ hx, -1, 1))))
        fb = [fb[0] - base[0], fb[1] - base[1]]; side_b += [np.abs(fb[0]), np.abs(fb[1])]
        if f != 'Thumb':                                       # MCP spread in the palm plane, off rest
            v = np.einsum('nji,nj->ni', R[:, h], s[0]); v0 = R0[h].T @ s0[0]
            sp = np.degrees(np.arctan2(v @ l, v @ a)) - np.degrees(np.arctan2(v0 @ l, v0 @ a)); spread.append(np.abs(sp))
        tws = []
        for k in range(3):
            par = h if k == 0 else b[k - 1]; D = local(b[k], par); t, _ = swing_twist(D, axis_in(b[k], b[k + 1])); tws.append(np.abs(t))
            speed.append(ang(np.einsum('nji,njk->nik', D[:-1], D[1:])) * fps)
        twist += tws
        per[f] = dict(side_bend_deg=stats(np.maximum(np.abs(fb[0]), np.abs(fb[1]))), twist_deg=stats(np.max(tws, 0)),
                      spread_deg=stats(spread[-1]) if f != 'Thumb' else None)
    out['finger_side_bend_deg'] = stats(np.max(side_b, 0)); out['finger_spread_deg'] = stats(np.max(spread, 0))
    out['finger_twist_deg'] = stats(np.max(twist, 0)); out['finger_speed_dps'] = stats(np.max(speed, 0))[1:]
    out['per_finger'] = per
    return out

if __name__ == '__main__':
    B = Body(sys.argv[1], vstep=8)
    for f in sys.argv[2:]:
        c = load_clip(f); r = dict(clip=os.path.basename(f), frames=c['frames'])
        for side in ('Left', 'Right'): r[side] = hand_metrics(B, c, side)
        print(json.dumps(r), flush=True)
