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
# maps are Poly Haven's (CC0), the slides' rubber grain ambientCG's Rubber004 (CC0). Everything this script makes is
# released under CC0.
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
FEET_ONLY = "--feet" in argv                                   # only the feet sheet's four shots
os.makedirs(OUT, exist_ok=True); os.makedirs(SHEET_DIR, exist_ok=True)
random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
CM = 0.1                                                       # one centimetre in MakeHuman units


def B(p): return Vector((p[0], -p[2], p[1]))                   # MakeHuman -> Blender
def MHv(v): return np.array([v[0], v[2], -v[1]])               # Blender -> MakeHuman
def crease(x, period, width):
    """1 in the narrow valley of a fold, 0 on its broad rounded crest: folds repeating every `period` along x"""
    u = ((x / period) % 1.0 - 0.5) * period; return math.exp(-(u / width) ** 2)
def smooth01(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else float(x >= b); return t * t * (3 - 2 * t)


# ================================================================ the body
base, BODY_F, _, _ = M.read_obj(f"{MH}/3dobjs/base.obj", groups={"body"})
# G2's body (room_build/mh/build_g2.mjs on preview/mh-motion): MakeHuman's macro modifiers evaluated as MakeHuman does,
# male, 20 years (a blend of the "child" and "young" targets), muscle 0.5, weight 0.4, proportions 0.75, ethnicity 1/3
# each, and the hand targets; then (on export only) a uniform scale to 1.75 m with the feet at y = 0
def g2_targets():
    age_val = 0.1875 + (20 - 11) / (25 - 11) * (0.5 - 0.1875)
    ages = {"child": (0.5 - age_val) / (0.5 - 0.1875), "young": (age_val - 0.1875) / (0.5 - 0.1875)}
    tri = lambda v: {"min": 1 - v / 0.5, "average": v / 0.5} if v < 0.5 else {"average": (1 - v) / 0.5, "max": (v - 0.5) / 0.5}
    muscles = {k + "muscle": w for k, w in tri(0.5).items()}; weights = {k + "weight": w for k, w in tri(0.4).items()}
    T = []
    for eth in ("african", "asian", "caucasian"):
        for age, aw in ages.items(): T.append((f"macrodetails/{eth}-male-{age}.target", aw / 3))
    for age, aw in ages.items():
        for mu, mw in muscles.items():
            for we, ww in weights.items():
                T.append((f"macrodetails/universal-male-{age}-{mu}-{we}.target", aw * mw * ww))
                T.append((f"macrodetails/proportions/male-{age}-{mu}-{we}-idealproportions.target", aw * mw * ww * 0.5))
    for sd in ("l", "r"):
        for k, w in (("fingers-diameter-incr", 0.55), ("fingers-length-decr", 1.0), ("scale-incr", 0.15)):
            T.append((f"armslegs/{sd}-hand-{k}.target", w))
    return [(f"{MH}/targets/{rel}", w) for rel, w in T if w > 1e-6]
REST = M.apply_targets(base, g2_targets())
NV = len(REST)
BODY_IDS = sorted({i for f in BODY_F for i in f})                 # the skin's vertices (the rest are helpers)
G2_Y0 = REST[BODY_IDS, 1].min(); G2_S = 1.75 / (REST[BODY_IDS, 1].max() - G2_Y0)   # MakeHuman units -> G2's metres
def to_g2(p): return np.stack([p[..., 0] * G2_S, (p[..., 1] - G2_Y0) * G2_S, p[..., 2] * G2_S], -1)
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


def inside_body(p):
    """p inside the (rest) body: an odd number of skin crossings along at least two of three rays"""
    odd = 0
    for d in (Vector((0.31, 0.83, 0.46)), Vector((-0.71, -0.2, 0.67)), Vector((0.12, -0.6, -0.79))):
        n, q = 0, Vector(p)
        while True:
            h = BODY_BVH.ray_cast(q, d, 30.0)
            if h[0] is None: break
            n += 1; q = h[0] + d * 1e-4
        odd += n % 2
    return odd >= 2


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
    # the slides: matte black moulded rubber (ambientCG Rubber004's grain), the footbed with faint moulded nubs 3 mm apart
    "rubber":  dict(tile=0.6, rgb=(0.016, 0.016, 0.017), rough=0.74, sheen=(0.0, 0.0), normal="rubber004", nstr=0.7, melange="rubber004", mel_amt=0.12, size=512),
    "footbed": dict(tile=0.6, rgb=(0.016, 0.016, 0.017), rough=0.78, sheen=(0.0, 0.0), normal="rubber004", nstr=0.7, melange="rubber004", mel_amt=0.12, dots=(20, 1.6), size=1024),
    "strap":   dict(tile=0.6, rgb=(0.017, 0.017, 0.018), rough=0.62, sheen=(0.0, 0.0), normal="rubber004", nstr=0.4, melange="rubber004", mel_amt=0.08, size=512),
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
    out = P.copy(); sleeve = np.zeros(len(P), bool); cuffzone = np.zeros(len(P), bool); hemzone = np.zeros(len(P), bool); fw = np.full(len(P), 99.0)
    torso_axis = Vector((0, J("spine03")[1], 0))
    for i, (p, n) in enumerate(zip(P, N)):
        p = Vector(p); n = Vector(n)
        sp = sleeve_param(p); is_sleeve = abs(p.x) > shoulder_x - 0.15 and sp[1] > 0.4
        d = 0.6 * CM                                                             # a slim fit (the owner): close to the body
        if is_sleeve:
            sleeve[i] = True; side, s, dist, q, ax = sp
            from_wrist = arm_len - s
            r = (p - q); r = r - ax * r.dot(ax)
            front = Vector((0, -1, 0)); front = (front - ax * front.dot(ax)).normalized()
            phi = math.atan2(r.normalized().cross(front).dot(ax), r.normalized().dot(front)) if r.length > 1e-6 else 0.0
            fw[i] = from_wrist
            d = 0.55 * CM + 0.15 * CM * max(0.0, -r.normalized().z) * smooth01(1.2, 2.0, s)  # a slim sleeve, a little weight under the forearm
            # the armpit: where the arm comes down against the body the sleeve's inner side lies close (not 2 cm out)
            inner = max(0.0, -r.normalized().x * (1 if side == "L" else -1)) * (1 - smooth01(0.9, 1.7, s))
            d -= inner * 0.3 * CM
            # elbow: diagonal wrinkles on the inner side, fanning out from the crease
            e = math.exp(-((s - elbow_s) / (0.55)) ** 2) * max(0.0, math.cos(phi)) ** 1.5
            d += e * (0.2 * CM - 0.6 * CM * crease(s - elbow_s + 0.11 * phi, 0.4, 0.09))   # sharp valleys, round crests
            d += 0.2 * CM * math.exp(-((s - elbow_s) / 0.8) ** 2) * max(0.0, -math.cos(phi)) * math.sin(3 * phi + 6 * s)   # bunching at the back of the elbow
            d += 0.12 * CM * smooth01(0.8, 1.6, s) * (1 - smooth01(elbow_s - 0.6, elbow_s - 0.2, s)) * math.sin(2 * math.pi * s / 0.55 + 1.7 * phi)   # soft folds down the upper arm
            # stacking above the cuff: the sleeve is longer than the arm and bunches on the forearm
            w = smooth01(0.45, 0.7, from_wrist) * (1 - smooth01(1.4, 1.9, from_wrist))
            d += w * 0.45 * CM * math.sin(2 * math.pi * from_wrist / 0.3 + 0.9 * math.sin(2 * phi + s))
            if from_wrist < 0.55:                                                  # the ribbed cuff hugs the wrist
                cuffzone[i] = True; d = 0.2 * CM
        else:
            th = math.atan2(p.x, -p.y)                                             # around the body, 0 at the front
            hz = p.z - hem_z
            # the sides under the arms: close to the body there, so the lowered arm does not cut into the hoodie
            d -= 0.3 * CM * abs(math.sin(th)) ** 3 * smooth01(chest_z - 2.4, chest_z - 1.2, p.z) * (1 - smooth01(chest_z + 0.4, chest_z + 1.0, p.z))
            drape = 1 - smooth01(0.7, 3.2, hz)
            d += drape * 0.3 * CM * math.sin(5 * th + 0.8 + 0.6 * math.sin(3 * th))    # soft vertical folds falling to the hem
            # the belly: the loose fleece sags into soft, slightly curved folds across the front above the hem
            belly = smooth01(0.8, 1.3, hz) * (1 - smooth01(2.8, 3.8, hz)) * max(0.0, math.cos(th)) ** 1.5
            # (no folds or volume over the belly standing: the seated corrective folds it when he sits)
            if hz < 0.6:                                                           # the ribbed hem band, gathered
                hemzone[i] = True; d = 0.4 * CM
            elif hz < 1.4:
                d += 0.3 * CM * math.sin(math.pi * (hz - 0.6) / 0.8)                 # the fleece blouses a little over the band
        out[i] = np.array(p + n * d)
    # the gathered bands: pulled towards their axis
    for i in np.nonzero(hemzone)[0]:
        p = out[i]; c = np.array([0, J("spine05")[1], p[2]]); out[i] = c + (p - c) * np.array([0.93, 0.93, 1.0])
    for i in np.nonzero(cuffzone)[0]:
        p = Vector(out[i]); _, s, _, q, ax = sleeve_param(p); r = p - q; r -= ax * r.dot(ax); out[i] = np.array(p - r * 0.03)
    # SLIM (the owner: "too puffed"): the source suit stands off the body by itself, so the fleece is capped at a distance
    # from the skin: 1 cm on the torso, 0.9 cm on the sleeves (a little more just above the hem band and the cuffs, where
    # real cloth stacks); nothing at the belly, chest or shoulders stands further out
    for i, p in enumerate(out):
        if hemzone[i] or cuffzone[i]: continue
        loc, nor, _, dd = BODY_BVH.find_nearest(Vector(p))
        if loc is None or (Vector(p) - loc).dot(nor) < 0: continue
        hz = p[2] - hem_z
        cap = (0.9 * CM + 0.35 * CM * (1 - smooth01(0.5, 1.9, fw[i]))) if sleeve[i] else (1.0 * CM + 0.3 * CM * (1 - smooth01(0.6, 1.5, hz)))
        if dd > cap: out[i] = np.array(loc + nor * cap)
    set_verts(o, out)
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()          # (the cap's creases at the armpits relaxed)
    bmesh.ops.smooth_vert(bm, verts=[v for v in bm.verts if not (hemzone[v.index] or cuffzone[v.index])], factor=0.3, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    for poly in o.data.polygons:
        vs = list(poly.vertices); poly.material_index = 1 if all(hemzone[v] or cuffzone[v] for v in vs) else 0
    push_out(o, 0.4 * CM)
    return o, hem_z


HOOD_EDGE = []
def hood_and_cords(shell):
    """a real lowered hood: from the neckline's sides and back it lies flat down the upper back in a soft U (longest at
    the back), two thin fabric layers about 1 cm thick in all, its folded opening edge round the neck, no rolled collar;
    two drawstrings hang from eyelets either side of the neckline, with aglets"""
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
        L = 0.3 + 1.9 * smooth01(0.12, 0.8, back)                                     # a broad round U down the back, as a lowered hood lies
        def lift(s, back=back, L=L):                                                   # flat on the back: 3 mm over the fleece
            return 0.3 * CM + 0.15 * CM * math.sin(math.pi * min(1.0, s / L)) * back
        go = (dirn * 0.35 + Vector((0, 1, 0)) * (0.65 + 0.35 * back)).normalized()      # back, not out over the shoulders
        pts = march(bvh, start + Vector((0, 0, 0.02)), go + Vector((0, 0, 0.1)), L, step=L / 16, down_from=0.05, lift=lift)
        # creases: the collapsed hood folds in radial lines
        nn = [bvh.find_nearest(q)[1] for q in pts]
        pts = [q + n * (0.08 * CM * math.sin(7 * th + 1.3) * math.sin(math.pi * j / (len(pts) - 1))) for j, (q, n) in enumerate(zip(pts, nn))]
        # (no stand-up collar: the hood leaves the neckline lying down)
        rows.append(pts)
    hood = grid_obj("hood", rows, MAT["fleece"], flip=True)
    sm = hood.modifiers.new("solid", "SOLIDIFY"); sm.thickness = 0.8 * CM; sm.offset = -1; sm.use_rim = True   # two thin layers, ~1 cm
    # the hood's opening edge, folded over at the neck (its hem with the drawstring channel), lying round the neckline
    edge = [r[1] * 0.6 + r[0] * 0.4 for r in rows]
    HOOD_EDGE.append(tube("hood_edge", edge, 0.32 * CM, MAT["fleece"], n=8, cap=True))
    # drawstrings from eyelets either side of the neckline's front
    cords = []
    for sgn in (-1, 1):
        th = sgn * math.radians(22); dirn = Vector((math.sin(th), -math.cos(th), 0))
        start = max((Vector(P[i]) for i in neck), key=lambda q: (q - c).normalized().dot(dirn))
        pts = march(bvh, start - Vector((0, 0, 0.12)), Vector((sgn * 0.12, -0.2, -1)), 2.6 + 0.15 * sgn, step=0.1, down_from=0.0, lift=0.45 * CM)
        cords.append(tube("cord", pts, 0.28 * CM, MAT["cord"], n=8))
        ag = pts[-3:]; cords.append(tube("aglet", ag, 0.36 * CM, MAT["aglet"], n=8))
    return hood, cords


POCKET_SEWING = []
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
    sm = pk.modifiers.new("solid", "SOLIDIFY"); sm.thickness = 0.3 * CM; sm.offset = -1; sm.use_rim = True
    # the sewing, as on a real kangaroo pocket: a twin-needle topstitch along the top, a stitch line down each side
    # (6 mm in from the edge, the thread a raised line on the fleece) and a rolled hem along each opening; the rows are
    # the pocket's outer surface, so the thread sits just on it
    nrm = lambda q: bvh.find_nearest(q)[1]
    def lift(pts, h): return [q + nrm(q) * h for q in pts]
    def mix(a, b, f): return [p * (1 - f) + q * f for p, q in zip(a, b)]
    for f in (0.38, 0.62):                                             # inset across the top edge
        top = mix(rows[-1], rows[-2], f)[1:-1]
        POCKET_SEWING.append(tube("stitch", lift(top, 0.02 * CM), 0.06 * CM, MAT["fleece"], n=6))
    for i0, i1 in ((0, 1), (-1, -2)):
        side = [r[i0] * 0.62 + r[i1] * 0.38 for r in rows[1:-1]]
        POCKET_SEWING.append(tube("stitch", lift(side, 0.02 * CM), 0.06 * CM, MAT["fleece"], n=6))
        opening = [r[i0] for r in rows[4:12]]                           # the opening's folded edge
        POCKET_SEWING.append(tube("hem", lift(opening, -0.1 * CM), 0.17 * CM, MAT["fleece"], n=8))
    return pk


# ================================================================ the trousers
def trousers(hem_z):
    o = part(JEANS_SRC, "trousers", [MAT["track"], MAT["rib"]]); subdivide(o, 1)
    P = verts_np(o); N = normals_np(o); out = P.copy(); cuff = np.zeros(len(P), bool)
    ankle_z = J("foot.L")[2]; knee_z = J("lowerleg01.L")[2]; crotch_z = J("upperleg01.L")[2] - 0.9
    for i, (p, n) in enumerate(zip(P, N)):
        p = Vector(p); n = Vector(n); side = "L" if p.x > 0 else "R"; sg = 1 if side == "L" else -1
        above = p.z > knee_z
        a = J(f"upperleg01.{side}") if above else J(f"lowerleg01.{side}")
        b2 = J(f"upperleg02.{side}", "tail") if above else J(f"lowerleg02.{side}", "tail"); ax = (b2 - a).normalized()
        r = p - a; r = r - ax * r.dot(ax); phi = math.atan2(r.x * sg, -r.y)        # round the leg: 0 front, + outside
        h = p.z - ankle_z
        # real track trousers: roomy at the seat and the thigh (about 2.4 cm off the body there, 9-10 cm more round the
        # thigh), easing over the knee and tapering down the shin to the elastic cuff; less ease on the inside of the
        # thigh, where the legs nearly meet
        t = smooth01(ankle_z + 0.4, knee_z, p.z)                                       # 0 at the cuff, 1 at the knee
        ease = 0.5 + 0.3 * t + 0.25 * smooth01(knee_z, knee_z + 1.6, p.z)               # cm, slim joggers: 0.5 cuff, 0.8 knee, 1.05 thigh
        inner = max(0.0, -math.sin(phi)) if above else 0.0
        ease *= 1 - 0.45 * inner
        # under the buttocks and the backs of the thighs, where he sits, the cloth lies close (pressed on the chair seat:
        # 3 mm); at the front of the hip, where the thigh folds up when he sits, less room
        under = max(0.0, n.y) * smooth01(knee_z + 0.2, knee_z + 0.8, p.z) * (1 - smooth01(crotch_z + 1.2, crotch_z + 1.8, p.z))
        crease_f = max(0.0, -n.y) * smooth01(crotch_z - 0.3, crotch_z + 0.6, p.z) * (1 - smooth01(crotch_z + 1.4, crotch_z + 2.0, p.z))
        ease = ease * (1 - 0.85 * min(1.0, 2.0 * under)) * (1 - 0.5 * crease_f)
        d = ease * CM
        d += 0.25 * CM * math.sin(4 * phi + 0.7) * (1 - smooth01(0.0, 2.5, abs(p.z - knee_z)))   # soft knee folds
        # the weight of the fabric: long soft folds falling down the front of the thigh, and drag lines from the crotch
        thigh = smooth01(knee_z + 0.3, knee_z + 1.2, p.z) * (1 - smooth01(crotch_z - 0.9, crotch_z - 0.3, p.z))
        d += thigh * (0.12 * CM - 0.35 * CM * crease(p.z + 0.22 * phi, 0.9, 0.12)) * max(0.0, math.cos(phi)) ** 0.5
        drag = smooth01(crotch_z - 1.6, crotch_z - 0.2, p.z) * (1 - smooth01(crotch_z - 0.2, crotch_z + 0.3, p.z)) * inner
        d += drag * 0.35 * CM * math.sin(2 * math.pi * (p.z * 1.6 + 0.9 * phi)) * smooth01(-0.2, 0.3, n.y)   # (not at the front)
        w = smooth01(0.35, 0.6, h) * (1 - smooth01(1.2, 1.7, h))                             # stacking above the cuffs
        d += w * 0.35 * CM * math.sin(2 * math.pi * h / 0.3 + 1.2 * math.sin(2 * phi))
        if h < 0.4: cuff[i] = True; d = 0.35 * CM
        out[i] = np.array(p + n * d)
    for i in np.nonzero(cuff)[0]:                                                       # elastic cuffs gather in
        p = Vector(out[i]); side = "L" if p.x > 0 else "R"; a = J(f"lowerleg02.{side}", "tail")
        r = p - a; r.z = 0; out[i] = np.array(p - r * 0.14)
    # SLIM (the owner: "too puffed"): slim tapered joggers, capped at a distance from the skin: 1.1 cm at the thigh, 0.8 at
    # the knee, 0.6 down the calf (1 cm just above the cuff, where it stacks); the seat and thighs never balloon
    for i, p in enumerate(out):
        if cuff[i]: continue
        loc, nor, _, dd = BODY_BVH.find_nearest(Vector(p))
        if loc is None or (Vector(p) - loc).dot(nor) < 0: continue
        h = p[2] - ankle_z
        cap = (0.6 + 0.2 * smooth01(knee_z - 1.2, knee_z, p[2]) + 0.3 * smooth01(knee_z, knee_z + 1.2, p[2])
               + 0.4 * smooth01(0.3, 0.5, h) * (1 - smooth01(1.3, 1.8, h))) * CM
        if dd > cap: out[i] = np.array(loc + nor * cap)
    # under the hoodie the waist is snug to the body (2.5 mm), blending back to the relaxed fit 7 cm below the hem, so the
    # gathered hem band always lies over it (it poked through the band at the hips)
    for i, p in enumerate(out):
        k = smooth01(hem_z - 0.7, hem_z + 0.1, p[2])
        if k <= 0: continue
        loc, nor, _, _ = BODY_BVH.find_nearest(Vector(p))
        out[i] = p * (1 - k) + np.array(loc + nor * 0.25 * CM) * k
    # where he sits (the crotch, the buttocks' undersides and the backs and insides of the thighs) the cloth lies 4.5 mm
    # off the skin, as trousers pressed on a chair seat do; the source suit's crotch hung up to 5 cm below the body there
    # and went through the seat when he sat
    for i, p in enumerate(out):
        nn = Vector(N[i]); x, y, z = p
        zone = smooth01(knee_z + 0.4, knee_z + 1.0, z) * (1 - smooth01(crotch_z + 0.5, crotch_z + 1.1, z))
        k = zone * max(min(1.0, 1.6 * max(0.0, nn.y)), (1 - smooth01(0.35, 0.9, abs(x))) * smooth01(-0.45, -0.1, nn.y), min(1.0, 1.6 * max(0.0, -nn.z)))
        if k <= 0: continue
        loc, nor, _, d = BODY_BVH.find_nearest(Vector(p))
        if d > 0.45 * CM: out[i] = p * (1 - k) + np.array(loc + nor * 0.45 * CM) * k
    set_verts(o, out)
    for poly in o.data.polygons: poly.material_index = 1 if all(cuff[v] for v in poly.vertices) else 0
    push_out(o, 0.35 * CM)
    # the front of the crotch and the tops of the thighs: a smooth drape, as real trousers fall over the body there (they
    # never follow its shape). The front is a height field (how far forward, over x and height): the cloth goes to the
    # further forward of the body's front widened (4 cm across) and smoothed (plus 7 mm), and the cloth's own front smoothed
    # (2 cm); vertices move only forward or back, so nothing folds
    P = verts_np(o); Nn = normals_np(o)
    fz = [i for i, p in enumerate(P) if (Nn[i][1] < -0.1 or (abs(p[0]) < 0.4 and Nn[i][1] < 0.35)) and crotch_z - 0.8 < p[2] < hem_z + 0.4 and abs(p[0]) < 1.35]
    gx = np.arange(-1.5, 1.5001, 0.1); gz = np.arange(crotch_z - 1.0, hem_z + 0.6, 0.1)
    E = np.full((len(gz), len(gx)), np.nan)
    for a, z in enumerate(gz):
        for b, x in enumerate(gx):
            h = BODY_BVH.ray_cast(Vector((x, -6, z)), Vector((0, 1, 0)), 8)
            if h[0] is not None: E[a, b] = -h[0].y                     # how far forward the body is
    def blur(F, sig, iters=1):
        k = np.exp(-0.5 * (np.arange(-3, 4) / sig) ** 2); k /= k.sum(); F = F.copy()
        for _ in range(iters):
            F = np.apply_along_axis(lambda r: np.convolve(np.pad(r, 3, mode="edge"), k, "valid"), 1, F)
            F = np.apply_along_axis(lambda c: np.convolve(np.pad(c, 3, mode="edge"), k, "valid"), 0, F)
        return F
    Ed = np.where(np.isnan(E), -9.0, E); D = Ed.copy()
    for da in (-1, 0, 1):                                             # widen: 1 cm up and down, 4 cm across (the front panel
        for db in range(-4, 5):                                       # spans the dip between the thighs at the crotch)
            D = np.maximum(D, np.roll(np.roll(Ed, da, 0), db, 1) - 0.004 * abs(db))
    D = np.where(D < -8, np.nan, D); Dn = np.where(np.isnan(D), np.nanmin(D), D); Ds = np.where(np.isnan(D), np.nan, blur(Dn, 1.2, 2))
    C = np.zeros_like(E); W_ = np.zeros_like(E)                       # the cloth's own front, binned
    for i in fz:
        a = int(round((P[i][2] - gz[0]) / 0.1)); b = int(round((P[i][0] - gx[0]) / 0.1))
        if 0 <= a < len(gz) and 0 <= b < len(gx): C[a, b] += -P[i][1]; W_[a, b] += 1
    C = np.where(W_ > 0, C / np.maximum(W_, 1), np.nan)
    for _ in range(6):                                                # fill the empty cells from their neighbours
        F = np.where(np.isnan(C), 0, C); Wn = (~np.isnan(C)).astype(float)
        S = sum(np.roll(np.roll(F, da, 0), db, 1) for da in (-1, 0, 1) for db in (-1, 0, 1))
        N_ = sum(np.roll(np.roll(Wn, da, 0), db, 1) for da in (-1, 0, 1) for db in (-1, 0, 1))
        C = np.where(np.isnan(C) & (N_ > 0), S / np.maximum(N_, 1), C)
    Cs = blur(np.where(np.isnan(C), np.nanmean(C), C), 2.0, 2)
    def sample(F, x, z):
        fa = (z - gz[0]) / 0.1; fb = (x - gx[0]) / 0.1; a0_ = int(np.clip(np.floor(fa), 0, len(gz) - 2)); b0_ = int(np.clip(np.floor(fb), 0, len(gx) - 2))
        ta, tb = min(max(fa - a0_, 0), 1), min(max(fb - b0_, 0), 1)
        return (F[a0_, b0_] * (1 - ta) * (1 - tb) + F[a0_ + 1, b0_] * ta * (1 - tb) + F[a0_, b0_ + 1] * (1 - ta) * tb + F[a0_ + 1, b0_ + 1] * ta * tb)
    for i in fz:
        x, y, z = P[i]
        w = (1 - smooth01(0.95, 1.35, abs(x))) * smooth01(crotch_z - 0.8, crotch_z - 0.45, z) * (1 - smooth01(hem_z, hem_z + 0.4, z)) * max(smooth01(-0.1, -0.4, Nn[i][1]), (1 - smooth01(0.25, 0.4, abs(x))) * smooth01(0.35, 0.1, Nn[i][1]))
        env = sample(Ds, x, z); own = sample(Cs, x, z)
        tgt = own if np.isnan(env) else max(own, env + 0.7 * CM)
        P[i][1] = y * (1 - w) + (-tgt) * w
    set_verts(o, P)
    # where the legs meet (the crotch junction) the snug pull towards the nearest skin flips between the two legs and
    # crumples a few faces: relaxed smooth there
    P = verts_np(o); cj = [i for i, p in enumerate(P) if abs(p[0]) < 0.5 and crotch_z - 0.9 < p[2] < crotch_z + 0.35]
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    for _ in range(14): bmesh.ops.smooth_vert(bm, verts=[bm.verts[i] for i in cj], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    P = verts_np(o); Nn = normals_np(o)
    for i in fz:
        x, z = P[i][0], P[i][2]; d = 0.0
        for sg in (1, -1):                                              # from beside the crotch down the inner thigh
            ax_, az_ = sg * 0.14, crotch_z + 0.05; bx_, bz_ = sg * 0.5, crotch_z - 0.95
            vx, vz = bx_ - ax_, bz_ - az_; L2 = vx * vx + vz * vz; t = max(0.0, min(1.0, ((x - ax_) * vx + (z - az_) * vz) / L2))
            dist = math.hypot(x - ax_ - t * vx, z - az_ - t * vz); fade = math.sin(math.pi * t) ** 0.6
            d += fade * (-0.38 * math.exp(-(dist / 0.07) ** 2) + 0.16 * math.exp(-((dist - 0.13) / 0.07) ** 2))
        P[i] = P[i] + Nn[i] * d * CM
    set_verts(o, P)
    push_out(o, 0.3 * CM, iters=1)
    print("TROUSERS front drape vertices:", len(fz), "crotch junction relaxed:", len(cj))
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
    # a short fly: a J of topstitching on his left of the centre front, from under the hoodie's hem down and round to the
    # crotch seam, and the centre seam below it; tonal thread, a raised line on the fabric
    def on_front(xz):
        out_ = []
        for x, z in xz:
            h = bvh.ray_cast(Vector((x, -6, z)), Vector((0, 1, 0)))
            if h[0] is not None: out_.append(h[0] + h[1] * 0.03 * CM)
        return out_
    ztop, zturn, zbot = hem_z + 0.2, crotch_z + 0.55, crotch_z + 0.18
    jx = [(0.3, ztop - (ztop - zturn) * k / 10) for k in range(11)] + \
         [(0.3 * math.cos(math.pi / 2 * k / 8), zturn - (zturn - zbot) * math.sin(math.pi / 2 * k / 8)) for k in range(1, 9)]
    stripes.append(tube("fly", on_front(jx), 0.05 * CM, MAT["cord"], n=6))
    stripes.append(tube("seam", on_front([(0.0, ztop - (ztop - crotch_z + 0.1) * k / 14) for k in range(15)]), 0.045 * CM, MAT["cord"], n=6))
    return o, stripes


# ================================================================ socks and slides
def socks():
    """white crew socks: the body's feet and lower shins, 2 mm out; over the toes one soft toe box (no toes of their
    own), slight compression folds at the ankle, a ribbed cuff"""
    top = J("foot.L")[2] + 0.95
    keep = [f for f in BODY_F if all(B(REST[i]).z < top for i in f)]
    ids = sorted({i for f in keep for i in f}); remap = {v: k for k, v in enumerate(ids)}
    o = mesh_obj("socks", [B(REST[i]) for i in ids], [[remap[i] for i in f] for f in keep], [MAT["sock"], MAT["sockrib"]])
    subdivide(o, 1)                                             # fine enough for the folds and a round toe box
    P = verts_np(o); N = normals_np(o); P += N * 0.2 * CM; set_verts(o, P)
    push_out(o, 0.25 * CM, iters=2)
    # the toe box (a morphological closing of the skin): the front of the foot is smoothed well inside the skin, then
    # every front vertex goes out along the smoothed normal to just past the OUTERMOST skin hit of a disk of rays 16 mm
    # across, so the knit bridges the toes as one soft shape (as a sock does) and never enters the skin
    ty = J("foot.L", "tail").y + 0.9
    front = [v.index for v in o.data.vertices if v.co.y < ty and v.co.z < J("foot.L")[2] + 0.45]
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    for _ in range(40): bmesh.ops.smooth_vert(bm, verts=[bm.verts[i] for i in front], factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    def close(gap, only_out):
        S = verts_np(o); NS = normals_np(o); P = S.copy(); r = 0.8 * CM
        for i in front:
            base, n = Vector(S[i]), Vector(NS[i]).normalized(); t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
            best = None
            offs = [Vector((0, 0, 0))] + [(t1 * math.cos(k * math.pi / 4) + t2 * math.sin(k * math.pi / 4)) * rr for rr in (r * 0.5, r) for k in range(8)]
            for off in offs:
                hit = BODY_BVH.ray_cast(base + n * 1.2 + off, -n, 2.5)
                if hit[0] is not None:
                    t = (hit[0] - base).dot(n); best = t if best is None else max(best, t)
            if best is not None and (not only_out or best + gap > 0): P[i] = np.array(base + n * (best + gap))
        set_verts(o, P)
    def relax(passes, fac):
        bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
        for _ in range(passes): bmesh.ops.smooth_vert(bm, verts=[bm.verts[i] for i in front], factor=fac, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.to_mesh(o.data); bm.free(); o.data.update()
    close(0.3 * CM, False); relax(10, 0.5)                       # no creases left from the closure ...
    close(0.25 * CM, True); relax(2, 0.3)                        # ... and nothing let back into the skin
    fs = set(front); keep_front = {i: o.data.vertices[i].co.copy() for i in fs}
    push_out(o, 0.25 * CM, iters=2)                              # the rest of the sock (the front stays on its closure)
    for i, c in keep_front.items(): o.data.vertices[i].co = c
    o.data.update()
    # a toe-box vertex the closure's rays missed stays where the smoothing shrank it, inside the foot: those go out
    # to 2.5 mm off the nearest skin (a vertex is inside if an odd number of skin crossings lie on 2 of 3 rays)
    stuck = 0
    for i in fs:
        p = o.data.vertices[i].co
        if inside_body(p):
            loc, nor, _, _ = BODY_BVH.find_nearest(p); o.data.vertices[i].co = loc + nor * 0.25 * CM; stuck += 1
    o.data.update(); print("SOCK toe-box vertices put back outside the skin:", stuck)
    # slight folds at the ankle: a few soft rings, each wavering in height and fading round the leg, 1.5 mm proud
    P = verts_np(o); N = normals_np(o); rng = random.Random(11)
    for sgn, s in ((1, "L"), (-1, "R")):
        c = J(f"foot.{s}"); rings = [(c.z + dz * CM, rng.uniform(0, 2 * math.pi), rng.uniform(0.6, 1.0)) for dz in (-0.6, 0.6, 1.8, 3.0, 4.1)]
        for i, p in enumerate(P):
            if p[0] * sgn <= 0 or p[2] < c.z - 0.15 or p[2] > top - 0.4: continue
            th = math.atan2(p[1] - c.y, (p[0] - c.x) * sgn); d = 0.0
            for zk, ph, amp in rings:
                zz = zk + 0.04 * math.sin(th + ph) + 0.02 * math.sin(2 * th + 1.7 * ph)
                d += amp * math.exp(-((p[2] - zz) / 0.045) ** 2) * (0.5 + 0.5 * math.cos(th - ph)) ** 0.7
            fade = smooth01(c.z - 0.15, c.z - 0.02, p[2]) * (1 - smooth01(top - 0.6, top - 0.42, p[2]))
            P[i] = P[i] + N[i] * 0.15 * CM * min(d, 1.2) * fade
    set_verts(o, P)
    # natural creases where a worn sock bunches: soft transverse grooves across the toe box (where the toes bend) and
    # just behind the strap, each a 1 mm groove with a slight ridge either side, fading out along its length
    P = verts_np(o); N = normals_np(o); rng = random.Random(5)
    for sgn, s_ in ((1, "L"), (-1, "R")):
        F = P[P[:, 0] * sgn > 0.3]; ymin, ymax = F[:, 1].min(), F[:, 1].max(); L = ymax - ymin
        xc = (F[:, 0].min() + F[:, 0].max()) / 2
        lines = [(ymin + L * f + rng.uniform(-0.04, 0.04), rng.uniform(-0.35, 0.35), rng.uniform(0.7, 1.0), rng.uniform(-0.25, 0.25))
                 for f in (0.08, 0.13, 0.18, 0.54, 0.6)]
        for i, p in enumerate(P):
            if p[0] * sgn <= 0.3 or N[i][2] < 0.15 or p[1] > ymin + 0.68 * L: continue
            d = 0.0
            for y0, ang, amp, off in lines:                             # a line across the foot, a little skewed
                u = (p[0] - xc) * sgn - off; dist = (p[1] - y0) - math.tan(ang) * u
                fade = math.exp(-(u / 0.32) ** 2) * amp
                d += fade * (-0.1 * math.exp(-(dist / 0.02) ** 2) + 0.045 * math.exp(-((abs(dist) - 0.04) / 0.02) ** 2))   # cm
            P[i] = P[i] + N[i] * d * CM
    set_verts(o, P)
    for poly in o.data.polygons:
        poly.material_index = 1 if min(o.data.vertices[v].co.z for v in poly.vertices) > top - 0.35 else 0
    return o, ids


MISSES = [0]
SLIDE_FLOOR = [None]
def slides(sock_obj):
    """black rubber slides, from photos of generic pool slides: a contoured footbed (2.3 cm under the heel, 1.5 cm at
    the toe, a toe spring, the heel cup and side rims, soft rounded edges) about 1 cm wider than the foot, the foot
    sitting in it; one wide padded strap (7.5 cm front to back) over the forefoot to just before the toes, moulded
    into the footbed's sides"""
    bvh = bvh_of(sock_obj); parts = []; S = verts_np(sock_obj); K = 64
    for sgn in (1, -1):
        F = S[S[:, 0] * sgn > 0.3]; zb = F[:, 2].min()
        foot = F[F[:, 2] < zb + 2.5 * CM]                                   # the plan-view silhouette of the foot
        cx, cy = (foot[:, 0].min() + foot[:, 0].max()) / 2, (foot[:, 1].min() + foot[:, 1].max()) / 2
        ymin, ymax = foot[:, 1].min(), foot[:, 1].max(); L = ymax - ymin  # toe tip (front is -y), heel
        rel = foot[:, :2] - [cx, cy]; ang = np.arctan2(rel[:, 1], rel[:, 0]); dist = np.hypot(rel[:, 0], rel[:, 1])
        R = []
        for k in range(K):
            a = 2 * math.pi * k / K; da = np.abs((ang - a + math.pi) % (2 * math.pi) - math.pi)
            sel = dist[da < math.radians(9)]; R.append(sel.max() if len(sel) else 0.5)
        for _ in range(3): R = [(R[k - 1] + 2 * R[k] + R[(k + 1) % K]) / 4 for k in range(K)]
        DIR = [(math.cos(2 * math.pi * k / K), math.sin(2 * math.pi * k / K)) for k in range(K)]
        fr = [max(0.0, -d[1]) for d in DIR]; bk = [max(0.0, d[1]) for d in DIR]
        R = [R[k] + (0.55 + 0.65 * fr[k] ** 2 + 0.1 * bk[k] ** 2) * CM for k in range(K)]   # 5.5 mm at the sides, 12 at the toe
        heel_bot = zb - 2.3 * CM; SLIDE_FLOOR[0] = heel_bot if SLIDE_FLOOR[0] is None else min(SLIDE_FLOOR[0], heel_bot)
        def bottom(y):                                                      # flat to the ball, then the toe spring
            s = (ymax - y) / L; return heel_bot + 0.8 * CM * smooth01(0.6, 1.08, s) ** 1.4
        def contact(x, y):                                                  # the sock's underside here (or None)
            h = bvh.ray_cast(Vector((x, y, zb - 0.5)), Vector((0, 0, 1)), 1.0)
            return h[0].z if h[0] is not None else None
        def pt(k, inset): r = max(R[k] - inset * CM, 0.0); return cx + r * DIR[k][0], cy + r * DIR[k][1]
        # the footbed's top: the sock's underside 1 mm up into it (the foot sits in the bed), never more than 9 mm
        # above the sole's lowest point (the arch), smoothed; outside the foot the bed carries on from the inside
        top_fr = [0.0, 0.16, 0.30, 0.44, 0.58, 0.72, 0.86, 1.0]           # of the radius inside the 1.5 cm inset
        Hraw = np.full((len(top_fr), K), np.nan)
        for j, f in enumerate(top_fr):
            for k in range(K):
                x, y = cx + (R[k] - 1.5 * CM) * f * DIR[k][0], cy + (R[k] - 1.5 * CM) * f * DIR[k][1]
                z = contact(x, y)
                if z is not None and z < zb + 0.9 * CM: Hraw[j, k] = z - 0.1 * CM
        for j in range(len(top_fr)):
            for k in range(K):
                if np.isnan(Hraw[j, k]): Hraw[j, k] = Hraw[j - 1, k] if j else np.nanmin(Hraw)
        H = Hraw.copy()
        for _ in range(4):
            Hs = H.copy()
            for j in range(len(top_fr)):
                for k in range(K):
                    nb = [H[j, k - 1], H[j, (k + 1) % K]] + ([H[j - 1, k]] if j else []) + ([H[j + 1, k]] if j + 1 < len(top_fr) else [])
                    Hs[j, k] = 0.5 * H[j, k] + 0.5 * sum(nb) / len(nb)
            H = np.minimum(Hs, Hraw + 0.05 * CM)                            # smoothing never lifts it into the sock
        H[0, :] = H[0, :].mean()
        rim = [H[-1, k] + (0.25 + 0.22 * bk[k] - 0.1 * fr[k]) * CM for k in range(K)]   # the heel cup, side rims, toe lip
        rings = []                                                          # (points, material) from the top centre out and round under
        for j, f in enumerate(top_fr):
            rings.append([(cx + (R[k] - 1.5 * CM) * f * DIR[k][0], cy + (R[k] - 1.5 * CM) * f * DIR[k][1], H[j, k]) for k in range(K)])
        for inset, zf in ((1.15, lambda k: H[-1, k] + 0.4 * (rim[k] - H[-1, k])), (0.85, lambda k: rim[k] - 0.04 * CM), (0.6, lambda k: rim[k])):
            rings.append([(*pt(k, inset), zf(k)) for k in range(K)])
        r_t = 0.6                                                           # the rounded top edge, 6 mm
        for deg in (45, 90):
            rings.append([(*pt(k, r_t * (1 - math.sin(math.radians(deg)))), rim[k] - r_t * CM * (1 - math.cos(math.radians(deg)))) for k in range(K)])
        rings.append([(*pt(k, 0.0), (rim[k] - r_t * CM + bottom(pt(k, 0)[1]) + 0.3 * CM) / 2) for k in range(K)])   # the side wall
        r_b = 0.3                                                           # the rounded bottom edge, 3 mm
        for deg in (0, 45, 90):
            rings.append([(*pt(k, r_b * (1 - math.cos(math.radians(deg)))), bottom(pt(k, 0)[1]) + r_b * CM * (1 - math.sin(math.radians(deg)))) for k in range(K)])
        for f in (0.66, 0.33, 0.0):
            rings.append([(cx + (R[k] - r_b * CM) * f * DIR[k][0], cy + (R[k] - r_b * CM) * f * DIR[k][1], bottom(cy + (R[k] - r_b * CM) * f * DIR[k][1])) for k in range(K)])
        bm = bmesh.new(); V = [[bm.verts.new(p) for p in ring] for ring in rings]
        n_top = len(top_fr) + 1                                             # footbed: the top up to the 1.15 cm inset
        for j in range(len(V) - 1):
            for k in range(K):
                q = [V[j][k], V[j][(k + 1) % K], V[j + 1][(k + 1) % K], V[j + 1][k]]
                if j == 0 or j == len(V) - 2:                               # the centres: collapse into triangles
                    q = [V[j][k], V[j + 1][(k + 1) % K], V[j + 1][k]] if j == 0 else [V[j][k], V[j][(k + 1) % K], V[j + 1][k]]
                try:
                    fc = bm.faces.new(q); fc.material_index = 1 if j < n_top - 1 else 0; fc.smooth = True
                except ValueError: pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new("slide_sole"); bm.to_mesh(me); bm.free()
        so = bpy.data.objects.new("slide_sole", me); SC.collection.objects.link(so)
        me.materials.append(MAT["rubber"]); me.materials.append(MAT["footbed"]); me.materials.append(MAT["strap"]); parts.append(so)
        for p in me.polygons: p.use_smooth = True
        # the strap: 7.5 cm from just behind the toes back over the forefoot; inside it 2 mm off the sock, padded (9 mm
        # thick over the top of the foot, 4.5 mm where it goes into the sole), its front and back edges rounded
        def edge_x(y, side):                                                # the bed's outline at this y, on this side
            best = None
            for k in range(K):
                if DIR[k][0] * side <= 0: continue
                x, yy = pt(k, 0.0); x2, yy2 = pt((k + 1) % K, 0.0)
                if (yy - y) * (yy2 - y) <= 0 and yy != yy2:
                    xx = x + (x2 - x) * (y - yy) / (yy2 - yy)
                    if best is None or (xx - cx) * side > (best - cx) * side: best = xx
            return best
        def rim_at(x, y):
            k = min(range(K), key=lambda k: (pt(k, 0.0)[0] - x) ** 2 + (pt(k, 0.0)[1] - y) ** 2); return rim[k]
        y_front = ymin + 0.215 * L; NV_, NU = 13, 25
        inner = []
        for jv in range(NV_):
            y = y_front + 7.5 * CM * (0.5 - 0.5 * math.cos(math.pi * jv / (NV_ - 1)))   # rows closer at the edges
            band = foot[np.abs(foot[:, 1] - y) < 0.6 * CM]; xc = (band[:, 0].min() + band[:, 0].max()) / 2
            o_ = Vector((xc, y, zb + 0.6 * CM)); row = []
            for ju in range(NU):
                a = math.pi * ju / (NU - 1); d = Vector((math.cos(a), 0, math.sin(a)))
                hit = bvh.ray_cast(o_ + d * 3, -d, 6.0)
                if hit[0] is None: MISSES[0] += 1
                row.append((hit[0] if hit[0] is not None else bvh.find_nearest(o_ + d * 0.6)[0]) + d * 0.2 * CM)   # (a miss: the nearest sock point)
            # each end goes down over the bed's rounded edge into its side wall
            for side, end in ((1, 0), (-1, -1)):
                p0 = row[end]; xe = edge_x(y, side) - side * 0.45 * CM; ze = rim_at(xe, y) - 0.8 * CM
                ext = [Vector((p0.x + (xe - p0.x) * smooth01(0, 1, t), y, p0.z + (ze - p0.z) * t)) for t in (0.35, 0.7, 1.0)]
                row = (ext[::-1] + row) if end == 0 else (row + ext)
            inner.append(row)
        nu = len(inner[0]); o_c = [Vector((sum(p.x for p in r) / nu, r[0].y, zb)) for r in inner]
        def thick(ju, v):
            u = ju / (nu - 1); mid = math.sin(math.pi * min(max((u * nu - 3) / (nu - 6), 0), 1)) ** 0.6
            return (0.45 + 0.45 * mid) * CM * max(0.0, 1 - abs(2 * v - 1) ** 5) ** 0.35
        outer = []
        for jv in range(NV_):
            v = 0.5 - 0.5 * math.cos(math.pi * jv / (NV_ - 1)); row = []
            for ju in range(nu):
                tu = inner[jv][min(ju + 1, nu - 1)] - inner[jv][max(ju - 1, 0)]
                tv = inner[min(jv + 1, NV_ - 1)][ju] - inner[max(jv - 1, 0)][ju]
                n = tu.cross(tv).normalized()
                if n.dot(inner[jv][ju] - o_c[jv]) < 0: n = -n
                row.append(inner[jv][ju] + n * thick(ju, v))
            outer.append(row)
        loop = inner + outer[::-1]                                          # round the strap's section: inside front to back, outside back to front
        st = grid_obj("slide_strap", [[p for p in r] for r in loop] + [loop[0]], MAT["strap"])
        bm = bmesh.new(); bm.from_mesh(st.data); bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(st.data); bm.free()
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
HOODIE = join([shell, hood, pk] + cords + POCKET_SEWING + HOOD_EDGE, "hoodie_black")
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
def garment_weights(name, o):
    """skin weights: the mix of the three body vertices' weights (MakeHuman's rule)"""
    b = BIND[name]
    wm = (WMAT[b["ref"][:, 0]] * b["w"][:, 0, None] + WMAT[b["ref"][:, 1]] * b["w"][:, 1, None] + WMAT[b["ref"][:, 2]] * b["w"][:, 2, None])
    return wm


for name, o in GARMENTS.items():
    skin(o, garment_weights(name, o))


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

# ================================================================ G2's body, dressed: the clothes added to boy_g2.glb itself
# (preview/mh-motion, room_build/mh/glb), skinned to ITS skin: the same 163 joints, rest pose and names, so its clips
# (clips_g2) drive the clothes too. Each garment vertex takes the four strongest of its weights (the mix of its three
# body vertices' default_weights, as MakeHuman does), the body's triangles under the clothes are dropped (MakeHuman's
# delete_verts), and nothing else in the file changes. Positions in G2's metres: to_g2().
import glb_io
G2_GLB = arg("--g2", os.path.join(HERE, "g2", "boy_g2.glb"))
def export_g2(path):
    js, bn = glb_io.read(G2_GLB); W = glb_io.Writer(js, bn)
    rest = json.load(open(os.path.join(os.path.dirname(G2_GLB), "boy_g2_rest.json")))
    jidx = {n: k for k, n in enumerate(rest["order"])}; bone_j = np.array([jidx[n] for n in BONES])
    ibm = glb_io.accessor(js, bn, js["skins"][0]["inverseBindMatrices"]).reshape(-1, 4, 4)
    for n, k in jidx.items():                                   # the skin's joint k is rest["order"][k]: its bind sits at its head
        assert np.allclose(-ibm[k, 3, :3], to_g2(np.array(SKEL[n]["head"])), atol=1e-5), ("joint order", n)
    nbody = len(BODY_IDS); gl = {v: k for k, v in enumerate(BODY_IDS)}
    prim = js["meshes"][0]["primitives"][0]
    def tris(faces):
        out = []
        for f in faces:
            q = [gl[v] for v in f]; out += q[:3] + ([q[0], q[2], q[3]] if len(q) == 4 else [])
        return np.array(out, np.uint32)
    old = glb_io.accessor(js, bn, prim["indices"])
    assert np.array_equal(old.astype(np.uint32), tris(BODY_F)), "G2's body triangles are not the base mesh's"
    hide = set()
    for v in DELETE.values(): hide |= set(v)
    kept = tris([f for f in BODY_F if not all(v in hide for v in f)])
    prim["indices"] = W.acc(kept, "SCALAR", 34963)
    mats = {}
    def material(name):
        if name in mats: return mats[name]
        m = MAT[name]; f = FABRICS.get(name, {})
        pbr = {"metallicFactor": 0.0, "roughnessFactor": float(m["rough"])}
        mat = {"name": name, "pbrMetallicRoughness": pbr}
        if m.get("color_map"):
            pbr["baseColorTexture"] = {"index": W.image(m["color_map"])}
            mat["normalTexture"] = {"index": W.image(m["normal_map"])}
        else: pbr["baseColorFactor"] = list(m["rgb"]) + [1.0]
        if f.get("sheen", (0, 0))[0]:
            mat["extensions"] = {"KHR_materials_sheen": {"sheenColorFactor": [f["sheen"][1]] * 3, "sheenRoughnessFactor": 0.45}}
            js.setdefault("extensionsUsed", []); "KHR_materials_sheen" in js["extensionsUsed"] or js["extensionsUsed"].append("KHR_materials_sheen")
        js["materials"].append(mat); mats[name] = len(js["materials"]) - 1; return mats[name]
    for gname, o in GARMENTS.items():
        me = o.data; me.update(); wm = garment_weights(gname, o)
        top = np.argsort(-wm, 1)[:, :4]; tw = np.take_along_axis(wm, top, 1); tw /= np.maximum(tw.sum(1, keepdims=True), 1e-9)
        P = to_g2(np.array([MHv(v.co) for v in me.vertices])); Nn = np.array([MHv(v.normal) for v in me.vertices])
        uvl = me.uv_layers["UVMap"].data; prims = []
        for mi in range(len(me.materials)):
            key, vp, vuv, idx = {}, [], [], []
            for p in me.polygons:
                if p.material_index != mi: continue
                corner = []
                for li in p.loop_indices:
                    vi = me.loops[li].vertex_index; uv = tuple(round(c, 6) for c in uvl[li].uv)
                    k = key.setdefault((vi, uv), len(key))
                    if k == len(vp): vp.append(vi); vuv.append((uv[0], 1 - uv[1]))
                    corner.append(k)
                for t in range(1, len(corner) - 1): idx += [corner[0], corner[t], corner[t + 1]]
            if not idx: continue
            vp = np.array(vp)
            prims.append({"attributes": {
                "POSITION": W.acc(P[vp].astype(np.float32), "VEC3", 34962, minmax=True),
                "NORMAL": W.acc(Nn[vp].astype(np.float32), "VEC3", 34962),
                "TEXCOORD_0": W.acc(np.array(vuv, np.float32), "VEC2", 34962),
                "JOINTS_0": W.acc(bone_j[top[vp]].astype(np.uint16), "VEC4", 34962),
                "WEIGHTS_0": W.acc(tw[vp].astype(np.float32), "VEC4", 34962)},
                "indices": W.acc(np.array(idx, np.uint32), "SCALAR", 34963), "material": material(me.materials[mi].name)})
        js["meshes"].append({"name": gname, "primitives": prims})
        js["nodes"].append({"name": gname, "mesh": len(js["meshes"]) - 1, "skin": 0})
        js["scenes"][js.get("scene", 0)]["nodes"].append(len(js["nodes"]) - 1)
    js.setdefault("asset", {})["generator"] = "SUB-01 clothes_mh/build_clothes.py (G2's body + G4's clothes)"
    W.write(path); print("wrote", path, round(os.path.getsize(path) / 1e6, 2), "MB; body triangles hidden:", (len(old) - len(kept)) // 3)
    json.dump({"hidden_body_vertices_mh": sorted(int(v) for v in hide),
               "note": "MakeHuman base-mesh vertex indices under the clothes (the union of the garments' delete_verts)"},
              open(os.path.join(os.path.dirname(path), "hidden_body_vertices.json"), "w"))


if os.path.exists(G2_GLB):
    os.makedirs(os.path.join(OUT, "g2"), exist_ok=True); export_g2(os.path.join(OUT, "g2", "boy_g2_dressed.glb"))
else: print("no", G2_GLB, ": the dressed G2 glb is not written")

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
    floor = SLIDE_FLOOR[0]                                     # the slides' soles stand on it
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


def overcast(on):
    """the comparison photos are outdoors under a soft grey sky: the studio lamps off, a bright even sky instead"""
    bg = SC.world.node_tree.nodes["Background"]
    for nm in ("key", "fill", "rim"): bpy.data.objects[nm].hide_render = on
    bg.inputs[0].default_value = (0.78, 0.8, 0.84, 1) if on else (0.26, 0.27, 0.29, 1)
    bg.inputs[1].default_value = 2.2 if on else 0.6
    if "sky" not in bpy.data.objects:
        ld = bpy.data.lights.new("sky", 'AREA'); ld.energy = 14000; ld.size = 40; lo = bpy.data.objects.new("sky", ld)
        lo.location = (4, 6, 30); SC.collection.objects.link(lo)
    bpy.data.objects["sky"].hide_render = not on


def compare_shots():
    """build_clothes.py's half of compare_real.py: each render matches its real photo's angle and light"""
    W_ = 520 if QUICK else 800; fl = J("foot.L"); fy = fl.y - 0.75
    overcast(True)
    # white socks: the photo looks at a foot from the front, a little from the outside, at shin height
    render(camera("k_sock", (fl.x + 1.3, fy - 4.6, FLOOR + 2.8), (fl.x, fy + 0.2, FLOOR + 0.9), 55), W_, W_, f"{SHEET_DIR}/cmp_sock.png")
    # the slide, as its wearer sees it: from above the knees, looking down the shins at the feet
    # (his belly would fill the frame: the hoodie and the body are left out of this one shot; the photo shows only a hem)
    for o in (HOODIE, body): o.hide_render = True
    render(camera("k_slide", (0.15, -3.4, FLOOR + 12.5), (0.0, fy - 0.7, FLOOR + 0.2), 60), W_, W_, f"{SHEET_DIR}/cmp_slide.png")
    for o in (HOODIE, body): o.hide_render = False
    # the trousers: a low camera in front, about knee height, looking a little up
    render(camera("k_trousers", (-3.0, -24, FLOOR + 5.0), (0, -0.2, FLOOR + 6.5), 50), W_, 2 * W_, f"{SHEET_DIR}/cmp_trousers.png")
    # the hoodie from behind, his right arm raised (as in the photo), the camera at chest height
    aim("upperarm01.R", (-0.62, -0.25, 0.75), "upperarm02.R"); aim("lowerarm01.R", (-0.12, -0.35, 1), "lowerarm02.R")
    render(camera("k_hoodie", (2.2, 15.5, 4.2), (-0.4, 0, 3.6), 50), W_, W_, f"{SHEET_DIR}/cmp_hoodie.png")
    overcast(False); pose_standing()


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
    # the feet: a 3/4 close-up, the side, from above (a little in front, past the trouser leg), the left foot
    bpy.context.view_layer.update(); fl = J("foot.L"); fy = fl.y - 0.75; FW = 520 if QUICK else 800
    render(camera("c_f34", (fl.x + 3.3, fy - 4.6, FLOOR + 2.7), (fl.x + 0.05, fy - 0.2, FLOOR + 0.45), 50), FW, FW, f"{SHEET_DIR}/feet_34.png")
    render(camera("c_fside", (fl.x + 12.0, fy, FLOOR + 0.9), (fl.x, fy, FLOOR + 0.75), 85), FW, FW, f"{SHEET_DIR}/feet_side.png")
    render(camera("c_ftop", (fl.x + 0.2, fy - 4.2, FLOOR + 10.5), (fl.x, fy - 0.4, FLOOR), 60), FW, FW, f"{SHEET_DIR}/feet_top.png")
    if not FEET_ONLY:
        compare_shots()
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
    # seated at the room's distance (5 m), the same direction as the seated shot
    tg = Vector((0, -1.6, -3.4)); dv = (Vector((-21, -15, 3.0)) - tg).normalized()
    render(camera("c_seat5", tg + dv * 50, tg, 50), FW, FW, f"{SHEET_DIR}/feet_room.png")
    if FEET_ONLY: print("DONE"); sys.exit(0)
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
