"""Natural hands on a baked clip GLB (COORD, after the owner's "twisted hands"): the Sims fingers are not retargeted.
python3 -I fix_hands_pose.py <in.glb> <out.glb> [phone hand: Left|Right|-]
  - fingers: Mixamo's relaxed seated hand (web/room/mh_mx/room_seated_idle, each bone's median over the clip), plus a
    slight curl from the clip: CURL x the clip's own flexion (about the bone's X, its curl axis) off its median, clamped
    to +-CURL_MAX. The thumb takes the relaxed pose only.
  - the phone hand: room_phone's grip (same side), still: no curl from the clip, and its wrist is left as baked (the
    phone rides on it).
  - wrists (hand vs forearm, off the rest pose): roll about the hand axis, flexion and deviation clamped
    (WRIST_ROLL, WRIST_FLEX, WRIST_DEV degrees); the forearm's roll vs the upper arm clamped to FOREARM_ROLL.
Everything else in the clip is unchanged. Writes via kimodo_g12/writeclip.mjs (animation-only, 30 fps, linear)."""
import json, sys, os, subprocess, tempfile
import numpy as np
from scipy.spatial.transform import Rotation as Rot
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, '..', '..')
EXP = os.path.join(H, '..', 'kimodo_g12', 'exp.mjs'); WRITE = os.path.join(H, '..', 'kimodo_g12', 'writeclip.mjs')
REF = os.path.join(R, 'web', 'room', 'mh_mx', 'room_seated_idle.glb'); GRIP = os.path.join(R, 'web', 'room', 'mh_mx', 'room_phone.glb')
E = lambda k, d: float(os.environ.get(k, d))
CURL, CURL_MAX = E('CURL', 0.3), E('CURL_MAX', 15)
WR, WF, WD, FR = E('WRIST_ROLL', 45), E('WRIST_FLEX', 60), E('WRIST_DEV', 40), E('FOREARM_ROLL', 80)
FING = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')

def exp(path):
    out = tempfile.mktemp(suffix='.json'); subprocess.run(['node', EXP, path, out], check=True, capture_output=True)
    j = json.load(open(out)); os.remove(out); return j

def tracks(j, fps=30):
    """node index -> {path: [F, k]} resampled to fps; F"""
    a = j['anims'][0]; T = max(max(c['t']) for c in a['ch']); F = int(round(T * fps)) + 1; tt = np.arange(F) / fps; o = {}
    for c in a['ch']:
        if c['path'] not in ('rotation', 'translation'): continue
        k = 4 if c['path'] == 'rotation' else 3; v = np.array(c['v'], float).reshape(-1, k); t = np.array(c['t'])
        if k == 4:
            for i in range(1, len(v)):
                if v[i] @ v[i - 1] < 0: v[i] = -v[i]
        r = np.stack([np.interp(tt, t, v[:, d]) for d in range(k)], 1)
        if k == 4: r /= np.linalg.norm(r, axis=1, keepdims=True)
        o.setdefault(c['node'], {})[c['path']] = r
    return o, F

def medians(path):
    j = exp(path); tr, _ = tracks(j); N = j['nodes']; o = {}
    for i, d in tr.items():
        if 'rotation' in d:
            v = d['rotation']; m = np.median(v, 0); o[N[i]['name']] = m / np.linalg.norm(m)
    return o

def swing_twist(q, axis):                                      # q [F,4] xyzw, axis (3,) -> twist deg, swing rotvec deg
    p = (q[:, :3] @ axis)[:, None] * axis; tw = np.concatenate([p, q[:, 3:]], 1); tw /= np.linalg.norm(tw, axis=1, keepdims=True) + 1e-12
    tw[tw[:, 3] < 0] *= -1; twist = 2 * np.degrees(np.arctan2(tw[:, :3] @ axis, tw[:, 3]))
    return twist, np.degrees((Rot.from_quat(q) * Rot.from_quat(tw).inv()).as_rotvec())

def clamp_joint(q, q0, axis, lat, nrm, lim_tw, lim_lat, lim_nrm):
    """local q [F,4] with rest q0: the delta off rest, as twist about axis then swing (about lat / nrm, + the rest),
    each part clamped; returns the new local q and how many frames changed"""
    d = (Rot.from_quat(q0).inv() * Rot.from_quat(q)).as_quat(); tw, sw = swing_twist(d, axis)
    a1, a2 = sw @ lat, sw @ nrm; a3 = sw - np.outer(a1, lat) - np.outer(a2, nrm)
    t2, b1, b2 = np.clip(tw, -lim_tw, lim_tw), np.clip(a1, -lim_lat, lim_lat), np.clip(a2, -lim_nrm, lim_nrm)
    ch = int(((t2 != tw) | (b1 != a1) | (b2 != a2)).sum())
    if not ch: return q, 0, [float(np.abs(tw).max()), float(np.abs(a1).max()), float(np.abs(a2).max())]
    sw2 = np.outer(b1, lat) + np.outer(b2, nrm) + a3
    d2 = Rot.from_rotvec(np.radians(sw2)) * Rot.from_rotvec(np.radians(t2)[:, None] * axis)
    return (Rot.from_quat(q0) * d2).as_quat(), ch, [float(np.abs(tw).max()), float(np.abs(a1).max()), float(np.abs(a2).max())]

def main(src, dst, phone):
    j = exp(src); N = j['nodes']; ix = {n['name']: i for i, n in enumerate(N)}; tr, F = tracks(j)
    ref = medians(REF); grip = medians(GRIP) if phone in ('Left', 'Right') else {}
    rest = {i: np.array(n['r'], float) for i, n in enumerate(N)}; pos = {i: np.array(n['t'], float) for i, n in enumerate(N)}
    def rot(nm):
        i = ix[nm]; d = tr.setdefault(i, {})
        if 'rotation' not in d: d['rotation'] = np.tile(rest[i], (F, 1))
        return d['rotation']
    def axis(nm, child):                                       # bone direction in its own frame (= child's local offset)
        v = pos[ix[child]]; return v / np.linalg.norm(v)
    rep = {}
    for side in ('Left', 'Right'):
        held = side == phone; src_pose = grip if held else ref; r = rep.setdefault(side, {'fingers': 'room_phone grip, still' if held else f'room_seated_idle relaxed + {CURL} x clip curl'})
        for f in FING:
            for k in (1, 2, 3):
                nm = f'mixamorig:{side}Hand{f}{k}'; q = rot(nm); qr = src_pose[nm]
                if held or f == 'Thumb': new = np.tile(qr, (F, 1))
                else:                                          # slight curl: the clip's own flexion off its median, about X
                    m = np.median(q, 0); m /= np.linalg.norm(m)
                    dq = (Rot.from_quat(m).inv() * Rot.from_quat(q)).as_quat()
                    th = np.clip(CURL * 2 * np.degrees(np.arctan2(dq[:, 0], dq[:, 3])), -CURL_MAX, CURL_MAX)
                    new = (Rot.from_quat(qr) * Rot.from_rotvec(np.radians(th)[:, None] * [1, 0, 0])).as_quat()
                tr[ix[nm]]['rotation'] = new
        # wrist: the palm frame in the hand's rest frame (a: to the middle knuckle, n: palm normal, l: across)
        hn, fn = f'mixamorig:{side}Hand', f'mixamorig:{side}ForeArm'
        a = axis(hn, f'mixamorig:{side}HandMiddle1')
        rq = Rot.from_quat(rest[ix[hn]])
        i1, p1 = pos[ix[f'mixamorig:{side}HandIndex1']], pos[ix[f'mixamorig:{side}HandPinky1']]
        n = np.cross(i1, p1); n -= (n @ a) * a; n /= np.linalg.norm(n); l = np.cross(a, n)
        if held: r['wrist'] = 'as baked (holds the phone)'
        else:
            q2, ch, mx = clamp_joint(rot(hn), rest[ix[hn]], a, l, n, WR, WF, WD); tr[ix[hn]]['rotation'] = q2
            r['wrist'] = dict(frames_clamped=ch, max_before_roll_flex_dev=[round(x, 1) for x in mx])
        fa = axis(fn, hn); u = np.cross(fa, [1, 0, 0] if abs(fa[0]) < 0.9 else [0, 1, 0]); u /= np.linalg.norm(u); w = np.cross(fa, u)
        q2, ch, mx = clamp_joint(rot(fn), rest[ix[fn]], fa, u, w, FR, 180, 180); tr[ix[fn]]['rotation'] = q2
        r['forearm_roll'] = dict(frames_clamped=ch, max_before=round(mx[0], 1))
    name = os.environ.get('CLIP_NAME') or j['anims'][0].get('name') or os.path.splitext(os.path.basename(dst))[0]
    fin = dict(name=name, fps=30, F=F, nodes=N,
               rot={str(i): np.round(d['rotation'], 6).ravel().tolist() for i, d in tr.items() if 'rotation' in d},
               trans={str(i): np.round(d['translation'], 4).ravel().tolist() for i, d in tr.items() if 'translation' in d})
    tmp = tempfile.mktemp(suffix='.json'); json.dump(fin, open(tmp, 'w'))
    subprocess.run(['node', WRITE, tmp, dst], check=True, capture_output=True, cwd=os.path.join(H, '..')); os.remove(tmp)
    print(json.dumps(dict(clip=name, out=dst, **rep)), flush=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '-')
