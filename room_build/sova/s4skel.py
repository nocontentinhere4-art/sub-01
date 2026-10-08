"""Sims 4 body skeleton (public bone names) + per-frame sampling of a decoded S3 clip.
Bone hash = FNV-32 of the lowercased name. Local offsets come from the clip's own position channels."""
import numpy as np
from s4clip import fnv32

FING = ['Thumb', 'Index', 'Mid', 'Ring', 'Pinky']
def _side(s):
    P = {}
    P[f'b__{s}_Thigh__'] = 'b__Pelvis__'
    P[f'b__{s}_Calf__'] = f'b__{s}_Thigh__'
    P[f'b__{s}_Foot__'] = f'b__{s}_Calf__'
    P[f'b__{s}_Toe__'] = f'b__{s}_Foot__'
    P[f'b__{s}_Clavicle__'] = 'b__Spine2__'
    P[f'b__{s}_UpperArm__'] = f'b__{s}_Clavicle__'
    P[f'b__{s}_Forearm__'] = f'b__{s}_UpperArm__'
    P[f'b__{s}_Hand__'] = f'b__{s}_Forearm__'
    for f in FING:
        P[f'b__{s}_{f}0__'] = f'b__{s}_Hand__'
        P[f'b__{s}_{f}1__'] = f'b__{s}_{f}0__'
        P[f'b__{s}_{f}2__'] = f'b__{s}_{f}1__'
    return P

def parents(spine_parent='b__ROOT_bind__'):
    P = {'b__ROOT_bind__': None, 'b__Pelvis__': 'b__ROOT_bind__', 'b__Spine0__': spine_parent,
         'b__Spine1__': 'b__Spine0__', 'b__Spine2__': 'b__Spine1__', 'b__Neck__': 'b__Spine2__', 'b__Head__': 'b__Neck__'}
    P.update(_side('L')); P.update(_side('R'))
    return P

PROPS = ['b__R_Prop__', 'b__L_Prop__', 'b__R_HandDangle_slot', 'b__L_HandDangle_slot']

def qmul(a, b):
    ax, ay, az, aw = np.moveaxis(a, -1, 0); bx, by, bz, bw = np.moveaxis(b, -1, 0)
    return np.stack([aw*bx + ax*bw + ay*bz - az*by, aw*by - ax*bz + ay*bw + az*bx,
                     aw*bz + ax*by - ay*bx + az*bw, aw*bw - ax*bx - ay*by - az*bz], -1)
def qrot(q, v):
    u = q[..., :3]; w = q[..., 3:4]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)
def qnorm(q): return q / np.linalg.norm(q, axis=-1, keepdims=True)

def sample_curve(frames, n, quat):
    """keys -> dense per-frame array (lerp / nlerp with hemisphere fix)"""
    idx = np.array([f for f, _ in frames], float); val = np.array([v for _, v in frames], float)
    if quat:
        val = qnorm(val)
        for i in range(1, len(val)):
            if np.dot(val[i], val[i-1]) < 0: val[i] = -val[i]
    out = np.empty((n, val.shape[1]))
    for k in range(val.shape[1]):
        out[:, k] = np.interp(np.arange(n), idx, val[:, k])
    return qnorm(out) if quat else out

def local_tracks(clip, names):
    """{name: (pos[n,3], quat[n,4])} for the named bones present in the clip"""
    n = clip['nframes']; H = {fnv32(nm.lower()): nm for nm in names}
    out = {}
    for c in clip['curves']:
        nm = H.get(c['key'])
        if nm is None: continue
        d = out.setdefault(nm, [None, None])
        d[0 if c['type'] == 1 else 1] = sample_curve(c['frames'], n, c['type'] == 2)
    return out

def world(tracks, P, extra_parent=None):
    """global (pos, quat) per bone; extra_parent maps prop bones -> parent"""
    P = dict(P); P.update(extra_parent or {})
    W = {}
    def go(b):
        if b in W: return W[b]
        p, q = tracks[b]
        par = P.get(b)
        if par is None: W[b] = (p, q)
        else:
            pp, pq = go(par)
            W[b] = (pp + qrot(pq, p), qmul(pq, q))
        return W[b]
    for b in P:
        if b in tracks: go(b)
    return W
