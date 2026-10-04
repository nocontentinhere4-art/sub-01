# Cuts the head (and the eye helpers) out of the MakeHuman default base mesh (hm08, CC0 since September 2020; see
# LICENSE.ASSETS.md in github.com/makehumancommunity/makehuman) and writes head.json in metres, the frame the
# hair is grown on. MakeHuman's units are decimetres with the origin at the body's middle (feet at y = -0.845 m).
#   python3 extract_head.py path/to/makehuman/data/3dobjs/base.obj head.json
import json, sys

src, dst = sys.argv[1], sys.argv[2]
vs, faces, grp = [], {}, None
for line in open(src):
    if line.startswith("v "):
        vs.append([float(t) for t in line.split()[1:4]])
    elif line.startswith("g "):
        grp = line[2:].strip()
    elif line.startswith("f "):
        faces.setdefault(grp, []).append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])

parts = {"head": [f for f in faces["body"] if all(vs[i][1] > 6.0 for i in f)],   # everything above the neck
         "leye": faces["helper-l-eye"], "reye": faces["helper-r-eye"]}
out = {}
for name, fs in parts.items():
    ids = sorted({i for f in fs for i in f}); m = {i: j for j, i in enumerate(ids)}
    tris = []
    for f in fs:
        g = [m[i] for i in f]
        tris += g[:3] + ([g[0], g[2], g[3]] if len(g) == 4 else [])
    out[name] = {"v": [round(c * 0.1, 5) for i in ids for c in vs[i]], "i": tris}
json.dump(out, open(dst, "w"))
