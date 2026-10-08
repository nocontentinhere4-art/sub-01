"""Round 4, "alive" (COORD after the owner: round 3's clamps made him stiff). On this morning's baked clip:
  - fingers follow the clip's OWN flexion per joint, rebuilt on Mixamo's relaxed hand (room_seated_idle): the curl
    stays, the sideways roll of the Sims fingers goes (a turn about each bone's curl axis only), nothing bends
    backwards (the curling branch), flexion clamped only to the owner's p1-p99, no rate limit;
  - the phone hand keeps round 2's grip (approved);
  - wrists and arms as baked, only single-frame flips undone;
  - nothing inside his body, moved only on the frames that go in, eased in and out (fit_hands.clear).
python3 -I fix_alive.py <char.glb decoded> <in.glb> <out.glb> [phone hand]"""
import json, sys, os, tempfile, subprocess
import numpy as np
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fix_hands_pose as fh
from owner_cmp import FN, REF
import fit_hands
from measure import Body

def p1p99():
    j = json.load(open(REF)); o = {}
    for f in FN:
        fl = np.array([h['fingers'][f]['flex'] for fr in j['frames'] for h in fr['hands']])
        o[f] = (np.percentile(fl, 1, 0), np.percentile(fl, 99, 0))
    return o

def unflip(q, big=60, back=30):
    q = q.copy(); a = lambda x, y: np.degrees(2 * np.arccos(np.clip(abs(np.sum(x * y, -1)), 0, 1))); n = 0
    for t in range(1, len(q) - 1):
        if a(q[t - 1], q[t]) > big and a(q[t - 1], q[t + 1]) < back:
            m = q[t - 1] + q[t + 1] * np.sign(q[t - 1] @ q[t + 1]); q[t] = m / np.linalg.norm(m); n += 1
    return q, n

def main(char, src, dst, phone):
    j = fh.exp(src); N = j['nodes']; ix = {n['name']: i for i, n in enumerate(N)}; tr, F = fh.tracks(j)
    ref = fh.medians(fh.REF); grip = fh.medians(fh.GRIP) if phone in ('Left', 'Right') else {}
    rest = {i: np.array(n['r'], float) for i, n in enumerate(N)}; pos = {i: np.array(n['t'], float) for i, n in enumerate(N)}
    def rot(nm):
        d = tr.setdefault(ix[nm], {})
        if 'rotation' not in d: d['rotation'] = np.tile(rest[ix[nm]], (F, 1))
        return d['rotation']
    L = p1p99(); rep = {}
    for side in ('Left', 'Right'):
        held = side == phone; r = rep.setdefault(side, {})
        for f in fh.FING:
            lo, hi = L[f.lower()]
            for k in (1, 2, 3):
                nm = f'mixamorig:{side}Hand{f}{k}'; q = rot(nm); ta, tb = pos[ix[nm]], pos[ix[f'mixamorig:{side}Hand{f}{k + 1}']]
                if held:
                    qr = grip[nm]; th = np.full(F, fh.solve(qr, ta, tb, np.clip(fh.flex(qr, ta, tb), lo[k - 1], hi[k - 1])))
                else:                                          # the clip's own flex, on the relaxed hand, curling side only
                    qr = ref[nm]; v = Rot.from_quat(q).apply(tb)
                    fl = np.degrees(np.arccos(np.clip(v @ ta / np.linalg.norm(ta) / np.linalg.norm(v, axis=1), -1, 1)))
                    g, fb = fh.branch(qr, ta, tb); th = np.interp(np.clip(fl, lo[k - 1], hi[k - 1]), fb, g)
                tr[ix[nm]]['rotation'] = (Rot.from_quat(qr) * Rot.from_rotvec(np.radians(th)[:, None] * [1, 0, 0])).as_quat()
        for b in ('Hand', 'ForeArm'):
            q2, n = unflip(rot(f'mixamorig:{side}{b}')); tr[ix[f'mixamorig:{side}{b}']]['rotation'] = q2; r[f'{b}_flips'] = n
    hi_ = ix['mixamorig:Hips']
    c = dict(set='x', name='x', frames=F, fps=30, hand=None, props={},
             rot={N[i]['name']: np.array(d['rotation']).tolist() for i, d in tr.items() if 'rotation' in d},
             hips=(tr[hi_]['translation'] if 'translation' in tr.get(hi_, {}) else np.tile(pos[hi_], (F, 1))).tolist())
    rep['clear'] = fit_hands.clear(Body(char, vstep=2), c)
    for nm, v in c['rot'].items(): tr.setdefault(ix[nm], {})['rotation'] = np.array(v)
    name = os.environ.get('CLIP_NAME') or j['anims'][0].get('name')
    fin = dict(name=name, fps=30, F=F, nodes=N, rot={str(i): np.round(d['rotation'], 6).ravel().tolist() for i, d in tr.items() if 'rotation' in d},
               trans={str(i): np.round(d['translation'], 4).ravel().tolist() for i, d in tr.items() if 'translation' in d})
    tmp = tempfile.mktemp(suffix='.json'); json.dump(fin, open(tmp, 'w'))
    subprocess.run(['node', fh.WRITE, tmp, dst], check=True, capture_output=True, cwd=os.path.join(fh.H, '..')); os.remove(tmp)
    print(json.dumps(dict(clip=name, out=dst, **rep)), flush=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else '-')
