# Fits a MakeHuman hair proxy (.mhclo + .obj, e.g. the CC0 system asset hair/short02) to the default base mesh (hm08)
# and writes it, with the head cut-out, as proxy.json in metres (the frame extract_head.py uses).
# A proxy vertex is w1*V1 + w2*V2 + w3*V3 + offset * scale over three base-mesh vertices; scale per axis is the
# base mesh's distance between the two x/y/z_scale reference vertices over the stored distance (1 on the default mesh).
#   python3 fit_proxy.py base.obj hair/short02/short02.mhclo proxy.json
import json, os, sys

base, mhclo, dst = sys.argv[1:4]
B = [[float(t) for t in l.split()[1:4]] for l in open(base) if l.startswith("v ")]
refs, scale, obj, inverts = [], [1.0, 1.0, 1.0], None, False
for line in open(mhclo):
    t = line.split()
    if not t or t[0].startswith("#"): continue
    if t[0] == "obj_file": obj = os.path.join(os.path.dirname(mhclo), t[1])
    elif t[0] in ("x_scale", "y_scale", "z_scale"):
        k = "xyz".index(t[0][0]); a, b, d = int(t[1]), int(t[2]), float(t[3])
        scale[k] = abs(B[a][k] - B[b][k]) / d
    elif t[0] == "verts": inverts = True
    elif t[0] == "delete_verts": inverts = False
    elif inverts and len(t) == 9:
        refs.append(([int(x) for x in t[:3]], [float(x) for x in t[3:6]], [float(x) for x in t[6:9]]))
    elif inverts and len(t) == 1:
        refs.append(([int(t[0])] * 3, [1.0, 0, 0], [0.0, 0, 0]))
P = []
for (ids, w, off) in refs:
    P.append([round(0.1 * (sum(w[j] * B[ids[j]][k] for j in range(3)) + off[k] * scale[k]), 6) for k in range(3)])
UV, F = [], []
for line in open(obj):
    if line.startswith("vt "): UV.append([float(x) for x in line.split()[1:3]])
    elif line.startswith("f "):
        F.append([[int(x) - 1 for x in c.split("/")[:2]] for c in line.split()[1:]])
assert len(P) == sum(1 for l in open(obj) if l.startswith("v ")), "one binding per obj vertex"
json.dump({"v": P, "uv": UV, "f": F}, open(dst, "w"))
print(len(P), "verts", len(F), "faces")
