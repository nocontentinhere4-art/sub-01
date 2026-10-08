"""Sims 4 clip (decoded by s4clip.py) -> mixamorig:* local rotations on char_mixamo.glb.

Per-bone world-rotation transfer through anatomical frames:
  A = frame(primary = bone -> child direction, secondary = hinge / lateral axis)
  Sims: A is constant in each bone's local frame (Sims bones point along +X and hinge about local Z;
        the hinge axes are estimated from the motion data itself, see hinge_axes()).
  Mixamo: A is measured on the T-pose node rest (arms along +-X, palms down, facing +Z).
  R_mixamo(t) = R_sims(t) * A_sims_local * A_mixamo_rest^T * R_mixamo_rest
Usage: python3 -I retarget.py <package> <char.glb (meshopt-decoded)> <out dir> set_11 set_4 ..."""
import json, struct, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4clip import clips_by_set, s3clip, set_names
from s4skel import parents, local_tracks, world, qrot, qmul, qnorm, PROPS, FING

def q2m(q):
    x, y, z, w = np.moveaxis(np.asarray(q, float), -1, 0)
    return np.stack([np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], -1),
                     np.stack([2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], -1),
                     np.stack([2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], -1)], -2)
def m2q(m):
    m = np.asarray(m, float); out = np.empty(m.shape[:-2] + (4,))
    flat = m.reshape(-1, 3, 3); o = out.reshape(-1, 4)
    for i, r in enumerate(flat):
        t = np.trace(r)
        if t > 0:
            s = np.sqrt(t + 1) * 2; o[i] = [(r[2,1]-r[1,2])/s, (r[0,2]-r[2,0])/s, (r[1,0]-r[0,1])/s, s/4]
        else:
            k = np.argmax(np.diag(r)); a, b, c = k, (k+1) % 3, (k+2) % 3
            s = np.sqrt(1 + r[a,a] - r[b,b] - r[c,c]) * 2
            v = np.empty(4); v[a] = s/4; v[b] = (r[b,a]+r[a,b])/s; v[c] = (r[c,a]+r[a,c])/s; v[3] = (r[c,b]-r[b,c])/s
            o[i] = v
    return out
def frame(p, s):
    x = p / np.linalg.norm(p); z = np.cross(x, s); z /= np.linalg.norm(z); y = np.cross(z, x)
    return np.stack([x, y, z], -1)
qinv = lambda q: q * np.array([-1, -1, -1, 1.])
X, Y, Z = np.eye(3)

# ---------------------------------------------------------------- mixamo side
def load_glb(path):
    d = open(path, 'rb').read(); L, = struct.unpack_from('<I', d, 12)
    j = json.loads(d[20:20+L]); return d, j, 20 + L + 8
class Mixamo:
    def __init__(self, path):
        self.d, self.j, self.bin0 = load_glb(path)
        N = self.j['nodes']; self.N = N
        self.idx = {n['name']: i for i, n in enumerate(N)}
        self.par = {}
        for i, n in enumerate(N):
            for c in n.get('children', []): self.par[c] = i
        self.lt = {i: np.array(n.get('translation', [0, 0, 0]), float) for i, n in enumerate(N)}
        self.lq = {i: np.array(n.get('rotation', [0, 0, 0, 1]), float) for i, n in enumerate(N)}
        self.ls = {i: np.array(n.get('scale', [1, 1, 1]), float) for i, n in enumerate(N)}
        self.joints = [N[k]['name'] for k in self.j['skins'][0]['joints']]
        self.rest = {}
        for nm in self.joints: self.rest[nm] = self.world_rest(self.idx[nm])
    def world_rest(self, i):
        t, q, s = self.lt[i], self.lq[i], self.ls[i]
        if i not in self.par: return t, q, s
        pt, pq, ps = self.world_rest(self.par[i]); return pt + qrot(pq, t * ps), qmul(pq, q), ps * s
    def P(self, b): return self.rest['mixamorig:' + b][0]
    def Q(self, b): return self.rest['mixamorig:' + b][1]
    def parent_name(self, nm): return self.N[self.par[self.idx[nm]]]['name']

S2M = {'b__ROOT_bind__': 'Hips', 'b__Spine0__': 'Spine', 'b__Spine1__': 'Spine1', 'b__Spine2__': 'Spine2',
       'b__Neck__': 'Neck', 'b__Head__': 'Head'}
MF = {'Thumb': 'Thumb', 'Index': 'Index', 'Mid': 'Middle', 'Ring': 'Ring', 'Pinky': 'Pinky'}
for s, side in (('L', 'Left'), ('R', 'Right')):
    S2M.update({f'b__{s}_Clavicle__': side + 'Shoulder', f'b__{s}_UpperArm__': side + 'Arm',
                f'b__{s}_Forearm__': side + 'ForeArm', f'b__{s}_Hand__': side + 'Hand',
                f'b__{s}_Thigh__': side + 'UpLeg', f'b__{s}_Calf__': side + 'Leg',
                f'b__{s}_Foot__': side + 'Foot', f'b__{s}_Toe__': side + 'ToeBase'})
    for f in FING:
        for k in range(3): S2M[f'b__{s}_{f}{k}__'] = f'{side}Hand{MF[f]}{k+1}'

def mixamo_frames(M, U):
    """anatomical frame per mixamo bone in world (T-pose node rest). U: finger hinge axes in hand frame."""
    A = {}
    # trunk and head: the T-pose rest is his neutral upright posture (face +Z), so "up" is world +Y, not the
    # joint chain (Mixamo's Head->HeadTop leans 19 deg forward: using it tipped his face back)
    for a in ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head'):
        A[a] = frame(Y, X)
    for side in ('Left', 'Right'):
        A[side+'Shoulder'] = frame(M.P(side+'Arm') - M.P(side+'Shoulder'), Y)
        for a, b in [('Arm', 'ForeArm'), ('ForeArm', 'Hand')]:
            d = M.P(side+b) - M.P(side+a); A[side+a] = frame(d, np.cross(d, Z))   # elbow flexes forward
        Ah = frame(M.P(side+'HandMiddle1') - M.P(side+'Hand'), M.P(side+'HandIndex1') - M.P(side+'HandPinky1'))
        A[side+'Hand'] = Ah
        for f in MF.values():
            for k in (1, 2, 3):
                d = M.P(f'{side}Hand{f}{k+1}') - M.P(f'{side}Hand{f}{k}')
                A[f'{side}Hand{f}{k}'] = frame(d, Ah @ U[(side[0], f, k)])
        for a, b in [('UpLeg', 'Leg'), ('Leg', 'Foot'), ('Foot', 'ToeBase'), ('ToeBase', 'Toe_End')]:
            A[side+a] = frame(M.P(side+b) - M.P(side+a), X)               # knee hinge = +X in T-pose
    return A

# ---------------------------------------------------------------- sims side
def hinge_axes(clips, P):
    """data-estimated hinge axis per Sims bone (local frame) + finger hinges in the hand's anatomical frame"""
    acc, accU = {}, {}
    for c in clips:
        T = local_tracks(c, list(P)); W = world(T, P)
        for s in 'LR':
            Ah = sims_hand_frame(T, W, s)
            chains = [('UpperArm', 'Forearm', 'Hand'), ('Thigh', 'Calf', 'Foot')]
            chains += [(f+'0', f+'1', f+'2') for f in FING]
            for a, b, cc in chains:
                A_, B_, C_ = (f'b__{s}_{x}__' for x in (a, b, cc))
                da = W[B_][0] - W[A_][0]; db = W[C_][0] - W[B_][0]
                cr = np.cross(da, db); n = np.linalg.norm(cr, axis=1) / np.linalg.norm(da, axis=1) / np.linalg.norm(db, axis=1)
                m = n > 0.25
                if not m.any(): continue
                h = cr[m] / np.linalg.norm(cr[m], axis=1, keepdims=True)
                for bone in (A_, B_):
                    acc.setdefault(bone, []).append(qrot(qinv(W[bone][1][m]), h))
                if a[:-1] in FING:
                    hu = np.einsum('nji,nj->ni', Ah[m], h)           # hinge in hand anatomical frame
                    for k in (0, 1): accU.setdefault((s, a[:-1], k + 1), []).append(hu)
    H = {k: (lambda m: m / np.linalg.norm(m))(np.concatenate(v).mean(0)) for k, v in acc.items()}
    U = {k: (lambda m: m / np.linalg.norm(m))(np.concatenate(v).mean(0)) for k, v in accU.items()}
    for s in 'LR':
        for f in FING:
            H[f'b__{s}_{f}2__'] = H[f'b__{s}_{f}1__']; U[(s, f, 3)] = U[(s, f, 2)]
    return H, {(('Left' if s == 'L' else 'Right')[0], MF[f], k): v for (s, f, k), v in U.items()}

def sims_hand_frame(T, W, s):
    """world anatomical frame of the Sims hand per frame: primary hand->Mid0, secondary Pinky0->Index0"""
    q = W[f'b__{s}_Hand__'][1]
    p = T[f'b__{s}_Mid0__'][0][0]; l = T[f'b__{s}_Index0__'][0][0] - T[f'b__{s}_Pinky0__'][0][0]
    return q2m(q) @ frame(p, l)

def sims_local_frames(T0, W0, H):
    """constant anatomical frame of each mapped Sims bone, in its own local frame"""
    A = {}
    for b in ['b__ROOT_bind__', 'b__Spine0__', 'b__Spine1__', 'b__Spine2__', 'b__Neck__', 'b__Head__']:
        A[b] = frame(X, Z)                                # Sims spine chain: X up the chain, Z = his left
    for s in 'LR':
        q = W0[f'b__{s}_Clavicle__'][1][0]               # clavicle: secondary = world up in a standing frame
        A[f'b__{s}_Clavicle__'] = frame(T0[f'b__{s}_UpperArm__'][0][0], qrot(qinv(q), Y))
        A[f'b__{s}_UpperArm__'] = frame(T0[f'b__{s}_Forearm__'][0][0], H[f'b__{s}_UpperArm__'])
        A[f'b__{s}_Forearm__'] = frame(T0[f'b__{s}_Hand__'][0][0], H[f'b__{s}_Forearm__'])
        A[f'b__{s}_Hand__'] = frame(T0[f'b__{s}_Mid0__'][0][0], T0[f'b__{s}_Index0__'][0][0] - T0[f'b__{s}_Pinky0__'][0][0])
        for f in FING:
            for k in range(3):
                b = f'b__{s}_{f}{k}__'
                d = T0[f'b__{s}_{f}{k+1}__'][0][0] if k < 2 else X
                A[b] = frame(d, H[b])
        A[f'b__{s}_Thigh__'] = frame(T0[f'b__{s}_Calf__'][0][0], H[f'b__{s}_Thigh__'])
        A[f'b__{s}_Calf__'] = frame(T0[f'b__{s}_Foot__'][0][0], H[f'b__{s}_Calf__'])
        for b, ch in (('Foot', 'Toe'), ('Toe', None)):
            q = W0[f'b__{s}_{b}__'][1][0]                 # lateral = world +X in a standing frame
            d = T0[f'b__{s}_{ch}__'][0][0] if ch else X
            A[f'b__{s}_{b}__'] = frame(d, qrot(qinv(q), X))
    return A

class Retarget:
    def __init__(self, pkg, glb):
        self.ents, self.raw = clips_by_set(pkg)
        self.P = parents(); self.M = Mixamo(glb)
        self.clips = {k: s3clip(v) for k, v in self.raw.items()}
        self.names = set_names(self.ents)
        self.H, self.U = hinge_axes(list(self.clips.values()), self.P)
        st = self.clips['set_10']                          # standing (TEXTING): reference for clavicle/foot axes
        T0 = local_tracks(st, list(self.P)); W0 = world(T0, self.P)
        self.AS = sims_local_frames(T0, W0, self.H)
        self.AM = mixamo_frames(self.M, self.U)
        # phone convention in the Sims prop slot, learned from the portrait viewing clips: the head's up axis is
        # the slot's +Z and the eyes lie in a fixed direction from the slot; screen normal = that direction minus its Z part
        # (per hand: the left from the left-hand portrait clips, the right from the couch clips held in the right)
        self.slot_n = {}
        for s_, sids in (('L', ('set_39', 'set_41', 'set_42', 'set_45', 'set_10')), ('R', ('set_18', 'set_20'))):
            acc = []
            for sid in sids:
                Tc = local_tracks(self.clips[sid], list(self.P) + PROPS); Wc = world(Tc, self.P)
                hq = Wc['b__Head__'][1]; eye = Wc['b__Head__'][0] + qrot(hq, np.array([0.06, 0.09, 0.]))
                pw, pq = Tc[f'b__{s_}_Prop__']; v = eye - pw; v /= np.linalg.norm(v, axis=1, keepdims=True)
                acc.append(qrot(qinv(pq), v))
                up = qrot(qinv(pq), qrot(hq, X)).mean(0)
            e = np.concatenate(acc).mean(0); e[2] = 0; self.slot_n[s_] = e / np.linalg.norm(e)
            self.slot_up = getattr(self, 'slot_up', {}); self.slot_up[s_] = np.sign(up[2]) or 1.0
        self.K = {}
        for sb, mb in S2M.items():
            Rm = q2m(self.M.Q(mb))
            self.K[sb] = self.AS[sb] @ self.AM[mb].T @ Rm
        # scale: hip-joint height (Sims thighs / mixamo up-legs) when standing
        mid = 0.5 * (self.M.P('LeftUpLeg') + self.M.P('RightUpLeg'))
        self.k = mid[1] / W0['b__ROOT_bind__'][0][0][1]
        self.hip_off = self.M.P('Hips') - mid

    def run(self, set_id, twist=0.5, clip=None, name=None, phone=True):
        """set_id of the reference (phone Ver. 8) package, or any decoded clip (s4clip.s3clip) from another package"""
        c = clip if clip is not None else self.clips[set_id]; n = c['nframes']
        T = local_tracks(c, list(self.P) + PROPS); W = world(T, self.P)
        M = self.M; Rw = {}
        for sb, mb in S2M.items():
            Rw[mb] = q2m(W[sb][1]) @ self.K[sb]
        # forearm twist: move part of the wrist's twist about the forearm axis into the forearm
        if twist:
            for side in ('Left', 'Right'):
                Rf, Rh = Rw[side+'ForeArm'], Rw[side+'Hand']
                ax = Rf @ (q2m(M.Q(side+'ForeArm')).T @ (M.P(side+'Hand') - M.P(side+'ForeArm')))
                ax /= np.linalg.norm(ax, axis=-1, keepdims=True)
                rel = Rh @ np.swapaxes(Rf, -1, -2)      # world-space delta hand vs forearm
                qr = m2q(rel); proj = np.einsum('ni,ni->n', qr[:, :3], ax)
                tw = np.concatenate([ax * proj[:, None], qr[:, 3:]], 1); tw = qnorm(tw + 1e-12)
                ang = 2 * np.arctan2(np.linalg.norm(tw[:, :3], axis=1) * np.sign(np.einsum('ni,ni->n', tw[:, :3], ax)), tw[:, 3])
                ang = (ang + np.pi) % (2 * np.pi) - np.pi
                part = qnorm(np.concatenate([ax * np.sin(twist * ang / 2)[:, None], np.cos(twist * ang / 2)[:, None]], 1))
                Rw[side+'ForeArm'] = q2m(part) @ Rf
        # local rotations
        out = {}
        def wq(nm):
            b = nm.split(':')[1]
            if b in Rw: return m2q(Rw[b])
            pq = wq(M.parent_name(nm)); return qmul(pq, np.broadcast_to(M.lq[M.idx[nm]], pq.shape))
        cache = {}
        def W_(nm):
            if nm not in cache: cache[nm] = wq(nm) if nm.startswith('mixamorig:') else np.tile([0, 0, 0, 1.], (n, 1))
            return cache[nm]
        for nm in M.joints:
            b = nm.split(':')[1]
            if b not in Rw: continue
            pq = W_(M.parent_name(nm)) if M.parent_name(nm).startswith('mixamorig:') else np.tile([0, 0, 0, 1.], (n, 1))
            lq = qnorm(qmul(qinv(pq), W_(nm)))
            for i in range(1, n):
                if np.dot(lq[i], lq[i-1]) < 0: lq[i] = -lq[i]
            out[nm] = lq
        hips = self.k * W['b__ROOT_bind__'][0] + np.einsum('nij,j->ni', Rw['Hips'] @ q2m(M.Q('Hips')).T, self.hip_off)
        arm_scale = M.ls[M.idx['mixamo']][0]
        if not phone:
            return dict(set=set_id, name=name or '', hand=None, fps=30, frames=n, rot={k: v.round(6).tolist() for k, v in out.items()},
                        hips=(hips / arm_scale).round(4).tolist(), props={}, k=self.k)
        props = {}
        hq = W['b__Head__'][1]; hp_ = W['b__Head__'][0]
        eye = hp_ + qrot(hq, np.array([0.06, 0.09, 0.]))           # Sims head: X up, Y forward, Z his left
        h_up, h_left = qrot(hq, X), qrot(hq, Z)
        landscape = 'LANDSCAPE' in (name or self.names.get(set_id, ''))
        for s, side in (('R', 'Right'), ('L', 'Left')):
            pw = T[f'b__{s}_Prop__'][0]; pq = T[f'b__{s}_Prop__'][1]      # baked world-space slot
            hp = W[f'b__{s}_Hand__'][0]
            Rm = Rw[side + 'Hand']; hand_m = hp  # world orientation of the mixamo hand
            rel_p = np.einsum('nji,nj->ni', Rm, (pw - hp) * self.k)       # in mixamo hand frame (m)
            v = eye - pw; dist = np.linalg.norm(v, axis=1); v = v / dist[:, None]
            gaze = np.degrees(np.arccos(np.clip(np.einsum('ni,ni->n', -v, qrot(hq, Y)), -1, 1)))
            call = np.median(dist) < 0.15
            if call:   # at the ear: screen against the cheek, long axis from ear towards the mouth
                n_ = hp_ + qrot(hq, np.array([0.05, 0.05, 0.])) - pw
            screen_eye = None; lng = qrot(hq, np.array([-0.5, 0.85, 0.]))
            if call:
                n_ = n_ / np.linalg.norm(n_, axis=1, keepdims=True)
                lng = lng - n_ * np.einsum('ni,ni->n', lng, n_)[:, None]; lng /= np.linalg.norm(lng, axis=1, keepdims=True)
                Rp = np.stack([n_, lng, np.cross(n_, lng)], -1)      # phone: +x screen normal, +y long axis
            else:      # watching: rigid in the slot (learned convention), long axis sideways for landscape
                ns = self.slot_n[s]; zs = Z * self.slot_up[s]; ls = np.cross(zs, ns) if landscape else zs
                Rp = q2m(pq) @ np.stack([ns, ls, np.cross(ns, ls)], -1)
            rel_R = np.swapaxes(Rm, -1, -2) @ Rp
            # mean rotation over the clip (the grip is rigid): average the matrices, re-orthonormalise
            u, _, vt = np.linalg.svd(rel_R.mean(0)); Rmean = u @ vt
            spread = np.degrees(np.arccos(np.clip((np.einsum('nij,ij->n', rel_R, Rmean) - 1) / 2, -1, 1)))
            ctr = rel_p.mean(0) + Rmean[:, 0] * 0.012                 # back of the phone on the fingers
            props[side] = dict(pos=ctr.tolist(), quat=m2q(Rmean).tolist(), pos_std_mm=float(rel_p.std(0).max() * 1000),
                               eye_dist=float(np.median(dist)), gaze_deg=float(np.median(gaze)), call=bool(call),
                               grip_spread_deg=float(np.percentile(spread, 90)))
        cand = sorted(props, key=lambda sd: (not props[sd]['call'], props[sd]['gaze_deg'] if not props[sd]['call'] else props[sd]['eye_dist']))
        calls = [sd for sd in props if props[sd]['call']]
        # the viewing hand: the slot nearest his line of sight; a tie (both hands at the phone) goes to the rigid grip
        hand = calls[0] if calls else min(props, key=lambda sd: (round(props[sd]['gaze_deg'] / 5), props[sd]['grip_spread_deg']))
        return dict(set=set_id, name=name or self.names.get(set_id, ''), hand=hand, fps=30, frames=n, rot={k: v.round(6).tolist() for k, v in out.items()},
                    hips=(hips / arm_scale).round(4).tolist(), props=props, k=self.k)

if __name__ == '__main__':
    R = Retarget(sys.argv[1], sys.argv[2]); os.makedirs(sys.argv[3], exist_ok=True)
    print('scale k', round(R.k, 4))
    for s in sys.argv[4:]:
        r = R.run(s); json.dump(r, open(os.path.join(sys.argv[3], s + '.json'), 'w'))
        print(s, r['name'], r['frames'], 'hand', r['hand'], {k: (round(v['eye_dist'], 2), round(v['gaze_deg']), v['call'], round(v['grip_spread_deg'])) for k, v in r['props'].items()})
