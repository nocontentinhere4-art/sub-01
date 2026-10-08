"""Retarget named clips from any Sova package with the calibration of the phone Ver. 8 package (hinge axes, slot convention).
python3 -I retarget_pkg.py <ref Ver.8 package> <char.glb decoded> <out dir> <package> <set_N[=slug]>...
Writes <out dir>/<slug>.json (retarget.py's format, no phone). The slug defaults to the English name, normalized."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retarget import Retarget
from s4clip import clips_by_set, s3clip, set_names

def slug(name):
    s = re.sub(r'\[(new!?|handmade|mocap)\]', '', name, flags=re.I)
    s = re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
    return s

R = Retarget(sys.argv[1], sys.argv[2]); out = sys.argv[3]; os.makedirs(out, exist_ok=True)
ents, raw = clips_by_set(sys.argv[4]); names = set_names(ents)
for a in sys.argv[5:]:
    sid, _, sl = a.partition('=')
    nm = names.get(sid, sid); sl = sl or slug(nm)
    r = R.run(sid, clip=s3clip(raw[sid]), name=nm, phone=False); r['set'] = sl; r['source'] = [os.path.basename(sys.argv[4]), sid, nm]
    json.dump(r, open(os.path.join(out, sl + '.json'), 'w')); print(sl, '<-', sid, nm, r['frames'], 'frames')
