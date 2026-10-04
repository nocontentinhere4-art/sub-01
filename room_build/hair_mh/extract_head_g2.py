# Cuts the head out of G2's body (room_build/mh/glb/boy_g2.glb on preview/mh-motion: MakeHuman base.obj + macro
# targets, metres, feet at y = 0) for growing the hair on. The GLB keeps base.obj's vertex order (the "body" group's
# vertices, sorted), so the head is picked by base.obj's own indices, exactly as extract_head.py does. The hair
# generator's hairline, ear and whorl settings are written for the default head (extract_head.py's frame), so the G2
# head is mapped into that frame by the least-squares scale + offset between the two (same topology), and the map
# is stored for taking the strands back.
#   python3 extract_head_g2.py base.obj boy_g2.glb boy_g2_rest.json head_g2.json
import json, struct, sys

base, glb, rest, dst = sys.argv[1:5]
B, faces, grp = [], [], None
for line in open(base):
    if line.startswith("v "): B.append([float(t) for t in line.split()[1:4]])
    elif line.startswith("g "): grp = line[2:].strip()
    elif line.startswith("f ") and grp == "body": faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
used = sorted({i for f in faces for i in f}); remap = {v: i for i, v in enumerate(used)}

b = open(glb, "rb").read(); n = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + n])
binstart = 20 + n + 8
acc = j["accessors"][j["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
bv = j["bufferViews"][acc["bufferView"]]
assert acc["componentType"] == 5126 and acc["type"] == "VEC3", "float positions expected"
off = binstart + bv.get("byteOffset", 0) + acc.get("byteOffset", 0); stride = bv.get("byteStride", 12)
G = [list(struct.unpack_from("<3f", b, off + i * stride)) for i in range(acc["count"])]

head = [f for f in faces if all(B[i][1] > 6.0 for i in f)]
ids = sorted({i for f in head for i in f}); m = {i: k for k, i in enumerate(ids)}
bp = [[c * 0.1 for c in B[i]] for i in ids]; gp = [G[remap[i]] for i in ids]
bc = [sum(p[k] for p in bp) / len(bp) for k in range(3)]; gc = [sum(p[k] for p in gp) / len(gp) for k in range(3)]
num = sum(sum((g[k] - gc[k]) * (p[k] - bc[k]) for k in range(3)) for g, p in zip(gp, bp))
den = sum(sum((p[k] - bc[k]) ** 2 for k in range(3)) for p in bp)
s = num / den; t = [gc[k] - s * bc[k] for k in range(3)]               # G2 ~ s * base + t
tris = []
for f in head:
    g = [m[i] for i in f]; tris += g[:3] + ([g[0], g[2], g[3]] if len(g) == 4 else [])
inv = lambda p: [round((p[k] - t[k]) / s, 6) for k in range(3)]
err = max(sum((inv(g)[k] - p[k]) ** 2 for k in range(3)) ** 0.5 for g, p in zip(gp, bp))
R = json.load(open(rest))
out = {"head": {"v": [c for g in gp for c in inv(g)], "i": tris},
       "map": {"s": s, "t": t, "note": "G2 metres = s * this frame + t"},
       "headBone": R["head"]["head"], "headBoneTail": R["tail"]["head"]}
# the eyes: the GLB's second primitive (MakeHuman's high-poly eyeballs with their iris colours), for the stand-in render
def read(ai):
    a = j["accessors"][ai]; v = j["bufferViews"][a["bufferView"]]
    comp = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2)}[a["componentType"]]; k = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
    st = v.get("byteStride", comp[1] * k); o = binstart + v.get("byteOffset", 0) + a.get("byteOffset", 0)
    return [list(struct.unpack_from("<%d%s" % (k, comp[0]), b, o + i * st)) for i in range(a["count"])]
ep = j["meshes"][0]["primitives"][1]
EP, EC, EI = read(ep["attributes"]["POSITION"]), read(ep["attributes"]["COLOR_0"]), [i[0] for i in read(ep["indices"])]
used_e = sorted(set(EI)); em = {v: k for k, v in enumerate(used_e)}
out["eyes"] = {"v": [c for i in used_e for c in inv(EP[i])], "c": [round(c, 4) for i in used_e for c in EC[i]], "i": [em[i] for i in EI]}
json.dump(out, open(dst, "w"))
print("verts", len(ids), "scale", round(s, 5), "offset", [round(x, 4) for x in t], "max shape difference after the map (m, base frame)", round(err, 4))
