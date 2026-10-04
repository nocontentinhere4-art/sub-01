"""MakeHuman file formats, read and written with numpy only (runs in Blender's Python too).

- base.obj (hm08): 19158 vertices; the "body" group is the skin, the rest are helpers (tights, joints, eyes).
- .target: "index dx dy dz" lines (a morph on the base mesh).
- .mhclo: a clothing proxy. Each clothing vertex is a weighted sum of three body vertices plus an offset; the offset
  is scaled per axis by the ratio of a measured body distance to the one stored in the file (x_scale / y_scale /
  z_scale lines: "vidx1 vidx2 distance"), exactly as MakeHuman's shared/proxy.py does it. delete_verts lists the body
  vertices the garment hides.
- .mhskel / .mhw: the default skeleton (joint positions are the means of body vertex sets) and its skin weights.

All coordinates are in MakeHuman units (decimetres), y up.
"""
import json
import numpy as np


def read_obj(path, groups=None):
    """vertices (N,3), faces (list of index lists) of the wanted groups (None: all), uvs (M,2), face uv indices"""
    V, VT, F, FT = [], [], [], []
    cur = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g ") or line.startswith("o "):
            cur = line.split(None, 1)[1].strip()
        elif line.startswith("f "):
            if groups is not None and cur not in groups:
                continue
            idx, tdx = [], []
            for tok in line.split()[1:]:
                p = tok.split("/")
                idx.append(int(p[0]) - 1)
                tdx.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
            F.append(idx); FT.append(tdx)
    return np.array(V, float), F, np.array(VT, float) if VT else np.zeros((0, 2)), FT


def read_target(path):
    idx, d = [], []
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        idx.append(int(p[0])); d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, int), np.array(d, float)


def apply_targets(coords, targets):
    out = coords.copy()
    for path, w in targets:
        i, d = read_target(path)
        out[i] += w * d
    return out


def _ranges(tokens):
    out, k = [], 0
    while k < len(tokens):
        if k + 2 < len(tokens) and tokens[k + 1] == "-":
            out.extend(range(int(tokens[k]), int(tokens[k + 2]) + 1)); k += 3
        else:
            out.append(int(tokens[k])); k += 1
    return out


def read_mhclo(path):
    """{'ref': (N,3) int, 'w': (N,3), 'off': (N,3), 'scale': [(v1, v2, d) x3], 'delete': [...], 'header': {...}}"""
    hdr, ref, w, off, scale, delete = {}, [], [], [], [None, None, None], []
    mode = None
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        if p[0] == "verts":
            mode = "verts"; continue
        if p[0] == "delete_verts":
            mode = "delete"; continue
        if mode == "verts":
            if len(p) == 1:                                 # exact: one body vertex
                ref.append([int(p[0])] * 3); w.append([1.0, 0, 0]); off.append([0.0, 0, 0])
            elif len(p) >= 9:
                ref.append([int(x) for x in p[0:3]]); w.append([float(x) for x in p[3:6]]); off.append([float(x) for x in p[6:9]])
            else:
                mode = None
            if mode:
                continue
        if mode == "delete":
            if p[0][0].isdigit() or p[0] == "-":
                delete.extend(_ranges(p)); continue
            mode = None
        key = p[0]
        if key in ("x_scale", "y_scale", "z_scale"):
            scale["xyz".index(key[0])] = (int(p[1]), int(p[2]), float(p[3]))
        else:
            hdr.setdefault(key, []).append(" ".join(p[1:]))
    return {"ref": np.array(ref, int), "w": np.array(w, float), "off": np.array(off, float), "scale": scale,
            "delete": delete, "header": hdr}


def scale_matrix(body, scale):
    m = np.identity(3)
    for n, e in enumerate(scale):
        if e is None:
            continue
        v1, v2, den = e
        m[n, n] = abs(body[v1][n] - body[v2][n]) / den
    return m


def fit(mhclo, body):
    """clothing vertex coordinates on this body (MakeHuman's Proxy.getCoords)"""
    r, w = mhclo["ref"], mhclo["w"]
    m = scale_matrix(body, mhclo["scale"])
    return (body[r[:, 0]] * w[:, 0, None] + body[r[:, 1]] * w[:, 1, None] + body[r[:, 2]] * w[:, 2, None]
            + mhclo["off"] @ m.T)


def _closest_on_triangle(p, a, b, c):
    """closest point on triangle abc to p, as barycentric (u, v, w) (Ericson, Real-Time Collision Detection 5.1.5)"""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0: return (1.0, 0.0, 0.0)
    bp = p - b; d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3: return (0.0, 1.0, 0.0)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3); return (1 - v, v, 0.0)
    cp = p - c; d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6: return (0.0, 0.0, 1.0)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6); return (1 - w, 0.0, w)
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); return (0.0, 1 - w, w)
    den = 1.0 / (va + vb + vc); v = vb * den; w = vc * den
    return (1 - v - w, v, w)


def bind(points, body, tris, scale, nearest):
    """a .mhclo binding for garment points made on this body: for each point the closest body triangle (nearest(p) ->
    candidate triangle indices), its barycentric weights and the offset, the offset stored unscaled at this body
    (the scale lines' distances are measured on it, so the matrix is the identity here)"""
    ref, w, off = [], [], []
    for p in points:
        best = None
        for t in nearest(p):
            a, b, c = body[tris[t][0]], body[tris[t][1]], body[tris[t][2]]
            bc = _closest_on_triangle(p, a, b, c)
            q = a * bc[0] + b * bc[1] + c * bc[2]
            d = float(((p - q) ** 2).sum())
            if best is None or d < best[0]:
                best = (d, tris[t], bc, q)
        _, tri, bc, q = best
        ref.append(list(tri)); w.append(list(bc)); off.append(list(p - q))
    sc = [(v1, v2, abs(body[v1][n] - body[v2][n])) for n, (v1, v2, _) in enumerate(scale)]
    return {"ref": np.array(ref, int), "w": np.array(w, float), "off": np.array(off, float), "scale": sc}


def _range_text(ids):
    ids = sorted(set(int(i) for i in ids)); out, k = [], 0
    while k < len(ids):
        j = k
        while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1: j += 1
        out.append(f"{ids[k]} - {ids[j]}" if j > k else f"{ids[k]}"); k = j + 1
    lines, cur = [], ""
    for t in out:
        if len(cur) + len(t) > 100: lines.append(cur.strip()); cur = ""
        cur += t + " "
    if cur.strip(): lines.append(cur.strip())
    return "\n".join(lines)


HEADER = """# This is a clothes file for MakeHuman (a proxy fitted to the hm08 base mesh).
#
# Made for SUB-01 by room_build/clothes_mh/build_clothes.py and released under CC0 1.0
# (https://creativecommons.org/publicdomain/zero/1.0/). {origin}
#
"""


def write_mhclo(path, name, uuid, binding, delete, obj_file, material, tags, origin, z_depth=50):
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER.format(origin=origin))
        f.write(f"uuid {uuid}\nbasemesh hm08\n")
        for t in tags: f.write(f"tag {t}\n")
        f.write(f"\nname {name}\nobj_file {obj_file}\n")
        for n, (v1, v2, d) in enumerate(binding["scale"]):
            f.write(f"{'xyz'[n]}_scale {v1} {v2} {d:.4f}\n")
        f.write(f"z_depth {z_depth}\nmaterial {material}\nverts 0\n")
        for r, w, o in zip(binding["ref"], binding["w"], binding["off"]):
            f.write(f"{r[0]} {r[1]} {r[2]} {w[0]:.5f} {w[1]:.5f} {w[2]:.5f} {o[0]:.5f} {o[1]:.5f} {o[2]:.5f}\n")
        if len(delete):
            f.write("\ndelete_verts\n" + _range_text(delete) + "\n")


def write_obj(path, V, F, UV=None, FT=None, groups=None):
    """F: faces (index lists); groups: per-face group names (one "g" line per run)"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("# CC0 1.0, made for SUB-01 by room_build/clothes_mh/build_clothes.py\n")
        for v in V: f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
        if UV is not None:
            for t in UV: f.write(f"vt {t[0]:.5f} {t[1]:.5f}\n")
        last = None
        for k, face in enumerate(F):
            g = groups[k] if groups else None
            if g != last: f.write(f"g {g}\n"); last = g
            if UV is not None:
                f.write("f " + " ".join(f"{i + 1}/{t + 1}" for i, t in zip(face, FT[k])) + "\n")
            else:
                f.write("f " + " ".join(str(i + 1) for i in face) + "\n")


def write_mhmat(path, name, diffuse_rgb, normal=None, normal_intensity=1.0, roughness=0.9, extra=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# CC0 1.0, made for SUB-01 by room_build/clothes_mh/build_clothes.py\n")
        f.write(f"name {name}\ndiffuseColor {diffuse_rgb[0]:.4f} {diffuse_rgb[1]:.4f} {diffuse_rgb[2]:.4f}\n")
        f.write("specularColor 0.03 0.03 0.03\n")
        f.write(f"shininess {1 - roughness:.3f}\nopacity 1.0\ntranslucency 0.0\nbackfaceCull False\n")
        if normal:
            f.write(f"normalmapTexture {normal}\nnormalmapIntensity {normal_intensity:.2f}\n")
            f.write("shaderConfig normal True\n")
        f.write("shaderConfig diffuse True\n" + extra)


def read_skeleton(skel_path, body):
    d = json.load(open(skel_path))
    joints = {k: body[np.array(v, int)].mean(axis=0) for k, v in d["joints"].items()}
    bones = {}
    for name, b in d["bones"].items():
        bones[name] = {"head": joints[b["head"]], "tail": joints[b["tail"]], "parent": b.get("parent")}
    return bones


def read_weights(path):
    d = json.load(open(path))["weights"]
    return {bone: (np.array([x[0] for x in vw], int), np.array([x[1] for x in vw], float)) for bone, vw in d.items()}
