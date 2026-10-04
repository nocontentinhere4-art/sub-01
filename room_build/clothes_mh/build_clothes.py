# blender -b -P build_clothes.py -- --mh <makehuman/data> --sys <system assets> --tex <room_build/tex> [--quick] [--no-render]
#
# His clothes, fitted to the MakeHuman base body (hm08) and written as MakeHuman clothes (.mhclo + .obj + .mhmat), so
# they follow any body shape made from that base: a black cotton hoodie (hood down, drawstrings, kangaroo pocket, ribbed
# cuffs and hem, weight folds at the elbows and the hem), dark track trousers with a side stripe and gathered cuffs,
# white crew socks and black slides. Then a still sheet: standing, seated at a desk typing, and two fabric close-ups.
#
# Sources (all CC0, see README.md): the hm08 base mesh, the asian-male-young macro target, the default skeleton and its
# weights (makehumancommunity/makehuman, LICENSE.ASSETS.md: CC0); the shapes of the hoodie's body and sleeves and of
# the trousers start from MakeHuman's system asset male_casualsuit02 (CC0 since 2020), reworked here; the fabric normal
# maps are Poly Haven's (CC0). Everything this script makes is released under CC0.
#
# Coordinates: MakeHuman files are in decimetres, y up, the body facing +z. In Blender the same numbers are used
# (1 unit = 1 dm) with z up and the body facing -y: B(x, y, z) = (x, -z, y).
import bpy, bmesh, sys, os, math, random, uuid, json
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mh_io as M

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
MH = arg("--mh", "/home/user/mh/mh/makehuman/data")
SYS = arg("--sys", "/home/user/mh/sys")
TEX = arg("--tex", os.path.join(HERE, "..", "tex"))
OUT = arg("--out", os.path.join(HERE, "assets"))
SHEET_DIR = arg("--shots", os.path.join(HERE, "out"))
QUICK = "--quick" in argv
RENDER = "--no-render" not in argv
os.makedirs(OUT, exist_ok=True); os.makedirs(SHEET_DIR, exist_ok=True)
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
CM = 0.1                                                       # one centimetre in MakeHuman units


def B(p): return Vector((p[0], -p[2], p[1]))                   # MakeHuman -> Blender
def MHv(v): return np.array([v[0], v[2], -v[1]])               # Blender -> MakeHuman
def smooth01(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else float(x >= b); return t * t * (3 - 2 * t)


# ================================================================ the body
base, BODY_F, _, _ = M.read_obj(f"{MH}/3dobjs/base.obj", groups={"body"})
REST = M.apply_targets(base, [(f"{MH}/targets/macrodetails/asian-male-young.target", 1.0)])   # a young man
NV = len(REST)
BODY_IDS = sorted({i for f in BODY_F for i in f})                 # the skin's vertices (the rest are helpers)
BODY_TRIS = []
for f in BODY_F:
    for k in range(1, len(f) - 1): BODY_TRIS.append((f[0], f[k], f[k + 1]))


def mesh_obj(name, verts, faces, mats=(), smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], [list(f) for f in faces]); me.update()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o)
    for m in mats: me.materials.append(m)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    return o


body = mesh_obj("body", [B(p) for p in REST], BODY_F)
BODY_BVH = BVHTree.FromPolygons([B(p) for p in REST], BODY_TRIS)

# the skeleton and its weights
SKEL = M.read_skeleton(f"{MH}/rigs/default.mhskel", REST)
WEIGHTS = M.read_weights(f"{MH}/rigs/default_weights.mhw")
arm_data = bpy.data.armatures.new("rig"); RIG = bpy.data.objects.new("rig", arm_data); SC.collection.objects.link(RIG)
bpy.context.view_layer.objects.active = RIG; bpy.ops.object.mode_set(mode='EDIT')
for name, b in SKEL.items():
    eb = arm_data.edit_bones.new(name); eb.head = B(b["head"]); eb.tail = B(b["tail"])
    if (eb.tail - eb.head).length < 1e-4: eb.tail = eb.head + Vector((0, 0, 0.05))
for name, b in SKEL.items():
    if b["parent"]: arm_data.edit_bones[name].parent = arm_data.edit_bones[b["parent"]]
bpy.ops.object.mode_set(mode='OBJECT')
BONES = list(SKEL)
WMAT = np.zeros((NV, len(BONES)), np.float32)                  # body vertex x bone
for j, bn in enumerate(BONES):
    if bn in WEIGHTS: idx, w = WEIGHTS[bn]; WMAT[idx, j] = w
WMAT /= np.maximum(WMAT.sum(1, keepdims=True), 1e-9)


def skin(o, wmat):
    """vertex groups from a (nverts x bones) weight matrix, and an armature modifier"""
    for j, bn in enumerate(BONES):
        col = wmat[:, j]; nz = np.nonzero(col > 1e-4)[0]
        if not len(nz): continue
        g = o.vertex_groups.new(name=bn)
        for i in nz: g.add([int(i)], float(col[i]), 'REPLACE')
    m = o.modifiers.new("rig", "ARMATURE"); m.object = RIG
    o.modifiers.move(len(o.modifiers) - 1, 0)


skin(body, WMAT)
SK = {n: (SKEL[n]["head"], SKEL[n]["tail"]) for n in SKEL}
def J(name, end="head"): return B(SK[name][0 if end == "head" else 1])


# ================================================================ helpers on Blender meshes
def verts_np(o): return np.array([v.co[:] for v in o.data.vertices])
def set_verts(o, P):
    for v, p in zip(o.data.vertices, P): v.co = p
    o.data.update()
def normals_np(o): o.data.update(); return np.array([v.normal[:] for v in o.data.vertices])


def subdivide(o, levels=1):
    m = o.modifiers.new("sub", "SUBSURF"); m.levels = levels; m.subdivision_type = 'CATMULL_CLARK'
    m.boundary_smooth = 'PRESERVE_CORNERS'
    bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=m.name)


def boundary_loops(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    edges = [e for e in bm.edges if e.is_boundary]; adj = {}
    for e in edges:
        a, b = e.verts[0].index, e.verts[1].index
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for s in adj:
        if s in seen: continue
        loop, prev, cur = [s], None, s; seen.add(s)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        loops.append(loop)
    bm.free(); return loops


def bvh_of(o):
    return BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])


def march(bvh, start, direction, length, step=0.08, down_from=0.0, lift=0.0, grav=Vector((0, 0, -1))):
    """walk over a surface from start: each step goes `step` along the current direction (turned towards the downhill
    tangent after `down_from`), then back onto the surface; returns the points (lifted by lift(s) along the normal)"""
    pts, p, d, s = [], start.copy(), direction.normalized(), 0.0
    loc, nor, _, _ = bvh.find_nearest(p); p = loc
    while s <= length + 1e-6:
        loc, nor, _, _ = bvh.find_nearest(p)
        h = lift(s) if callable(lift) else lift
        pts.append(loc + nor * h)
        if s > down_from:
            t = grav - nor * grav.dot(nor)
            if t.length > 1e-6: d = (d * 0.75 + t.normalized() * 0.25).normalized()
        d = (d - nor * d.dot(nor)); d = d.normalized() if d.length > 1e-6 else d
        p = loc + d * step; s += step
    return pts


def tube(name, pts, r, mat, n=8, cap=True):
    """a round tube through points (Blender coords)"""
    bm = bmesh.new(); rings = []
    for k, c in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        a = t.orthogonal().normalized(); b = t.cross(a)
        rk = r(k / max(1, len(pts) - 1)) if callable(r) else r
        rings.append([bm.verts.new(c + (a * math.cos(2 * math.pi * i / n) + b * math.sin(2 * math.pi * i / n)) * rk) for i in range(n)])
    for k in range(len(rings) - 1):
        for i in range(n): bm.faces.new([rings[k][i], rings[k][(i + 1) % n], rings[k + 1][(i + 1) % n], rings[k + 1][i]]).smooth = True
    if cap: bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return o


def grid_obj(name, rows, mat, flip=False):
    bm = bmesh.new(); V = [[bm.verts.new(p) for p in row] for row in rows]
    for j in range(len(V) - 1):
        for i in range(len(V[j]) - 1):
            q = [V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i]]
            bm.faces.new(q[::-1] if flip else q).smooth = True
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return o


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.context.view_layer.objects.active = objs[0]
    for o in objs: o.select_set(True)
    bpy.ops.object.join(); objs[0].name = name; objs[0].data.name = name; return objs[0]


def push_out(o, gap=0.025, iters=2):
    """no garment vertex inside the (rest) body: any vertex closer than `gap` to the skin, or behind it, goes out along
    the skin's normal to `gap`"""
    P = verts_np(o); moved = 0
    for _ in range(iters):
        for i, p in enumerate(P):
            loc, nor, _, d = BODY_BVH.find_nearest(Vector(p))
            if loc is None: continue
            s = (Vector(p) - loc).dot(nor)
            if s < gap: P[i] = np.array(loc + nor * gap); moved += 1
    set_verts(o, P); return moved


# ================================================================ materials (Cycles; the sheet) and their tiled normal maps
def tex_path(asset, kind="nor_gl"):
    for ext in ("jpg", "png"):
        p = f"{TEX}/{asset}/{kind}.{ext}" if kind != "Diffuse" else f"{TEX}/{asset}/Diffuse.{ext}"
        if os.path.exists(p): return p
    raise FileNotFoundError(f"{TEX}/{asset}/{kind}")


def fabric(name, rgb, rough, normal_asset=None, tile=0.3, nstr=1.0, sheen=0.0, sheen_tint=(0.5, 0.5, 0.5), melange=None, mel_amt=0.25, spec=0.4, stitch=0.0, bump=0.35):
    """a fabric in Cycles: the tiled normal map (and a melange tone) box-projected in object space, 1 tile = `tile` dm"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; P = nt.nodes["Principled BSDF"]
    P.inputs["Base Color"].default_value = (*rgb, 1); P.inputs["Roughness"].default_value = rough
    P.inputs["Specular IOR Level"].default_value = spec
    if sheen:
        P.inputs["Sheen Weight"].default_value = sheen; P.inputs["Sheen Roughness"].default_value = 0.45
        P.inputs["Sheen Tint"].default_value = (*sheen_tint, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / tile,) * 3
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    knit = m_knit = None
    if normal_asset:
        it = nt.nodes.new("ShaderNodeTexImage"); it.image = bpy.data.images.load(tex_path(normal_asset), check_existing=True)
        it.image.colorspace_settings.name = "Non-Color"; it.projection = 'BOX'; it.projection_blend = 0.3
        nt.links.new(mp.outputs["Vector"], it.inputs["Vector"])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nstr
        nt.links.new(it.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], P.inputs["Normal"])
        if stitch:
            # jersey: columns of V stitches, `stitch` dm apart (a wave along x with a zig-zag along z), plus fuzz
            sc = nt.nodes.new("ShaderNodeMapping"); sc.inputs["Scale"].default_value = (1 / stitch, 1 / stitch, 1 / stitch)
            nt.links.new(tc.outputs["Object"], sc.inputs["Vector"])
            sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(sc.outputs["Vector"], sep.inputs["Vector"])
            fz = nt.nodes.new("ShaderNodeMath"); fz.operation = 'PINGPONG'; fz.inputs[1].default_value = 0.5; nt.links.new(sep.outputs["Z"], fz.inputs[0])
            u = nt.nodes.new("ShaderNodeMath"); u.operation = 'ADD'; nt.links.new(sep.outputs["X"], u.inputs[0]); nt.links.new(fz.outputs[0], u.inputs[1])
            u2 = nt.nodes.new("ShaderNodeMath"); u2.operation = 'ADD'; nt.links.new(sep.outputs["Y"], u2.inputs[0]); nt.links.new(u.outputs[0], u2.inputs[1])
            w = nt.nodes.new("ShaderNodeMath"); w.operation = 'SINE'
            k = nt.nodes.new("ShaderNodeMath"); k.operation = 'MULTIPLY'; k.inputs[1].default_value = 2 * math.pi
            nt.links.new(u2.outputs[0], k.inputs[0]); nt.links.new(k.outputs[0], w.inputs[0])
            ns = nt.nodes.new("ShaderNodeTexNoise"); ns.inputs["Scale"].default_value = 1 / (stitch * 0.6); ns.inputs["Detail"].default_value = 6
            nt.links.new(tc.outputs["Object"], ns.inputs["Vector"])
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = 'MULTIPLY_ADD'; mx.inputs[1].default_value = 0.6
            nt.links.new(w.outputs[0], mx.inputs[0]); nt.links.new(ns.outputs["Fac"], mx.inputs[2])
            bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = stitch * 0.25
            nt.links.new(mx.outputs[0], bp.inputs["Height"]); nt.links.new(nm.outputs["Normal"], bp.inputs["Normal"])
            nt.links.new(bp.outputs["Normal"], P.inputs["Normal"])
    if melange:
        dt = nt.nodes.new("ShaderNodeTexImage"); dt.image = bpy.data.images.load(tex_path(melange, "Diffuse"), check_existing=True)
        dt.projection = 'BOX'; dt.projection_blend = 0.3; nt.links.new(mp.outputs["Vector"], dt.inputs["Vector"])
        bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(dt.outputs["Color"], bw.inputs["Color"])
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 1 - mel_amt; mr.inputs["To Max"].default_value = 1 + mel_amt
        nt.links.new(bw.outputs["Val"], mr.inputs["Value"])
        mx = nt.nodes.new("ShaderNodeMixRGB"); mx.blend_type = 'MULTIPLY'; mx.inputs["Fac"].default_value = 1.0
        mx.inputs["Color1"].default_value = (*rgb, 1); nt.links.new(mr.outputs["Result"], mx.inputs["Color2"])
        nt.links.new(mx.outputs["Color"], P.inputs["Base Color"])
    m["tile"] = tile; m["normal_asset"] = normal_asset or ""; m["rgb"] = list(rgb); m["rough"] = rough
    return m


# the fabrics: tileable colour and normal maps baked once (fabric_bake.py: Poly Haven's photo normal + a procedural
# jersey stitch for the knits), mapped by the garments' box-projected UVs (one UV tile = `tile` dm of cloth). The same
# maps go into the .mhmat files and the web materials, so the sheet shows what a web material shows.
import fabric_bake
TEXOUT = os.path.join(OUT, "textures"); os.makedirs(TEXOUT, exist_ok=True)
FABRICS = {   # tile dm, linear rgb, rough, sheen (weight, tint), Poly Haven normal + strength, melange, knit stitches per tile, size
    "fleece":  dict(tile=0.9, rgb=(0.02, 0.02, 0.022), rough=0.9, sheen=(1.0, 0.22), normal="jersey_melange", nstr=1.4, melange="jogging_melange", mel_amt=0.5, cols=41, rows=41, kstr=1.2, size=1024),
    "rib":     dict(tile=0.35, rgb=(0.017, 0.017, 0.019), rough=0.92, sheen=(1.0, 0.2), normal="ribbed_corduroy", nstr=1.8, cols=12, rows=12, kstr=1.5, size=512),
    "cord":    dict(tile=0.2, rgb=(0.035, 0.035, 0.037), rough=0.75, sheen=(0.6, 0.2), normal="jersey_melange", nstr=0.8, size=256),
    "track":   dict(tile=0.8, rgb=(0.016, 0.018, 0.025), rough=0.62, sheen=(0.5, 0.16), normal="bi_stretch", nstr=1.0, size=512),
    "stripe":  dict(tile=0.8, rgb=(0.6, 0.6, 0.58), rough=0.65, sheen=(0.0, 0.0), normal="bi_stretch", nstr=0.8, size=256),
    "sock":    dict(tile=0.5, rgb=(0.8, 0.8, 0.78), rough=0.97, sheen=(0.7, 0.5), normal="knitted_fleece", nstr=1.2, cols=20, rows=20, kstr=1.0, size=512),
    "sockrib": dict(tile=0.25, rgb=(0.78, 0.78, 0.76), rough=0.97, sheen=(0.7, 0.5), normal="ribbed_corduroy", nstr=1.6, cols=8, rows=8, kstr=1.2, size=256),
    "eva":     dict(tile=1.2, rgb=(0.02, 0.02, 0.022), rough=0.62, sheen=(0.0, 0.0), normal="hessian_380", nstr=0.25, size=256),
}


def uv_fabric(name, f):
    cp, npth = fabric_bake.bake(name, f, TEX, TEXOUT)
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; P = nt.nodes["Principled BSDF"]
    P.inputs["Roughness"].default_value = f["rough"]; P.inputs["Specular IOR Level"].default_value = 0.15
    if f["sheen"][0]:
        P.inputs["Sheen Weight"].default_value = f["sheen"][0]; P.inputs["Sheen Roughness"].default_value = 0.45
        P.inputs["Sheen Tint"].default_value = (f["sheen"][1],) * 3 + (1,)
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    ci = nt.nodes.new("ShaderNodeTexImage"); ci.image = bpy.data.images.load(cp); nt.links.new(uvn.outputs["UV"], ci.inputs["Vector"])
    nt.links.new(ci.outputs["Color"], P.inputs["Base Color"])
    ni = nt.nodes.new("ShaderNodeTexImage"); ni.image = bpy.data.images.load(npth); ni.image.colorspace_settings.name = "Non-Color"
    nt.links.new(uvn.outputs["UV"], ni.inputs["Vector"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(ni.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], P.inputs["Normal"])
    m["tile"] = f["tile"]; m["rgb"] = list(f["rgb"]); m["rough"] = f["rough"]; m["color_map"] = cp; m["normal_map"] = npth
    return m


MAT = {k: uv_fabric(k, f) for k, f in FABRICS.items()}
MAT.update({
    "skin": fabric("skin", (0.52, 0.36, 0.28), 0.5, spec=0.35),
    "aglet": fabric("aglet", (0.02, 0.02, 0.02), 0.3, spec=0.5),
    "studio": fabric("studio", (0.42, 0.42, 0.42), 0.8),
    "desk": fabric("desk", (0.3, 0.3, 0.3), 0.6),
})
body.data.materials.append(MAT["skin"])


# ================================================================ the CC0 suit, fitted to this body, split into shirt and jeans
SUIT = M.read_mhclo(f"{SYS}/clothes/male_casualsuit02/male_casualsuit02.mhclo")
SV, SF, _, _ = M.read_obj(f"{SYS}/clothes/male_casualsuit02/male_casualsuit02.obj")
SP = M.fit(SUIT, REST)
par = list(range(len(SP)))
def find(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for f in SF:
    for a, b2 in zip(f, f[1:] + f[:1]): par[find(a)] = find(b2)
comps = {}
for i in range(len(SP)): comps.setdefault(find(i), []).append(i)
comps = sorted(comps.values(), key=lambda c: -SP[c, 1].max())
def part(ids, name, mats):
    s = set(ids); remap = {v: k for k, v in enumerate(ids)}
    faces = [[remap[i] for i in f] for f in SF if f[0] in s]
    return mesh_obj(name, [B(SP[i]) for i in ids], faces, mats)
SHIRT_SRC, JEANS_SRC = comps[0], comps[1]


# ================================================================ the hoodie
def sleeve_param(p):
    """(side, s along the arm from the shoulder in dm, distance to the arm axis, the nearest axis point, unit axis) or None"""
    best = None
    for side in ("L", "R"):
        chain = [J(f"upperarm01.{side}"), J(f"lowerarm01.{side}"), J(f"lowerarm02.{side}", "tail")]
        acc = 0.0
        for a, b2 in zip(chain, chain[1:]):
            ab = b2 - a; t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared)); q = a + ab * t
            d = (p - q).length
            if best is None or d < best[2]: best = (side, acc + t * ab.length, d, q, ab.normalized())
            acc += ab.length
    return best


def hoodie():
    o = part(SHIRT_SRC, "hoodie_body", [MAT["fleece"], MAT["rib"]]); subdivide(o, 1)
    P = verts_np(o); N = normals_np(o)
    shoulder_x = abs(J("upperarm01.L")[0])
    arm_len = (J("upperarm01.L") - J("lowerarm01.L")).length + (J("lowerarm01.L") - J("lowerarm02.L", "tail")).length
    elbow_s = (J("upperarm01.L") - J("lowerarm01.L")).length
    hem_z = P[:, 2].min(); chest_z = J("spine02")[2]
    out = P.copy(); sleeve = np.zeros(len(P), bool); cuffzone = np.zeros(len(P), bool); hemzone = np.zeros(len(P), bool)
    torso_axis = Vector((0, J("spine03")[1], 0))
    for i, (p, n) in enumerate(zip(P, N)):
        p = Vector(p); n = Vector(n)
        sp = sleeve_param(p); is_sleeve = abs(p.x) > shoulder_x - 0.15 and sp[1] > 0.4
        d = 1.3 * CM                                                             # fleece is roomier than a tee
        if is_sleeve:
            sleeve[i] = True; side, s, dist, q, ax = sp
            from_wrist = arm_len - s
            r = (p - q); r = r - ax * r.dot(ax)
            front = Vector((0, -1, 0)); front = (front - ax * front.dot(ax)).normalized()
            phi = math.atan2(r.normalized().cross(front).dot(ax), r.normalized().dot(front)) if r.length > 1e-6 else 0.0
            d = 1.1 * CM + 0.5 * CM * max(0.0, -r.normalized().z)                 # the sleeve's weight sags under the arm
            # elbow: diagonal wrinkles on the inner side, fanning out from the crease
            e = math.exp(-((s - elbow_s) / (0.55)) ** 2) * max(0.0, math.cos(phi)) ** 1.5
            d += e * 0.85 * CM * math.sin(2 * math.pi * (s - elbow_s) / 0.26 + 2.2 * phi)
            d += 0.4 * CM * math.exp(-((s - elbow_s) / 0.8) ** 2) * max(0.0, -math.cos(phi)) * math.sin(3 * phi + 6 * s)   # bunching at the back of the elbow
            # stacking above the cuff: the sleeve is longer than the arm and bunches on the forearm
            w = smooth01(0.45, 0.7, from_wrist) * (1 - smooth01(1.4, 1.9, from_wrist))
            d += w * 0.7 * CM * math.sin(2 * math.pi * from_wrist / 0.3 + 0.9 * math.sin(2 * phi + s))
            if from_wrist < 0.55:                                                  # the ribbed cuff hugs the wrist
                cuffzone[i] = True; d = -0.25 * CM
        else:
            th = math.atan2(p.x, -p.y)                                             # around the body, 0 at the front
            hz = p.z - hem_z
            drape = 1 - smooth01(0.7, 3.2, hz)
            d += drape * 0.6 * CM * math.sin(5 * th + 0.8 + 0.6 * math.sin(3 * th))    # vertical folds falling to the hem
            if hz < 0.6:                                                           # the ribbed hem band, gathered
                hemzone[i] = True; d = 0.4 * CM
            elif hz < 1.4:
                d += 0.7 * CM * math.sin(math.pi * (hz - 0.6) / 0.8)                 # the fleece blouses over the band
        out[i] = np.array(p + n * d)
    # the gathered bands: pulled towards their axis
    for i in np.nonzero(hemzone)[0]:
        p = out[i]; c = np.array([0, J("spine05")[1], p[2]]); out[i] = c + (p - c) * np.array([0.93, 0.93, 1.0])
    for i in np.nonzero(cuffzone)[0]:
        p = Vector(out[i]); _, s, _, q, ax = sleeve_param(p); r = p - q; r -= ax * r.dot(ax); out[i] = np.array(p - r * 0.12)
    set_verts(o, out)
    for poly in o.data.polygons:
        vs = list(poly.vertices); poly.material_index = 1 if all(hemzone[v] or cuffzone[v] for v in vs) else 0
    push_out(o, 0.4 * CM)
    return o, hem_z


def hood_and_cords(shell):
    """the hood lies down on the shoulders and the back: from the neckline's sides and back it runs over the shoulders
    and down the upper back (longest at the back), a thick soft double layer with radial creases; two drawstrings hang
    from eyelets either side of the neckline, with aglets"""
    loops = boundary_loops(shell); P = verts_np(shell)
    neck = max(loops, key=lambda L: P[L, 2].mean()); NP = P[neck]; c = Vector(NP.mean(0))
    bvh = bvh_of(shell)
    ring = sorted(neck, key=lambda i: math.atan2(P[i, 0] - c.x, -(P[i, 1] - c.y)))       # 0 at the front
    rows = []
    NA = 44
    for k in range(NA + 1):
        th = math.radians(28) + (2 * math.pi - 2 * math.radians(28)) * k / NA         # from the front-left round the back
        dirn = Vector((math.sin(th), -math.cos(th), 0))
        # the neckline point in this direction
        start = max((Vector(P[i]) for i in neck), key=lambda q: (q - c).normalized().dot(dirn))
        back = 0.5 - 0.5 * math.cos(th)                                               # 0 front, 1 back
        L = 0.3 + 2.7 * back ** 2.2
        def lift(s, back=back, L=L):
            return (0.5 + 1.6 * math.sin(math.pi * min(1.0, s / L)) * back) * CM + 0.35 * CM
        go = (dirn * 0.35 + Vector((0, 1, 0)) * (0.65 + 0.35 * back)).normalized()      # back, not out over the shoulders
        pts = march(bvh, start + Vector((0, 0, 0.12)), go + Vector((0, 0, 0.25)), L, step=L / 16, down_from=0.15, lift=lift)
        # creases: the collapsed hood folds in radial lines
        nn = [bvh.find_nearest(q)[1] for q in pts]
        pts = [q + n * (0.35 * CM * math.sin(7 * th + 1.3) * math.sin(math.pi * j / (len(pts) - 1))) for j, (q, n) in enumerate(zip(pts, nn))]
        # the collar stands up a little where it leaves the neckline
        pts[0] = pts[0] + Vector((0, 0, 0.12 + 0.1 * back)) - dirn * 0.04
        rows.append(pts)
    hood = grid_obj("hood", rows, MAT["fleece"], flip=True)
    sm = hood.modifiers.new("solid", "SOLIDIFY"); sm.thickness = 0.5 * CM; sm.offset = -1; sm.use_rim = True
    # drawstrings from eyelets either side of the neckline's front
    cords = []
    for sgn in (-1, 1):
        th = sgn * math.radians(22); dirn = Vector((math.sin(th), -math.cos(th), 0))
        start = max((Vector(P[i]) for i in neck), key=lambda q: (q - c).normalized().dot(dirn))
        pts = march(bvh, start - Vector((0, 0, 0.12)), Vector((sgn * 0.12, -0.2, -1)), 2.6 + 0.15 * sgn, step=0.1, down_from=0.0, lift=0.45 * CM)
        cords.append(tube("cord", pts, 0.28 * CM, MAT["cord"], n=8))
        ag = pts[-3:]; cords.append(tube("aglet", ag, 0.36 * CM, MAT["aglet"], n=8))
    return hood, cords


def pocket(shell, hem_z):
    """the kangaroo pocket: a patch on the belly from the hem band up, its sides sloping in to the openings"""
    bvh = bvh_of(shell); rows = []
    z0, z1 = hem_z + 0.65, hem_z + 2.55
    for j in range(13):
        t = j / 12; z = z0 + (z1 - z0) * t; half = 1.55 - 0.45 * smooth01(0.35, 1.0, t)     # the openings slope in
        row = []
        for i in range(21):
            x = -half + 2 * half * i / 20
            hit = bvh.ray_cast(Vector((x, -6, z)), Vector((0, 1, 0)))
            loc, nor = hit[0], hit[1]
            if loc is None: loc, nor, _, _ = bvh.find_nearest(Vector((x, -1, z)))
            side = smooth01(0.85, 1.0, abs(x) / half); opening = side * smooth01(0.3, 0.45, t)          # the openings stand off
            tuck = max(side * (1 - smooth01(0.3, 0.45, t)), smooth01(0.9, 1.0, t), 1 - smooth01(0.0, 0.08, t))   # the sewn edges tuck in
            row.append(loc + nor * (0.5 * CM + 0.25 * CM * opening - 0.35 * CM * tuck))
        rows.append(row)
    pk = grid_obj("pocket", rows, MAT["fleece"], flip=True)
    sm = pk.modifiers.new("solid", "SOLIDIFY"); sm.thickness = 0.25 * CM; sm.offset = -1; sm.use_rim = True
    return pk


# ================================================================ the trousers
def trousers(hem_z):
    o = part(JEANS_SRC, "trousers", [MAT["track"], MAT["rib"]]); subdivide(o, 1)
    P = verts_np(o); N = normals_np(o); out = P.copy(); cuff = np.zeros(len(P), bool)
    ankle_z = J("foot.L")[2]; knee_z = J("lowerleg01.L")[2]
    for i, (p, n) in enumerate(zip(P, N)):
        p = Vector(p); n = Vector(n); side = "L" if p.x > 0 else "R"
        a = J(f"lowerleg01.{side}"); b2 = J(f"lowerleg02.{side}", "tail"); ax = (b2 - a).normalized()
        r = p - a; r = r - ax * r.dot(ax); phi = math.atan2(r.x * (1 if side == "L" else -1), -r.y)
        h = p.z - ankle_z
        d = 0.9 * CM                                                                  # a relaxed fit
        d += 0.25 * CM * math.sin(4 * phi + 0.7) * (1 - smooth01(0.0, 2.5, abs(p.z - knee_z)))   # soft knee folds
        w = smooth01(0.35, 0.6, h) * (1 - smooth01(1.2, 1.7, h))                             # stacking above the cuffs
        d += w * 0.35 * CM * math.sin(2 * math.pi * h / 0.3 + 1.2 * math.sin(2 * phi))
        if h < 0.4: cuff[i] = True; d = 0.35 * CM
        out[i] = np.array(p + n * d)
    for i in np.nonzero(cuff)[0]:                                                       # elastic cuffs gather in
        p = Vector(out[i]); side = "L" if p.x > 0 else "R"; a = J(f"lowerleg02.{side}", "tail")
        r = p - a; r.z = 0; out[i] = np.array(p - r * 0.14)
    # under the hoodie the waist is snug to the body (2.5 mm), blending back to the relaxed fit 7 cm below the hem, so the
    # gathered hem band always lies over it (it poked through the band at the hips)
    for i, p in enumerate(out):
        k = smooth01(hem_z - 0.7, hem_z + 0.1, p[2])
        if k <= 0: continue
        loc, nor, _, _ = BODY_BVH.find_nearest(Vector(p))
        out[i] = p * (1 - k) + np.array(loc + nor * 0.25 * CM) * k
    set_verts(o, out)
    for poly in o.data.polygons: poly.material_index = 1 if all(cuff[v] for v in poly.vertices) else 0
    push_out(o, 0.35 * CM)
    # the side stripe: one 1.4 cm band down the outside of each leg, on the fabric
    bvh = bvh_of(o); stripes = []
    for sgn in (1, -1):
        side = "L" if sgn > 0 else "R"; hip = J(f"upperleg01.{side}"); ank = J(f"lowerleg02.{side}", "tail")
        rows = []
        for k in range(48):
            t = k / 47; z = hip.z + 0.35 + (ank.z + 0.45 - hip.z - 0.35) * t
            cx = hip.x + (ank.x - hip.x) * t; cy = hip.y + (ank.y - hip.y) * t
            hit = bvh.ray_cast(Vector((cx + sgn * 6, cy, z)), Vector((-sgn, 0, 0)))
            if hit[0] is None: continue
            loc, nor = hit[0], hit[1]
            across = Vector((0, 1, 0)); across = (across - nor * across.dot(nor)).normalized()
            rows.append([loc + nor * 0.12 * CM + across * (0.7 * CM * u) for u in (-1, 0, 1)])
        stripes.append(grid_obj("stripe", [list(r) for r in zip(*rows)], MAT["stripe"], flip=sgn < 0))
    return o, stripes


# ================================================================ socks and slides
def socks():
    """white crew socks: the body's feet and lower shins, 2 mm out, the toes smoothed into one envelope, a ribbed top"""
    top = J("foot.L")[2] + 0.95
    keep = [f for f in BODY_F if all(B(REST[i]).z < top for i in f)]
    ids = sorted({i for f in keep for i in f}); remap = {v: k for k, v in enumerate(ids)}
    o = mesh_obj("socks", [B(REST[i]) for i in ids], [[remap[i] for i in f] for f in keep], [MAT["sock"], MAT["sockrib"]])
    # the toes become one envelope: smooth the front of the foot, then out of the skin
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.free()
    P = verts_np(o); N = normals_np(o); P += N * 0.2 * CM; set_verts(o, P)
    push_out(o, 0.25 * CM, iters=2)
    # a sock does not go between the toes: concave places fill outward only (towards their neighbours, along the normal)
    # until the front of the foot is one smooth envelope; nothing ever moves inward, so it never enters the skin
    nb = {}
    for poly in o.data.polygons:
        vs = list(poly.vertices)
        for a, b2 in zip(vs, vs[1:] + vs[:1]): nb.setdefault(a, set()).add(b2); nb.setdefault(b2, set()).add(a)
    front = [v.index for v in o.data.vertices if v.co.y < J("foot.L", "tail").y + 0.75 and v.co.z < J("foot.L")[2] + 0.35]
    # a sock is one smooth shape over the toes (a morphological closing of the skin): the front of the foot is smoothed
    # well inside the skin, then every front vertex goes out along the smoothed normal to just past the OUTERMOST skin
    # hit of a small disk of rays (5 mm across), so the knit bridges the gaps between the toes and never enters the skin
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    for _ in range(25): bmesh.ops.smooth_vert(bm, verts=[bm.verts[i] for i in front], factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    S = verts_np(o); NS = normals_np(o); P = S.copy(); r = 0.25 * CM
    for i in front:
        base, n = Vector(S[i]), Vector(NS[i]).normalized(); t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
        best = None
        for k in range(7):
            off = Vector((0, 0, 0)) if k == 0 else (t1 * math.cos(k * math.pi / 3) + t2 * math.sin(k * math.pi / 3)) * r
            hit = BODY_BVH.ray_cast(base + n * 1.2 + off, -n, 2.5)
            if hit[0] is not None:
                t = (hit[0] - base).dot(n); best = t if best is None else max(best, t)
        if best is not None: P[i] = np.array(base + n * (best + 0.25 * CM))
    set_verts(o, P)
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    for _ in range(2): bmesh.ops.smooth_vert(bm, verts=[bm.verts[i] for i in front], factor=0.35, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    push_out(o, 0.2 * CM, iters=1)
    for poly in o.data.polygons:
        poly.material_index = 1 if min(o.data.vertices[v].co.z for v in poly.vertices) > top - 0.35 else 0
    return o, ids


MISSES = [0]
def slides(sock_obj):
    """black slides: a 2.4 cm EVA footbed under each foot (its outline the foot's footprint, 8 mm out) and a wide
    padded strap over the instep"""
    bvh = bvh_of(sock_obj); parts = []
    floor = min(B(REST[i]).z for i in BODY_IDS)
    for sgn in (1, -1):
        side = "L" if sgn > 0 else "R"
        foot = np.array([B(REST[i]) for i in BODY_IDS if B(REST[i]).z < floor + 0.55 and B(REST[i]).x * sgn > 0.3])   # the sole: heel to toes
        cx, cy = (foot[:, 0].min() + foot[:, 0].max()) / 2, (foot[:, 1].min() + foot[:, 1].max()) / 2   # (the toes are dense: not the mean)
        # the outline: the footprint's extent in each direction, smoothed, 8 mm out
        outline = []
        for k in range(48):
            a = 2 * math.pi * k / 48; d = np.array([math.cos(a), math.sin(a)])
            rel = foot[:, :2] - [cx, cy]; proj = rel @ d
            outline.append(max(proj.max(), 0.3) + 0.8 * CM)
        sm_ = [sum(outline[(k + j) % 48] for j in (-2, -1, 0, 1, 2)) / 5 for k in range(48)]
        bm = bmesh.new(); bot, topv = [], []
        z0, z1 = floor - 1.6 * CM, floor + 0.2 * CM                                      # an 1.8 cm sole
        for k in range(48):
            a = 2 * math.pi * k / 48; x, y = cx + sm_[k] * math.cos(a), cy + sm_[k] * math.sin(a)
            bot.append(bm.verts.new((x, y, z0))); topv.append(bm.verts.new((x, y, z1)))
        bm.faces.new(list(reversed(bot))); bm.faces.new(topv)
        for k in range(48): bm.faces.new([bot[k], bot[(k + 1) % 48], topv[(k + 1) % 48], topv[k]])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.18 * CM, segments=2, affect='EDGES', clamp_overlap=True)   # a flatter edge
        me = bpy.data.meshes.new("slide_sole"); bm.to_mesh(me); bm.free()
        so = bpy.data.objects.new("slide_sole", me); SC.collection.objects.link(so); me.materials.append(MAT["eva"]); parts.append(so)
        # the strap: arcs over the instep, from one edge of the footbed to the other
        ys = [cy + (foot[:, 1].min() - cy) * f for f in (0.0, 0.11, 0.22, 0.33, 0.44, 0.55, 0.64)]   # a wide strap over the instep
        rows = []
        for y in ys:
            row = []
            for j in range(15):
                u = j / 14; a = math.pi * u
                dirv = Vector((math.cos(a), 0, math.sin(a)))
                o_ = Vector((cx, y, floor + 0.3))
                hit = bvh.ray_cast(o_ + dirv * 3, -dirv, 6.0)
                if hit[0] is None: MISSES[0] += 1
                p = hit[0] + (dirv * 0.35 * CM) if hit[0] is not None else o_ + dirv * 0.5
                if p.z < z1: p.z = z1
                row.append(p)
            rows.append(row)
        if os.environ.get("POSE_DEBUG"):
            sp = np.array([[q.x, q.y, q.z] for r in rows for q in r]); so_ = verts_np(sock_obj); so_ = so_[so_[:, 0] * sgn > 0.3]
            print("STRAPDBG", side, "cx cy", round(cx, 2), round(cy, 2), "foot y", round(foot[:, 1].min(), 2), round(foot[:, 1].max(), 2), "strap min", sp.min(0).round(2), "max", sp.max(0).round(2), "sock min", so_.min(0).round(2), "max", so_.max(0).round(2))
        st = grid_obj("slide_strap", rows, MAT["eva"])
        sm = st.modifiers.new("solid", "SOLIDIFY"); sm.thickness = 0.55 * CM; sm.offset = 1; sm.use_rim = True
        parts.append(st)
    return parts


# ================================================================ build
shell, HEM_Z = hoodie()
hood, cords = hood_and_cords(shell)
pk = pocket(shell, HEM_Z)
pants, stripes = trousers(HEM_Z)
sock, SOCK_IDS = socks()
sl = slides(sock); print("STRAP ray misses", MISSES[0])
for o in (hood, pk): bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="solid")
for o in sl:
    if o.modifiers: bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="solid")
HOODIE = join([shell, hood, pk] + cords, "hoodie_black")
TROUSERS = join([pants] + stripes, "track_trousers")
SLIDES = join(sl, "slides_black")
GARMENTS = {"hoodie_black": HOODIE, "track_trousers": TROUSERS, "socks_white": sock, "slides_black": SLIDES}


def box_uvs(o):
    """per face, a box projection in fabric units: one UV tile = the material's tile (dm)"""
    me = o.data; uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        tile = me.materials[p.material_index].get("tile", 0.3); n = p.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            u, v = (c.x, c.y) if ax == 2 else (c.y, c.z) if ax == 0 else (c.x, c.z)
            uvl.data[li].uv = (u / tile, v / tile)


for o in GARMENTS.values(): box_uvs(o)


# ================================================================ bind (.mhclo), hide the covered skin, skin the garments
SCALE_REF = SUIT["scale"]
def binding(o):
    ref, w, off = [], [], []
    for v in o.data.vertices:
        loc, nor, fi, _ = BODY_BVH.find_nearest(v.co)
        tri = BODY_TRIS[fi]; a, b2, c = (B(REST[t]) for t in tri)
        bc = M._closest_on_triangle(np.array(loc), np.array(a), np.array(b2), np.array(c))
        q = a * bc[0] + b2 * bc[1] + c * bc[2]
        ref.append(tri); w.append(bc); off.append(MHv(v.co - q))
    sc = [(v1, v2, abs(REST[v1][n] - REST[v2][n])) for n, (v1, v2, _) in enumerate(SCALE_REF)]
    return {"ref": np.array(ref, int), "w": np.array(w, float), "off": np.array(off, float), "scale": sc}


def covered(o, reach=3.5 * CM):
    """body vertices under a garment: a ray from the vertex along its normal meets the garment within `reach`"""
    bvh = bvh_of(o); out = []
    used = sorted({i for f in BODY_F for i in f})
    body.data.update(); nrm = {v.index: v.normal.copy() for v in body.data.vertices}
    for i in used:
        p = B(REST[i]); hit = bvh.ray_cast(p + nrm[i] * 0.01, nrm[i], reach)
        if hit[0] is not None: out.append(i)
    return out


BIND, DELETE = {}, {}
def close_gaps(ids, rounds=3):
    """a skin vertex most of whose neighbours are hidden is hidden too (no islands of skin under the clothes)"""
    s = set(ids); nb = {}
    for f in BODY_F:
        for a, b2 in zip(f, f[1:] + f[:1]): nb.setdefault(a, set()).add(b2); nb.setdefault(b2, set()).add(a)
    for _ in range(rounds):
        add = {v for v in nb if v not in s and sum(n in s for n in nb[v]) >= 0.6 * len(nb[v])}
        if not add: break
        s |= add
    return sorted(s)


for name, o in GARMENTS.items():
    BIND[name] = binding(o)
    DELETE[name] = close_gaps(covered(o, 5 * CM)) if name != "slides_black" else []
    if name == "socks_white": DELETE[name] = sorted(set(DELETE[name]) | set(SOCK_IDS))
    print(name, "verts", len(o.data.vertices), "faces", len(o.data.polygons), "hides", len(DELETE[name]), "body vertices")
for name, o in GARMENTS.items():
    b = BIND[name]
    wm = (WMAT[b["ref"][:, 0]] * b["w"][:, 0, None] + WMAT[b["ref"][:, 1]] * b["w"][:, 1, None] + WMAT[b["ref"][:, 2]] * b["w"][:, 2, None])
    skin(o, wm)


# ================================================================ write the MakeHuman clothes: .obj (box-projected UVs, metres of fabric per tile), .mhclo, .mhmat
import shutil
def write_garment(name, o, tags):
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    me = o.data; V = [MHv(v.co) for v in me.vertices]; F = [list(p.vertices) for p in me.polygons]
    groups = [me.materials[p.material_index].name for p in me.polygons]
    uvl = me.uv_layers["UVMap"]; UV, FT = [], []
    for p in me.polygons:
        FT.append([len(UV) + k for k in range(len(p.loop_indices))])
        UV.extend(tuple(uvl.data[li].uv) for li in p.loop_indices)
    M.write_obj(os.path.join(d, f"{name}.obj"), V, F, UV, FT, groups)
    mats = {me.materials[p.material_index].name for p in me.polygons}
    main = max(mats, key=lambda k: groups.count(k)); mm = MAT[main]
    for k in mats:                                            # every group's baked maps go with the garment
        if MAT[k].get("color_map"):
            shutil.copy(MAT[k]["color_map"], d); shutil.copy(MAT[k]["normal_map"], d)
    col, nor = os.path.basename(mm["color_map"]), os.path.basename(mm["normal_map"])
    M.write_mhmat(os.path.join(d, f"{name}.mhmat"), name, (1.0, 1.0, 1.0), nor, 1.0, mm["rough"],
                  extra=f"diffuseTexture {col}\n# per-group materials of the .obj (g lines), each with <group>_color.jpg and <group>_normal.jpg: "
                        + ", ".join(sorted(mats)) + "\n")
    M.write_mhclo(os.path.join(d, f"{name}.mhclo"), name, str(uuid.uuid5(uuid.NAMESPACE_URL, "sub01/clothes/" + name)),
                  BIND[name], DELETE[name], f"{name}.obj", f"{name}.mhmat", tags,
                  "Shapes partly derived from MakeHuman's CC0 system asset male_casualsuit02." if name in ("hoodie_black", "track_trousers") else "",
                  z_depth={"socks_white": 30, "slides_black": 10, "track_trousers": 45, "hoodie_black": 55}[name])
for name, o in GARMENTS.items():
    write_garment(name, o, ["Male", "Casual", "SUB-01"])
    back = M.fit(M.read_mhclo(os.path.join(OUT, name, f"{name}.mhclo")), REST)
    err = np.abs(back - np.array([MHv(v.co) for v in o.data.vertices])).max()
    print("REFIT", name, "max error", round(float(err) * 100, 3), "mm"); assert err < 0.002, (name, err)
json.dump({k: {"verts": len(o.data.vertices), "faces": len(o.data.polygons), "hides": len(DELETE[k])} for k, o in GARMENTS.items()},
          open(os.path.join(OUT, "summary.json"), "w"), indent=1)

# the body as the sheet shows it: the skin under the clothes removed (MakeHuman's delete_verts)
ALL_DEL = set()
for v in DELETE.values(): ALL_DEL |= set(v)
bm = bmesh.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.index in ALL_DEL for v in f.verts)], context='FACES')
bm.to_mesh(body.data); bm.free()


# ================================================================ poses
def rot_world(name, axis, deg):
    pb = RIG.pose.bones[name]; bpy.context.view_layer.update()
    h = RIG.matrix_world @ pb.head
    R = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-h)
    pb.matrix = RIG.matrix_world.inverted() @ R @ RIG.matrix_world @ pb.matrix; bpy.context.view_layer.update()


def reset_pose():
    for pb in RIG.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    for o in [RIG, body] + list(GARMENTS.values()): o.location = (0, 0, 0)
    bpy.context.view_layer.update()


def aim(name, direction, end=None):
    """turn a bone (and its children) about its head so that its head -> tail (or head -> the tail of `end`, a chain)
    points along `direction` (world)"""
    bpy.context.view_layer.update(); pb = RIG.pose.bones[name]; mw = RIG.matrix_world
    h = mw @ pb.head; t = mw @ (RIG.pose.bones[end].tail if end else pb.tail)
    q = (t - h).rotation_difference(Vector(direction).normalized())
    R = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h)
    pb.matrix = mw.inverted() @ R @ mw @ pb.matrix; bpy.context.view_layer.update()
    if os.environ.get("POSE_DEBUG"):
        t2 = mw @ (RIG.pose.bones[end].tail if end else pb.tail); print("AIM", name, "want", tuple(round(c, 2) for c in Vector(direction).normalized()), "got", tuple(round(c, 2) for c in (t2 - (mw @ pb.head)).normalized()))


def pose_standing():
    reset_pose()
    for s, sg in (("L", 1), ("R", -1)):
        aim(f"upperarm01.{s}", (0.17 * sg, 0.03, -1), f"upperarm02.{s}")         # arms down at his sides
        aim(f"lowerarm01.{s}", (0.06 * sg, -0.22, -1), f"lowerarm02.{s}")        # elbows a little bent
        aim(f"wrist.{s}", (0.03 * sg, -0.12, -1))


def pose_seated():
    reset_pose()
    for s, sg in (("L", 1), ("R", -1)):
        aim(f"upperleg01.{s}", (0.1 * sg, -1, -0.06), f"upperleg02.{s}")          # thighs level on the seat
        aim(f"lowerleg01.{s}", (0.04 * sg, -0.14, -1), f"lowerleg02.{s}")        # shins down, feet flat
        aim(f"foot.{s}", (0.08 * sg, -1, -0.5))
        aim(f"upperarm01.{s}", (0.2 * sg, -0.42, -1), f"upperarm02.{s}")         # upper arms down and a little forward
        aim(f"lowerarm01.{s}", (-0.16 * sg, -1, 0.06), f"lowerarm02.{s}")        # forearms level, to the keyboard
        aim(f"wrist.{s}", (-0.1 * sg, -1, -0.05))
    rot_world("spine03", 'X', -4); rot_world("neck01", 'X', -6)
    for s, sg in (("L", 1), ("R", -1)):                                          # fingers curled over the keys
        for f in range(2, 6):
            for seg, ang in ((1, 14), (2, 26), (3, 18)):
                nm = f"finger{f}-{seg}.{s}"
                if nm in RIG.pose.bones: rot_world(nm, 'X', ang)


# ================================================================ the studio and the sheet
def lights():
    w = bpy.data.worlds.new("w"); SC.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.26, 0.27, 0.29, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    for nm, loc, rot, en, size in (("key", (-14, -16, 18), (55, 0, -40), 9000, 9), ("fill", (18, -12, 8), (75, 0, 55), 2600, 12),
                                   ("rim", (6, 16, 16), (-60, 0, 160), 5200, 7)):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = en; ld.size = size
        lo = bpy.data.objects.new(nm, ld); lo.location = loc; lo.rotation_euler = [math.radians(a) for a in rot]; SC.collection.objects.link(lo)
    floor = min(B(REST[i]).z for i in BODY_IDS) - 1.6 * CM
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, floor)); bpy.context.active_object.data.materials.append(MAT["studio"])
    return floor


FLOOR = lights()
for o in GARMENTS.values():
    m = o.modifiers.new("sub", "SUBSURF"); m.levels = 1; m.render_levels = 1
m = body.modifiers.new("sub", "SUBSURF"); m.levels = 1; m.render_levels = 1
SC.render.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 24 if QUICK else 160
SC.cycles.use_denoising = True; SC.render.film_transparent = False
SC.view_settings.view_transform = 'AgX'
SC.view_settings.exposure = 0.1


def camera(name, loc, target, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens; co = bpy.data.objects.new(name, cd); SC.collection.objects.link(co)
    co.location = loc; d = Vector(target) - Vector(loc); co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return co


def render(cam, w, h, path):
    SC.camera = cam; SC.render.resolution_x = w; SC.render.resolution_y = h; SC.render.resolution_percentage = 100
    SC.render.filepath = path; bpy.ops.render.render(write_still=True); print("rendered", path)


def seat_props(on):
    for nm in ("stool", "desk"):
        if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm])
    if not on: return
    bpy.context.view_layer.update()
    # the seat: under his thighs (the lowest point of the posed body between the hips and the knees)
    dg = bpy.context.evaluated_depsgraph_get(); ev = TROUSERS.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world
    pts = [mw @ v.co for v in me.vertices]; ev.to_mesh_clear()
    seat = min(p.z for p in pts if -1.6 < p.y < 1.0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.2, (seat + FLOOR) / 2)); st = bpy.context.active_object; st.name = "stool"
    st.scale = (4.2, 3.6, seat - FLOOR); st.data.materials.append(MAT["desk"])
    wr = RIG.matrix_world @ RIG.pose.bones["wrist.L"].head
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, wr.y - 1.6, wr.z - 0.45)); dk = bpy.context.active_object; dk.name = "desk"
    dk.scale = (12, 5.0, 0.3); dk.data.materials.append(MAT["desk"])


if RENDER:
    W = 560 if QUICK else 800; Hh = 2 * W
    pose_standing(); seat_props(False)
    render(camera("c_stand", (-7.5, -24, 2.4), (0, 0, -0.6), 50), W, Hh, f"{SHEET_DIR}/standing.png")
    render(camera("c_hood", (-3.6, -9.5, 6.2), (0.2, 0.0, 3.4), 60), W, W, f"{SHEET_DIR}/close_hood.png")
    if os.environ.get("POSE_DEBUG"):
        render(camera("c_knit", (0.6, -3.2, 2.2), (0.3, 0, 2.0), 50), 500, 500, f"{SHEET_DIR}/debug_knit.png")
        render(camera("c_hem", (3.2, -5.5, 0.6), (1.2, 0, 0.2), 50), 500, 500, f"{SHEET_DIR}/debug_hem.png")
        fl = J("foot.L"); render(camera("c_foot", (fl.x - 2.5, fl.y - 4.5, fl.z + 1.6), (fl.x, fl.y - 0.5, fl.z - 0.4), 50), 500, 500, f"{SHEET_DIR}/debug_foot.png")
    pose_seated(); bpy.context.view_layer.update()
    # lower the rig so the feet stay on the floor
    dg = bpy.context.evaluated_depsgraph_get(); ev = SLIDES.evaluated_get(dg); me = ev.to_mesh(); low = min((ev.matrix_world @ v.co).z for v in me.vertices); ev.to_mesh_clear()
    for o in [RIG, body] + list(GARMENTS.values()): o.location.z += FLOOR - low
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ev = SLIDES.evaluated_get(dg); me = ev.to_mesh(); low2 = min((ev.matrix_world @ v.co).z for v in me.vertices); ev.to_mesh_clear()
    print("SEAT floor", round(FLOOR, 3), "slides low before", round(low, 3), "after", round(low2, 3))
    seat_props(True)
    if os.environ.get("POSE_DEBUG"):
        cs = camera("c_side", (-30, -1.5, -2.0), (0, -1.5, -2.0), 50); cs.data.type = 'ORTHO'; cs.data.ortho_scale = 22
        render(cs, 600, 600, f"{SHEET_DIR}/debug_side.png")
    bpy.context.view_layer.update(); el = RIG.matrix_world @ RIG.pose.bones["lowerarm01.R"].head
    render(camera("c_seat", (-21, -15, 3.0), (0, -1.6, -3.4), 50), W, Hh, f"{SHEET_DIR}/seated.png")
    bpy.ops.object.select_all(action='DESELECT'); dg = bpy.context.evaluated_depsgraph_get(); posed = []
    for o in [body, bpy.data.objects["stool"], bpy.data.objects["desk"]] + list(GARMENTS.values()):   # posed copies (the glTF
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)                       # exporter skips armatures)
        c = bpy.data.objects.new(o.name.split(".")[0], me); c.matrix_world = o.matrix_world.copy(); SC.collection.objects.link(c)
        c.select_set(True); posed.append(c)
    bpy.ops.export_scene.gltf(filepath=f"{SHEET_DIR}/web_check.glb", export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_materials='EXPORT', export_image_format='JPEG')
    for c in posed: bpy.data.objects.remove(c)
    render(camera("c_elbow", (el.x - 5.5, el.y - 1.0, el.z + 2.6), (el.x + 0.6, el.y - 0.6, el.z - 0.2), 55), W, W, f"{SHEET_DIR}/close_elbow.png")
print("DONE")
