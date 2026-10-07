"""A Mixamo capture on a Mixamo-rigged character's own skeleton, by bone name, no retarget (G17; the Mixamo skeleton path
of docs/design/mixamo/README.md): the character's nodes (its rest pose), the clip's rotations on the bones of the same
name, the hips' travel scaled by the character's hip height over the clip skeleton's (as web/room/char_mixamo.js does in
the page, so the page's own scaling is then 1). Output: an exp.mjs-style json bed_clip.py reads.
python bed_src.py <character.json> <clip.json> <out.json> [from,to (s)]   (exp.mjs of the character GLB and of mixamo_glb.mjs's clip GLB;
  from,to: only that stretch of the take)"""
import json, sys, numpy as np
from rt import Skel
from bedrig import strip

ch_p, cl_p, out_p = sys.argv[1:4]
TRIM = [float(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 and sys.argv[4] else None
C, K = json.load(open(ch_p)), json.load(open(cl_p))
cn = {strip(n['name']): i for i, n in enumerate(C['nodes'])}; kn = [strip(n['name']) for n in K['nodes']]
def hip_height(d):
    s = Skel(d); P, _, _ = s.fk(s.T[None], s.R[None]); ix = {strip(n): i for i, n in enumerate(s.names)}
    feet = [P[0, ix[n]][1] for n in ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase') if n in ix]
    return P[0, ix['Hips']][1] - min(feet)
k = hip_height(C) / hip_height(K)
ch = []
for c in K['anims'][0]['ch']:
    n = kn[c['node']]
    if n not in cn: continue
    v = c['v'] if not (c['path'] == 'translation' and n == 'Hips') else (np.array(c['v']) * k).tolist()
    if c['path'] == 'translation' and n != 'Hips': continue
    t = np.array(c['t']); w = np.array(v).reshape(len(t), -1)
    if TRIM:
        keep = (t >= TRIM[0] - 1e-6) & (t <= TRIM[1] + 1e-6)
        if keep.sum() < 2: keep = np.abs(t - TRIM[0]) == np.abs(t - TRIM[0]).min()
        t, w = t[keep] - TRIM[0], w[keep]
    ch.append({'node': cn[n], 'path': c['path'], 'interp': c.get('interp', 'LINEAR'), 't': t.tolist(), 'v': w.ravel().tolist()})
miss = sorted({kn[c['node']] for c in K['anims'][0]['ch']} - set(cn))
json.dump({'nodes': C['nodes'], 'anims': [{'name': K['anims'][0]['name'], 'ch': ch}]}, open(out_p, 'w'))
print(json.dumps({'channels': len(ch), 'hips_scale': round(float(k), 4), 'clip_bones_not_on_character': miss[:10]}))
