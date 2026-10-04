# blender -b -P g2_pose_check.py -- [--quick]
#
# The clothes in G2's motion: assets/g2/boy_g2_dressed.glb posed by G2's clips (clips_g2, preview/mh-motion) at the
# times COORD A asked for, skinned here exactly as three.js does (linear blend skinning: each vertex moved by its four
# joints' world x inverse-bind matrices, the clip's keys interpolated linearly, rotations by slerp), then measured:
#   - cloth inside the body: a garment vertex behind the posed body's surface (signed distance to the nearest body
#     point along that point's face normal), in mm;
#   - cloth through the chair seat (top 0.505 m above the floor, G2's measured contact) or into the mattress (top 0.66 m);
# and drawn on one sheet: each pose whole and close on its contact, the chair or the mattress in place, any offending
# garment vertex in red. Numbers to out/pose_check.json and the sheet to docs/design/clothes-mh/g2_poses.jpg.
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import glb_io as G

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in argv
DRESSED = os.path.join(HERE, "assets", "g2", "boy_g2_dressed.glb")
NAKED = os.path.join(HERE, "g2", "boy_g2.glb")                     # the full body's triangles (for the inside test)
OUTD = os.path.join(HERE, "out"); os.makedirs(OUTD, exist_ok=True)
SHEET = os.path.join(HERE, "..", "..", "docs", "design", "clothes-mh", "g2_poses.jpg")
SEAT_Y, MATTRESS_Y = 0.505, 0.66
POSES = [("rest", 0.0, None), ("desk_type_ik", 3.0, "seat"), ("room_walk", 0.3, None), ("room_bed_lie", 12.0, "bed")]
SEAT_T = 0.05                                                        # the seat is a 5 cm slab (a chair: nothing under it)
INSIDE = 0.002                                                       # more than 2 mm behind the skin counts

js, bn = G.read(DRESSED); nodes = js["nodes"]
parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
skin = js["skins"][0]; joints = skin["joints"]
IBM = G.accessor(js, bn, skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)   # column-major -> row-major
name_ix = {n.get("name"): i for i, n in enumerate(nodes)}
MESHES = {}
for n in nodes:
    if "mesh" not in n: continue
    prims = []
    for p in js["meshes"][n["mesh"]]["primitives"]:
        a = p["attributes"]
        prims.append(dict(P=G.accessor(js, bn, a["POSITION"]), J=G.accessor(js, bn, a["JOINTS_0"]).astype(int),
                          W=G.accessor(js, bn, a["WEIGHTS_0"]), I=G.accessor(js, bn, p["indices"]).reshape(-1, 3),
                          mat=js["materials"][p["material"]]["name"] if "material" in p else ""))
    MESHES[n["name"]] = prims
njs, nbn = G.read(NAKED)
FULL_BODY_I = G.accessor(njs, nbn, njs["meshes"][0]["primitives"][0]["indices"]).reshape(-1, 3)
KEPT = {tuple(sorted(t)) for t in MESHES["body"][0]["I"].tolist()}           # the triangles still shown when dressed
VISIBLE_TRI = np.array([tuple(sorted(t)) in KEPT for t in FULL_BODY_I.tolist()])


def trs(t, r, s):
    M = Quaternion((r[3], r[0], r[1], r[2])).to_matrix().to_4x4()
    for k in range(3): M.col[k] *= s[k]
    M.translation = Vector(t); return np.array(M)


def pose_matrices(clip, t):
    if clip == "rest": return np.array([np.linalg.inv(IBM[k]) @ IBM[k] for k in range(len(joints))])
    cj, cb = G.read(os.path.join(HERE, "g2", clip + ".glb")); an = cj["animations"][0]
    T = {i: list(n.get("translation", [0, 0, 0])) for i, n in enumerate(nodes)}
    R = {i: list(n.get("rotation", [0, 0, 0, 1])) for i, n in enumerate(nodes)}
    S = {i: list(n.get("scale", [1, 1, 1])) for i, n in enumerate(nodes)}
    for ch in an["channels"]:
        nm = cj["nodes"][ch["target"]["node"]]["name"]; i = name_ix.get(nm)
        if i is None: continue
        sm = an["samplers"][ch["sampler"]]; x = G.accessor(cj, cb, sm["input"]); y = G.accessor(cj, cb, sm["output"])
        k = int(np.clip(np.searchsorted(x, t) - 1, 0, len(x) - 2)); f = float(np.clip((t - x[k]) / max(x[k + 1] - x[k], 1e-9), 0, 1))
        if ch["target"]["path"] == "rotation":
            a, b = Quaternion((y[k][3], *y[k][:3])), Quaternion((y[k + 1][3], *y[k + 1][:3]))
            q = a.slerp(b, f); R[i] = [q.x, q.y, q.z, q.w]
        elif ch["target"]["path"] == "translation": T[i] = list(y[k] * (1 - f) + y[k + 1] * f)
        elif ch["target"]["path"] == "scale": S[i] = list(y[k] * (1 - f) + y[k + 1] * f)
    world = {}
    def W(i):
        if i not in world: world[i] = (W(parent[i]) if i in parent else np.eye(4)) @ trs(T[i], R[i], S[i])
        return world[i]
    return np.array([W(j) @ IBM[k] for k, j in enumerate(joints)])


def skinned(pr, M):
    v = np.c_[pr["P"], np.ones(len(pr["P"]))]; out = np.zeros((len(v), 3))
    for k in range(4):
        out += pr["W"][:, k, None] * np.einsum("nij,nj->ni", M[pr["J"][:, k]], v)[:, :3]
    return out


def inside(bvh, p):
    """inside the closed-ish body: an odd number of surface crossings, on at least two of three rays"""
    odd = 0
    for d in (Vector((0.31, 0.83, 0.46)), Vector((-0.71, -0.2, 0.67)), Vector((0.12, -0.6, -0.79))):
        n, o = 0, p.copy()
        while True:
            h = bvh.ray_cast(o, d, 3.0)
            if h[0] is None: break
            n += 1; o = h[0] + d * 1e-5
        odd += n % 2
    return odd >= 2


def B(a): return np.c_[a[:, 0], -a[:, 2], a[:, 1]]                  # glTF (y up) -> Blender (z up)


def mesh(name, P, I, mat, red=None):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(p) for p in P], [], [tuple(int(x) for x in t) for t in I]); me.update()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); me.materials.append(mat)
    if red is not None:
        ca = me.color_attributes.new("bad", 'FLOAT_COLOR', 'POINT')
        for i, r in enumerate(red): ca.data[i].color = (1, 0, 0, 1) if r else (0, 0, 0, 1)
    return o


def material(name, rgb, rough, red=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; P = nt.nodes["Principled BSDF"]
    P.inputs["Roughness"].default_value = rough
    if red:
        ca = nt.nodes.new("ShaderNodeVertexColor"); ca.layer_name = "bad"
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'
        nt.links.new(ca.outputs["Color"], mx.inputs[0]); mx.inputs[6].default_value = (*rgb, 1); mx.inputs[7].default_value = (0.9, 0.02, 0.02, 1)
        nt.links.new(mx.outputs[2], P.inputs["Base Color"])
    else: P.inputs["Base Color"].default_value = (*rgb, 1)
    return m


COL = {"hoodie_black": (0.03, 0.03, 0.032), "track_trousers": (0.022, 0.024, 0.032), "socks_white": (0.8, 0.8, 0.78),
       "slides_black": (0.02, 0.02, 0.021)}
report, shots = {}, []
bpy.ops.wm.read_factory_settings(use_empty=True); SC = bpy.context.scene
SC.render.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 16 if QUICK else 64; SC.cycles.use_denoising = True
SC.view_settings.view_transform = 'AgX'
w = bpy.data.worlds.new("w"); SC.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.52, 0.55, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
ld = bpy.data.lights.new("key", 'AREA'); ld.energy = 900; ld.size = 3; lo = bpy.data.objects.new("key", ld); lo.location = (-2, -3, 4)
lo.rotation_euler = (math.radians(45), 0, math.radians(-35)); SC.collection.objects.link(lo)
MAT_SKIN = material("skin", (0.62, 0.45, 0.36), 0.5); MAT_PROP = material("prop", (0.35, 0.33, 0.3), 0.7)
GM = {k: material(k, c, 0.8, red=True) for k, c in COL.items()}

for clip, t, contact in POSES:
    for o in list(SC.objects):
        if o.type == 'MESH': bpy.data.objects.remove(o)
    M = pose_matrices(clip, t)
    body = skinned(MESHES["body"][0], M)
    bvh = BVHTree.FromPolygons([Vector(p) for p in body], [tuple(int(x) for x in f) for f in FULL_BODY_I])
    hips = (M[joints.index(name_ix["Hips"])] @ np.linalg.inv(IBM[joints.index(name_ix["Hips"])]))[:3, 3]
    knees = [(M[joints.index(name_ix[k])] @ np.linalg.inv(IBM[joints.index(name_ix[k])]))[:3, 3] for k in ("LeftLeg", "RightLeg")]
    fwd = np.mean(knees, 0) - hips; fwd[1] = 0; fwd /= max(np.linalg.norm(fwd), 1e-6)
    rep = {"clip": clip, "t": t, "garments": {}}
    allP = [body]
    mesh("body", B(body), MESHES["body"][0]["I"], MAT_SKIN)
    for g in COL:
        rows = []
        for pr in MESHES[g]:
            P = skinned(pr, M); bad = np.zeros(len(P), bool); depth = np.zeros(len(P)); vis = np.zeros(len(P), bool)
            for i, p in enumerate(P):
                loc, nor, fi, d = bvh.find_nearest(Vector(p))
                if loc is None or d < INSIDE or d > 0.06: continue
                if inside(bvh, Vector(p)):
                    bad[i] = True; depth[i] = d; vis[i] = VISIBLE_TRI[fi]
            seat = np.zeros(len(P))
            if contact == "seat":                                    # the seat: 46 x 44 cm, its centre 12 cm in front of the hips
                c = hips + fwd * 0.05; side = np.array([-fwd[2], 0, fwd[0]])
                inbox = (np.abs((P - c) @ fwd) < 0.16) & (np.abs((P - c) @ side) < 0.2) & (P[:, 1] > SEAT_Y - SEAT_T)
                seat = np.where(inbox, np.maximum(0, SEAT_Y - P[:, 1]), 0)
            elif contact == "bed":
                seat = np.maximum(0, MATTRESS_Y - P[:, 1])
            if os.environ.get("DIAG") and contact == "seat" and (seat > 0.002).any():
                rb = MESHES["body"][0]["P"]; rbvh = BVHTree.FromPolygons([Vector(x) for x in rb], [tuple(int(x) for x in f) for f in FULL_BODY_I])
                rd = [rbvh.find_nearest(Vector(x))[3] for x in pr["P"][seat > 0.002]]
                pb = [bvh.find_nearest(Vector(x)) for x in P[seat > 0.002]]
                print("DIAGR rest gap mm", np.percentile(np.array(rd) * 1000, [0, 50, 100]).round(1), "posed gap mm", np.percentile(np.array([x[3] for x in pb]) * 1000, [0, 50, 100]).round(1),
                      "nearest body y", np.percentile(np.array([x[0][1] for x in pb]), [0, 50, 100]).round(3), "cloth y", np.percentile(P[seat > 0.002][:, 1], [0, 50, 100]).round(3))
                q = P[seat > 0.002] - hips; print("DIAGS", g, pr["mat"], int((seat > 0.002).sum()), "fwd", np.percentile(q @ fwd, [0, 50, 100]).round(3),
                      "side", np.percentile(q @ np.array([-fwd[2], 0, fwd[0]]), [0, 50, 100]).round(3), "depth", np.percentile(seat[seat > 0.002], [50, 100]).round(4))
            red = bad | (seat > 0.002 if contact == "seat" else np.zeros(len(P), bool))
            if os.environ.get("DIAG") and bad.any():
                heads = np.array([(M[k] @ np.linalg.inv(IBM[k]))[:3, 3] for k in range(len(joints))])
                near = np.argmin(((P[bad][:, None, :] - heads[None]) ** 2).sum(-1), 1)
                from collections import Counter
                print("DIAGB", clip, g, pr["mat"], Counter(nodes[joints[k]]["name"] for k in near).most_common(6), "depth p50/p90/max", np.percentile(depth[bad], [50, 90, 100]).round(4))
            if os.environ.get("DIAG") and clip == "rest" and bad.any():
                q = P[bad]; print("DIAG", g, pr["mat"], len(q), "min", q.min(0).round(3), "max", q.max(0).round(3), "depth", np.percentile(depth[bad], [50, 90, 100]).round(4))
            rows.append((P, pr, red, depth, seat, vis))
            mesh(g, B(P), pr["I"], GM[g], red)
            allP.append(P)
        n_in = int(sum(r[2].sum() for r in rows)); tot = sum(len(r[0]) for r in rows)
        rep["garments"][g] = {"verts": tot, "inside_body_over_2mm": int(sum((r[3] > INSIDE).sum() for r in rows)),
                              "inside_where_skin_shows": int(sum(r[5].sum() for r in rows)),
                              "max_inside_mm": round(1000 * max(float(r[3].max()) for r in rows), 1),
                              ("below_seat_top_mm" if contact == "seat" else "below_mattress_top_mm" if contact else "below_floor_mm"):
                              round(1000 * max(float(r[4].max()) for r in rows), 1) if contact else round(1000 * max(0.0, -min(float(r[0][:, 1].min()) for r in rows)), 1)}
    rep["body_lowest_m"] = round(float(body[:, 1].min()), 4)
    rep["garments_below_floor_mm"] = {g: round(1000 * max(0.0, -float(skinned(MESHES[g][0], M)[:, 1].min())), 1) for g in COL}
    if contact == "seat":
        c = hips + fwd * 0.05; side = np.array([-fwd[2], 0, fwd[0]])
        m = (np.abs((body - c) @ fwd) < 0.16) & (np.abs((body - c) @ side) < 0.2) & (body[:, 1] > SEAT_Y - SEAT_T)
        rep["body_below_seat_top_mm"] = round(1000 * max(0.0, SEAT_Y - float(body[m, 1].min())) if m.any() else 0.0, 1)
    report[clip] = rep; print("POSE", json.dumps(rep))
    # the props: floor, and the chair seat or the mattress
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); bpy.context.active_object.data.materials.append(MAT_PROP)
    if contact == "seat":
        c = hips + fwd * 0.08; bpy.ops.mesh.primitive_cube_add(size=1, location=(c[0], -c[2], SEAT_Y - SEAT_T / 2))
        o = bpy.context.active_object; o.scale = (0.42, 0.44, SEAT_T); o.rotation_euler[2] = math.atan2(-fwd[2], fwd[0])
        o.data.materials.append(MAT_PROP)
    elif contact == "bed":
        A = np.concatenate(allP); lo_, hi_ = A.min(0) - 0.25, A.max(0) + 0.25
        bpy.ops.mesh.primitive_cube_add(size=1, location=((lo_[0] + hi_[0]) / 2, -(lo_[2] + hi_[2]) / 2, MATTRESS_Y / 2))
        o = bpy.context.active_object; o.scale = (hi_[0] - lo_[0], hi_[2] - lo_[2], MATTRESS_Y); o.data.materials.append(MAT_PROP)
    if clip == "rest": continue
    # two views: the whole figure, and close on the contact (the hips / the back on the mattress / the legs walking)
    A = B(np.concatenate(allP)); ctr = (A.min(0) + A.max(0)) / 2; ext = float(np.max(A.max(0) - A.min(0)))
    hb = B(hips[None])[0]; fwdb = np.array([fwd[0], -fwd[2], 0])
    for view, (eye, tgt, lens) in {"whole": (ctr + np.array([-0.55, -1.0, 0.25]) * ext * 1.25, ctr, 40),
                                   "close": (hb + np.array([-1.0, -0.35, 0.1]) * 1.1 - fwdb * 0.2 + np.array([0, 0, 0.05]), hb + np.array([0, 0, -0.08]), 45)}.items():
        cd = bpy.data.cameras.new("c"); cd.lens = lens; co = bpy.data.objects.new("c", cd); SC.collection.objects.link(co)
        co.location = Vector(eye); co.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler(); SC.camera = co
        S_ = 360 if QUICK else 560; SC.render.resolution_x = S_; SC.render.resolution_y = S_
        f = os.path.join(OUTD, f"pose_{clip}_{view}.png"); SC.render.filepath = f; bpy.ops.render.render(write_still=True); shots.append(f)
        bpy.data.objects.remove(co)

json.dump(report, open(os.path.join(OUTD, "pose_check.json"), "w"), indent=1)
# the sheet: one column per pose (whole above, close below)
ims = [bpy.data.images.load(f) for f in shots]; s = ims[0].size[0]; g = 6
cols = len(POSES) - 1; Wd, Hd = cols * s + (cols - 1) * g, 2 * s + g
px = np.full((Hd, Wd, 4), [0.08, 0.08, 0.09, 1.0], np.float32)
for k, im in enumerate(ims):
    a = np.array(im.pixels[:], np.float32).reshape(s, s, 4); c, r = k // 2, 1 - k % 2      # Blender images: bottom row first
    px[r * (s + g): r * (s + g) + s, c * (s + g): c * (s + g) + s] = a
out = bpy.data.images.new("sheet", Wd, Hd, alpha=False); out.pixels = px.ravel(); out.filepath_raw = SHEET; out.file_format = 'JPEG'
SC.render.image_settings.quality = 90; out.save(); print("wrote", SHEET)
