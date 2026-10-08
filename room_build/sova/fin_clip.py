"""kimodo/mx_fit.py's output (fin.json: node indices, flat arrays) <-> retarget.py's clip JSON (node names), so the
post-fit steps (fit_rest.py) run on the fitted clip. python3 -I fin_clip.py to_clip <fin.json> <clip.json> | to_fin <clip.json> <fin.json>"""
import json, sys
import numpy as np
mode, a, b = sys.argv[1:4]
if mode == 'to_clip':
    j = json.load(open(a)); N = j['nodes']; hi = next(i for i, n in enumerate(N) if n['name'] == 'mixamorig:Hips')
    c = dict(set=j['name'], name=j['name'], hand=None, fps=j['fps'], frames=j['F'], props={},
             rot={N[int(i)]['name']: np.array(v).reshape(-1, 4).tolist() for i, v in j['rot'].items()},
             hips=np.array(j['trans'][str(hi)]).reshape(-1, 3).tolist())
    json.dump(c, open(b, 'w'))
else:
    c = json.load(open(a)); j = json.load(open(b)); N = j['nodes']; ix = {n['name']: i for i, n in enumerate(N)}
    for k, v in c['rot'].items(): j['rot'][str(ix[k])] = np.array(v).ravel().round(6).tolist()
    j['trans'][str(ix['mixamorig:Hips'])] = np.array(c['hips']).ravel().round(4).tolist()
    json.dump(j, open(b, 'w'))
