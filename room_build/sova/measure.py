"""Whole-clip contact pass on our character (meshopt-decoded char_mixamo.glb) for a retarget.py JSON.
Every `step`-th frame, every 2nd skin vertex, linear-blend skinned like three.js does:
  - hands/fingers into his body (torso, head, legs, the other arm): nearest body vertex + its normal
  - the phone (7.2 x 15 x 0.8 cm box) into his head/face; fingers into the phone; the eye -> screen distance/angle
  - lying clips: the body against a fixed mattress plane (the lowest torso/leg point over the clip)
python3 -I measure.py <char.glb> <clip.json>... -> prints a JSON line per clip"""
import json, sys, os
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retarget import Mixamo, q2m

PH = np.array([0.008, 0.150, 0.072])      # phone box: x = thickness (screen normal), y = long, z = wide

def accessor(M, i):
    a = M.j['accessors'][i]; bv = M.j['bufferViews'][a['bufferView']]
    ct = {5126: np.float32, 5123: np.uint16, 5122: np.int16, 5121: np.uint8, 5120: np.int8, 5125: np.uint32}[a['componentType']]
    nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    off = M.bin0 + bv.get('byteOffset', 0) + a.get('byteOffset', 0); isz = np.dtype(ct).itemsize
    stride = bv.get('byteStride') or nc * isz
    raw = np.frombuffer(M.d, np.uint8, stride * (a['count'] - 1) + nc * isz, off)
    out = np.lib.stride_tricks.as_strided(raw, (a['count'], nc * isz), (stride, 1)).copy().view(ct).reshape(a['count'], nc)
    if a.get('normalized') and ct != np.float32: out = np.maximum(out.astype(np.float32) / np.iinfo(ct).max, -1)
    return out

def mat(t, q, s):
    m = np.zeros(q.shape[:-1] + (4, 4)); m[..., :3, :3] = q2m(q) * s[..., None, :]; m[..., :3, 3] = t; m[..., 3, 3] = 1; return m

class Body:
    def __init__(self, glb, vstep=2):
        M = Mixamo(glb); self.M = M
        sk = M.j['skins'][0]; self.jn = [M.N[i]['name'] for i in sk['joints']]
        self.ibm = accessor(M, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        P, Nn, J, Wt = [], [], [], []
        for node in M.N:
            if 'mesh' not in node or 'skin' not in node: continue
            for pr in M.j['meshes'][node['mesh']]['primitives']:
                at = pr['attributes']
                P.append(accessor(M, at['POSITION'])); Nn.append(accessor(M, at['NORMAL']))
                J.append(accessor(M, at['JOINTS_0']).astype(int)); Wt.append(accessor(M, at['WEIGHTS_0']).astype(float))
        sel = slice(None, None, vstep)
        self.P = np.concatenate(P)[sel].astype(float); self.Nm = np.concatenate(Nn)[sel].astype(float)
        self.J = np.concatenate(J)[sel]; self.W = np.concatenate(Wt)[sel]; self.W /= self.W.sum(1, keepdims=True)
        dom = np.array(self.jn)[self.J[np.arange(len(self.J)), self.W.argmax(1)]]
        b = np.array([d.split(':')[1] for d in dom])
        reg = np.full(len(b), 'other', object)
        reg[np.isin(b, ['Head', 'HeadTop_End'])] = 'head'
        reg[np.isin(b, ['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'LeftShoulder', 'RightShoulder'])] = 'torso'
        for s in ('Left', 'Right'):
            reg[np.isin(b, [s + 'UpLeg', s + 'Leg', s + 'Foot', s + 'ToeBase', s + 'Toe_End'])] = 'legs'
            reg[np.isin(b, [s + 'Arm', s + 'ForeArm'])] = s + 'Arm'
            reg[np.char.startswith(b.astype(str), s + 'Hand')] = s + 'Hand'
        self.reg = reg; self.bone = b
        # eyes (bind pose): 3.5 cm above and 3 cm behind the nose tip (front-most midline head vertex below the fringe)
        hv = self.P[reg == 'head']; hv = hv[(np.abs(hv[:, 0]) < 0.03) & (hv[:, 1] < hv[:, 1].max() - 0.15)]
        self.eye_bind = hv[hv[:, 2].argmax()] * [0, 1, 1] + [0, 0.035, -0.03]

    def joints(self, clip):
        """world matrices [n, J, 4, 4] for every node on the joint list"""
        M = self.M; n = clip['frames']; out = {}
        def wm(nm):
            if nm in out: return out[nm]
            i = M.idx[nm]; t = np.broadcast_to(M.lt[i], (n, 3)).copy(); q = np.broadcast_to(M.lq[i], (n, 4)).copy(); s = np.broadcast_to(M.ls[i], (n, 3))
            if nm in clip['rot']: q = np.array(clip['rot'][nm])
            if nm == 'mixamorig:Hips': t = np.array(clip['hips'])
            m = mat(t, q, s)
            if i in M.par: m = wm(M.N[M.par[i]]['name']) @ m
            out[nm] = m; return m
        return np.stack([wm(nm) for nm in self.jn], 1), wm

    def skin(self, Wj, f):
        S = Wj[f] @ self.ibm                                    # [J,4,4]
        Mv = np.einsum('vk,vkij->vij', self.W, S[self.J])       # blended per vertex
        p = np.einsum('vij,vj->vi', Mv[:, :3, :3], self.P) + Mv[:, :3, 3]
        nn = np.einsum('vij,vj->vi', Mv[:, :3, :3], self.Nm); nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-12
        return p, nn

def measure(B, clip, step=2, lying=None):
    Wj, wm = B.joints(clip); n = clip['frames']; side = clip.get('hand')
    phone = side is not None
    if phone:
        hand_m = wm(f'mixamorig:{side}Hand'); pr = clip['props'][side]
        ph_local = mat(np.array(pr['pos']) / 0.01, np.array(pr['quat']), np.array([100., 100, 100]))
        PHW = hand_m @ ph_local                                      # phone world [n,4,4]
    head = wm('mixamorig:Head'); ji = B.jn.index('mixamorig:Head')
    eye_l = np.linalg.inv(B.ibm[ji]) @ np.append(B.eye_bind, 1)              # head-local position of the bind eye
    R = {k: [] for k in ('hand_body', 'phone_head', 'finger_phone', 'eye')}
    lows = []
    reg = B.reg; frames = list(range(0, n, step))
    for f in frames:
        p, nn = B.skin(Wj, f)
        # hands into the body
        res = {}
        for s in ('Left', 'Right'):
            other = 'Right' if s == 'Left' else 'Left'
            body = np.isin(reg, ['torso', 'head', 'legs', other + 'Arm', other + 'Hand'])
            tree = cKDTree(p[body]); hv = p[reg == s + 'Hand']
            d, i = tree.query(hv, distance_upper_bound=0.10)
            ok = np.isfinite(d); q = p[body][i[ok]]; qn = nn[body][i[ok]]
            depth = -np.einsum('ij,ij->i', hv[ok] - q, qn)
            m = depth > 0.01; deep = depth[m]; rg = reg[body][i[ok]][m]
            byreg = {r: float(deep[rg == r].max()) for r in set(rg)}
            res[s] = (len(deep), float(deep.max()) if len(deep) else 0.0, byreg)
        R['hand_body'].append(res)
        if lying is not None:
            lows.append([p[reg == r][:, 1].min() for r in ('torso', 'legs', 'head')] + [p[:, 1].min()])
        if not phone: continue
        # phone vs head, fingers vs phone
        inv = np.linalg.inv(PHW[f]); hl = (inv[:3, :3] @ p[reg == 'head'].T).T + inv[:3, 3]
        inside = np.all(np.abs(hl) < PH / 2, axis=1)
        dbox = np.linalg.norm(np.maximum(np.abs(hl) - PH / 2, 0), axis=1)
        fl = (inv[:3, :3] @ p[reg == side + 'Hand'].T).T + inv[:3, 3]
        fin = np.all(np.abs(fl) < PH / 2, axis=1)
        fdepth = (PH / 2 - np.abs(fl[fin])).min(1) if fin.any() else np.zeros(0)
        R['phone_head'].append((int(inside.sum()), float(dbox.min())))
        R['finger_phone'].append((int(fin.sum()), float(fdepth.max()) if len(fdepth) else 0.0))
        eye = (head[f] @ eye_l)[:3]; c = PHW[f][:3, 3]; nrm = PHW[f][:3, 0] / np.linalg.norm(PHW[f][:3, 0])
        v = eye - c; dist = np.linalg.norm(v); R['eye'].append((float(dist), float(np.degrees(np.arccos(np.clip(v @ nrm / dist, -1, 1))))))
    out = dict(set=clip['set'], name=clip['name'], hand=side, frames_measured=len(frames), step=step)
    for s in ('Left', 'Right'):
        a = np.array([r[s][:2] for r in R['hand_body']]); br = {}
        for r in R['hand_body']:
            for k, v in r[s][2].items(): br[k] = max(br.get(k, 0), v)
        out[f'{s}_hand_in_body'] = dict(frames=int((a[:, 0] > 0).sum()), max_verts=int(a[:, 0].max()), max_depth_cm=round(a[:, 1].max() * 100, 1),
                                        by_region_cm={k: round(v * 100, 1) for k, v in sorted(br.items())})
        # fingers alive: per finger joint, the rotation range over the clip (deg, about its own median), max per hand
        rngs = []
        for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
            for k in (1, 2, 3):
                q = np.array(clip['rot'][f'mixamorig:{s}Hand{f}{k}']); med = q[len(q) // 2]
                ang = 2 * np.degrees(np.arccos(np.clip(np.abs(q @ med), -1, 1))); rngs.append(np.percentile(ang, 98))
        out[f'{s}_finger_motion_deg'] = dict(median_joint=round(float(np.median(rngs)), 1), max_joint=round(float(np.max(rngs)), 1))
    if not phone: R['phone_head'] = R['finger_phone'] = R['eye'] = None
    if phone:
      a = np.array(R['phone_head']); out['phone_in_head'] = dict(frames=int((a[:, 0] > 0).sum()), max_verts=int(a[:, 0].max()), min_gap_cm=round(a[:, 1].min() * 100, 1))
      a = np.array(R['finger_phone']); out['fingers_in_phone'] = dict(frames=int((a[:, 0] > 0).sum()), max_verts=int(a[:, 0].max()), max_depth_cm=round(a[:, 1].max() * 100, 1))
      a = np.array(R['eye']); out['eye_to_screen'] = dict(dist_cm=[round(a[:, 0].min() * 100), round(a[:, 0].max() * 100)], angle_deg_median=round(float(np.median(a[:, 1]))), angle_deg_max=round(float(a[:, 1].max())))
    if lying is not None:
        L = np.array(lows); plane = L[:, 0].min()                  # mattress = lowest torso point (back/buttocks) over the clip
        sup = L[:, 0]
        out['mattress'] = dict(plane_y=round(float(plane), 3), torso_support_range_cm=round(float((sup.max() - sup.min()) * 100), 1),
                               torso_low_range_cm=[round(float((L[:, 0].min() - plane) * 100), 1), round(float((L[:, 0].max() - plane) * 100), 1)],
                               legs_low_range_cm=[round(float((L[:, 1].min() - plane) * 100), 1), round(float((L[:, 1].max() - plane) * 100), 1)],
                               any_below_cm=round(float((plane - L[:, 3].min()) * 100), 1))
    return out

if __name__ == '__main__':
    B = Body(sys.argv[1])
    for f in sys.argv[2:]:
        c = json.load(open(f)); step = 2 if c['frames'] <= 600 else 4
        lying = True if any(k in c['name'] for k in ('BED', 'WATCHING', 'TYPING', 'CALL VER')) and 'COUCH' not in c['name'] else None
        print(json.dumps(measure(B, c, step, lying)), flush=True)
