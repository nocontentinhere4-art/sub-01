"""Lying clips for OUR bed, in the page's convention (boy_mh.js: the bed clips sit on the 0.66 m mattress, the room's 0.82
less its 0.16 floor; the page turns and places them itself, bedPlace: the head toward the headboard, the hips on the duvet).
Per clip: the hips lowered/raised so his lowest torso point over the clip lies at 0.66 - 1.5 cm of give; then written as
an animation-only GLB on char_mixamo's nodes (kimodo_g12/writeclip.mjs), as web/room/mh_mx/.
python3 -I bed_build.py <char.json> <clip.json> <out fin.json>   (then: node writeclip.mjs <fin.json> <out.glb>)"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import Body
TOP = 0.66 - 0.015
ch, cl, out = sys.argv[1:4]
B = Body(os.environ['CHAR_GLB'], vstep=8)
c = json.load(open(cl)); Wj, wm = B.joints(c); n = c['frames']
low = np.array([B.skin(Wj, f)[0][B.reg == 'torso'][:, 1].min() for f in range(0, n, 3)])
dy = TOP - low.min()
h = np.array(c['hips']); h[:, 1] += dy / 0.01; c['hips'] = h.tolist()
J = json.load(open(ch)); N = J['nodes']; ix = {nd['name']: i for i, nd in enumerate(N)}
fin = dict(name=c['set'], fps=30, F=n, nodes=[dict(name=nd['name'], parent=nd['parent'], t=nd['t'], r=nd['r'], s=nd['s']) for nd in N],
           rot={str(ix[k]): np.array(v).ravel().round(6).tolist() for k, v in c['rot'].items() if k in ix},
           trans={str(ix['mixamorig:Hips']): np.array(c['hips']).ravel().round(4).tolist()})
json.dump(fin, open(out, 'w'))
print(c['set'], 'support moved by', round(dy * 100, 1), 'cm to', TOP, 'm', flush=True)
