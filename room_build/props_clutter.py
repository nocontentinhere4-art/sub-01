# blender -b -P props_clutter.py            -> out/props_clutter_raw.glb (+ out/clutter_sweep.txt), then:
# node post_clutter.mjs out/props_clutter_raw.glb ../web/room/props_clutter.glb
#
# The room's lived-in hard props (#98, the owner: "fai una bottiglia per bene... e altre cose sparse per la stanza"):
# the water bottle he drinks from (the page's PROP.bottle takes this model; it keeps its place and origin), and the
# things lying about on the hard surfaces: a notebook with a pen and a pencil, wired earbuds and a phone charger cable on
# the desk, a glass of water on the window sill, an apple on the fridge, a small succulent on the bookshelf.
# Real photoscans where Poly Haven has them (CC0: binder_notebook, stationery_supplies, food_apple_01, potted_plant_04);
# the bottle, the glass, the earbuds and the charger are modelled here (CC0) at real sizes. No brands, logos or labels.
# Placed in world metres (glTF: x right, y up, z towards the viewer; the floor's top at y 0.16), clear of the places
# room.html hard-codes and of his walking graph (the same zones as build_room.py's sweep; out/clutter_sweep.txt).
import bpy, bmesh, math, os, sys, json, random
from mathutils import Vector, Matrix

R = os.path.dirname(os.path.abspath(__file__)); AS = f"{R}/assets"; TX = f"{R}/tex_final"; OUT = f"{R}/out"; os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
random.seed(23)

FY, DTOP, FTOP, WY0 = 0.16, 0.97, 1.27, 1.27                 # floor, desk top, fridge top, window sill (build_room.py)
IX, IZ = -1.9, -1.45                                          # the window wall's and the back wall's inner faces
SHELF_TOP_LEVEL = 1.70 + 0.018                                # the bookshelf's top board (LEVELS[4] + T)


def B(x, y, z): return Vector((x, -z, y))                    # glTF -> Blender
def G(v): return (v.x, v.z, -v.y)                            # Blender -> glTF


def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


# ---------------------------------------------------------------- materials
MATS = {}
def img(name, colour=True):
    im = bpy.data.images.load(f"{TX}/{name}", check_existing=True)
    if not colour: im.colorspace_settings.name = "Non-Color"
    return im


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, nor=None, nstr=1.0, mr=None, alpha=None, uv=0.1, diff_img=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; P = nt.nodes["Principled BSDF"]
    P.inputs["Base Color"].default_value = (*color, 1); P.inputs["Roughness"].default_value = rough; P.inputs["Metallic"].default_value = metal
    if diff_img is not None:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = diff_img; nt.links.new(t.outputs["Color"], P.inputs["Base Color"])
        nt.links.new(t.outputs["Alpha"], P.inputs["Alpha"])
    if nor:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(nor, False); n = nt.nodes.new("ShaderNodeNormalMap"); n.inputs["Strength"].default_value = nstr
        nt.links.new(t.outputs["Color"], n.inputs["Color"]); nt.links.new(n.outputs["Normal"], P.inputs["Normal"])
    if mr:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(mr, False); s = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], s.inputs["Color"]); nt.links.new(s.outputs["Green"], P.inputs["Roughness"])
        if metal: nt.links.new(s.outputs["Blue"], P.inputs["Metallic"])
    if alpha is not None:
        P.inputs["Alpha"].default_value = alpha; m.blend_method = 'BLEND'
    m["uv"] = uv; MATS[name] = m; return m


# the bottle: matte sage powder coat (orange peel, smudges), bare brushed steel at the foot, a black polypropylene cap
mat("bottle_coat", srgb("#8a9684"), rough=0.62, nor="white_nor.jpg", nstr=0.35, mr="plastic_mr.jpg", uv=0.05)
mat("bottle_steel", srgb("#c6c8ca"), rough=0.3, metal=1.0, nor="metal_nor.jpg", nstr=0.5, mr="metal_mr.jpg", uv=0.06)
mat("cap_black", srgb("#1b1b1d"), rough=0.55, nor="plastic_nor.jpg", nstr=0.2, mr="plastic_mr.jpg", uv=0.08)
# the glass: transmissive (KHR_materials_transmission, IOR 1.5; post_clutter.mjs adds its volume: a faint green in the
# thick base and the rim). The water stays alpha blended: three.js draws a transmissive surface from the opaque scene
# only, so a transmissive water inside a transmissive glass would vanish; the page draws the glass without depth writes
# so the water shows through it
m_ = mat("glass", srgb("#ffffff"), rough=0.03); P_ = m_.node_tree.nodes["Principled BSDF"]
P_.inputs["Transmission Weight"].default_value = 1.0; P_.inputs["IOR"].default_value = 1.5
mat("water", srgb("#cfe3ea"), rough=0.02, alpha=0.42)
# earbuds, the charger and its cable: white plastic and a slightly greyer cable sheath
mat("white_plastic", srgb("#eceae6"), rough=0.34, nor="plastic_nor.jpg", nstr=0.15, mr="plastic_mr.jpg", uv=0.05)
mat("cable_white", srgb("#dcdad5"), rough=0.5)
mat("connector", srgb("#b9bbbe"), rough=0.3, metal=1.0)
# soft contact shadows under the props (an alpha disc: the page's shadow maps are coarse at this scale)
def contact_image():
    n = 64; im = bpy.data.images.new("contact", n, n, alpha=True); px = []
    for j in range(n):
        for i in range(n):
            r = math.hypot(i + 0.5 - n / 2, j + 0.5 - n / 2) / (n / 2)
            a = max(0.0, 1 - r) ** 1.6 * 0.55
            px += [0.02, 0.018, 0.015, a]
    im.pixels = px; im.filepath_raw = f"{OUT}/contact.png"; im.file_format = 'PNG'; im.save(); return im
mat("contact", (0, 0, 0), rough=1.0, diff_img=contact_image()); MATS["contact"].blend_method = 'BLEND'; MATS["contact"]["nouv"] = 1


# ---------------------------------------------------------------- helpers
def new_obj(name, bm, material):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); me.materials.append(MATS[material]); return o


def project_uv(o):
    """box projection in world space; 1 texture tile = material['uv'] metres (atlas materials keep their own UVs)"""
    me = o.data
    if not me.materials or me.materials[0].get("nouv") or me.materials[0].name not in MATS: return   # (the scans keep their own UVs)
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap"); s = me.materials[0].get("uv", 0.1)
    for p in me.polygons:
        n = p.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            w = o.matrix_world @ me.vertices[me.loops[li].vertex_index].co; gx, gy, gz = w.x, w.z, -w.y
            u, v = (gx, gz) if ax == 2 else (gz, gy) if ax == 0 else (gx, gy)
            uvl.data[li].uv = (u / s, v / s)


def lathe(name, material, prof, n=40, mod=None):
    """profile [(r, h)] revolved about the local vertical axis (glTF y) at the origin; mod(r, angle, h) -> r adds ribs"""
    bm = bmesh.new(); rings = []
    for (r, h) in prof:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n; rr = mod(r, a, h) if (mod and r > 0) else r
            ring.append(bm.verts.new(B(rr * math.cos(a), h, rr * math.sin(a))))
        rings.append(ring)
    for k in range(len(rings) - 1):
        if prof[k][0] == 0 and prof[k + 1][0] == 0: continue
        for i in range(n):
            j = (i + 1) % n; f = bm.faces.new([rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]]); f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(name, bm, material)


def disc(name, r, y=0.0006):
    bm = bmesh.new(); n = 20; c = bm.verts.new(B(0, y, 0)); ring = [bm.verts.new(B(r * math.cos(2 * math.pi * i / n), y, r * math.sin(2 * math.pi * i / n))) for i in range(n)]
    for i in range(n): bm.faces.new([c, ring[(i + 1) % n], ring[i]])
    o = new_obj(name, bm, "contact"); uvl = o.data.uv_layers.new(name="UVMap")
    for p in o.data.polygons:
        for li in p.loop_indices:
            v = o.data.vertices[o.data.loops[li].vertex_index].co; uvl.data[li].uv = (0.5 + v.x / (2 * r), 0.5 + v.y / (2 * r))
    return o


def tube(name, material, pts, r, n=8, res=10):
    """a cable through glTF points: a NURBS curve (it stays inside its points' hull) turned into a mesh"""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = max(1, n // 4 - 1); cu.resolution_u = res
    sp = cu.splines.new('NURBS'); sp.points.add(len(pts) - 1); sp.order_u = 3; sp.use_endpoint_u = True
    for pt, p in zip(sp.points, pts): pt.co = (*B(*p), 1.0)
    co = bpy.data.objects.new(name + "_c", cu); SC.collection.objects.link(co); bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(co.evaluated_get(bpy.context.evaluated_depsgraph_get())); bpy.data.objects.remove(co)
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); me.materials.clear(); me.materials.append(MATS[material])
    for p in me.polygons: p.use_smooth = True
    return o


def xf(objs, loc=(0, 0, 0), ry=0.0, rx=0.0, rz=0.0):
    """rotate about the local glTF axes (z, then x, then y), then move to loc (glTF)"""
    M = Matrix.Translation(B(*loc)) @ Matrix.Rotation(ry, 4, 'Z') @ Matrix.Rotation(rx, 4, 'X') @ Matrix.Rotation(-rz, 4, 'Y')
    for o in objs: o.data.transform(M); o.data.update()


def box_of(objs):
    lo = [1e9] * 3; hi = [-1e9] * 3
    for o in objs:
        for v in o.data.vertices:
            w = G(o.matrix_world @ v.co)
            for k in range(3): lo[k] = min(lo[k], w[k]); hi[k] = max(hi[k], w[k])
    return lo, hi


def import_scan(k, keep=None):
    """a Poly Haven glTF: the kept meshes, their transforms applied, joined into one object at its own place"""
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=f"{AS}/{k}/{k}.gltf")
    new = [o for o in bpy.data.objects if o not in before]; meshes = []
    for o in new:
        if o.type == 'MESH' and (keep is None or any(o.name.startswith(kk) for kk in keep)): meshes.append(o)
    names = {o.name for o in meshes}
    out = []
    for o in meshes:
        o.data = o.data.copy(); o.data.transform(o.matrix_world); o.parent = None; o.matrix_world = Matrix.Identity(4); out.append(o)
    for nm in [o.name for o in new]:
        if nm not in names and nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm])
    return out


def place(objs, at, support_y, ry=0.0, centre=True):
    """turn the parts about their own footprint's centre, then put their lowest point on support_y at (x, z)"""
    lo, hi = box_of(objs); c = ((lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2)
    xf(objs, loc=(-c[0], -c[1], -c[2]))
    xf(objs, ry=ry); lo, hi = box_of(objs)
    xf(objs, loc=(at[0] - ((lo[0] + hi[0]) / 2 if centre else 0), support_y - lo[1], at[1] - ((lo[2] + hi[2]) / 2 if centre else 0)))


def decimate(objs, max_tris):
    for o in objs:
        t = sum(len(p.vertices) - 2 for p in o.data.polygons)
        if t > max_tris:
            m = o.modifiers.new("dec", "DECIMATE"); m.ratio = max_tris / t
            bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="dec")


# ---------------------------------------------------------------- the built room, for supports and collisions
# out/room_clean_dec.glb and out/tripo2_dec.glb: web/room/room_clean.glb and props_tripo2.glb without their meshopt
# compression (node decode.mjs, see CREDITS.md). Kept only as a BVH tree (world, glTF axes); the imported objects go.
# Leaves out what the page hides or cuts away when the Tripo props load (room.html T2_OLD, the mug): those are not seen
from mathutils.bvhtree import BVHTree
ROOM_HIDDEN = ("desk_lamp_arm_01", "potted_plant_02", "cardboard_box_01", "alarm_clock_01", "potted_plant_04", "headphones_mesh")
ROOM_CUTS = [((-0.198, 0.155, 1.02), (0.07, 0.70, 1.46)), ((1.53, 0.155, 0.13), (1.87, 0.72, 0.47)), ((-0.68, 0.155, -1.35), (-0.42, 0.48, -1.09)),
             ((-0.89, 0.965, -1.27), (-0.71, 1.02, -1.13)), ((-1.41, 0.968, -1.34), (-0.71, 1.545, -1.14)), ((-1.62, 0.968, -1.40), (-1.42, 1.172, -1.20)),
             ((-0.665, 0.968, -1.40), (-0.507, 1.172, -1.20)), ((-0.545, 0.968, -1.025), (-0.415, 1.07, -0.935))]
def room_bvh():
    before = set(bpy.data.objects)
    for f in ("room_clean_dec.glb", "tripo2_dec.glb"):
        if not os.path.exists(f"{OUT}/{f}"): sys.exit(f"{OUT}/{f} missing: node decode.mjs ../web/room/{f.replace('_dec', '').replace('tripo2', 'props_tripo2')} out/{f}")
        bpy.ops.import_scene.gltf(filepath=f"{OUT}/{f}")
    new = [o for o in bpy.data.objects if o not in before]; dg = bpy.context.evaluated_depsgraph_get(); V, P = [], []
    inside = lambda p: any(all(lo[k] <= p[k] <= hi[k] for k in range(3)) for lo, hi in ROOM_CUTS)
    for o in new:
        if o.type != 'MESH' or o.name.startswith(ROOM_HIDDEN): continue
        me = o.evaluated_get(dg).to_mesh(); M = o.matrix_world; base = len(V)
        V += [G(M @ v.co) for v in me.vertices]
        for p in me.polygons:
            vs = [base + i for i in p.vertices]
            if not all(inside(V[i]) for i in vs): P.append(vs)
        o.evaluated_get(dg).to_mesh_clear()
    for o in new: bpy.data.objects.remove(o)
    for c in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(c):
            if d.users == 0 and d.name not in MATS and d.name != "contact": c.remove(d)
    return BVHTree.FromPolygons([Vector(v) for v in V], P)
ROOM = room_bvh()
def support_at(x, z, y0=2.6):
    """the height of the room's first surface under (x, z), looking down from y0"""
    hit = ROOM.ray_cast(Vector((x, y0, z)), Vector((0, -1, 0)))
    return hit[0].y if hit[0] is not None else None


def room_hits(objs, support):
    """triangle pairs between the parts (those above support + 3 mm, if it rests on one) and the built room: [] if clear"""
    V, P = [], []
    for o in objs:
        if "contact" in o.name: continue
        ws = [G(o.matrix_world @ v.co) for v in o.data.vertices]; base = len(V); V += [Vector(w) for w in ws]
        P += [[base + i for i in p.vertices] for p in o.data.polygons if support is None or min(ws[i][1] for i in p.vertices) > support + 0.003]
    if not P: return [], V, P
    return ROOM.overlap(BVHTree.FromPolygons(V, P)), V, P


def fit(objs, spots, support):
    """place the parts at the first (x, z, ry) of spots where they are clear of the room; the last one if none is"""
    for (x, z, ry) in spots:
        place(objs, (x, z), support, ry=ry)
        if not room_hits(objs, support)[0]: print("FIT", objs[0].name, (x, z, ry)); return (x, z)
    print("FIT none for", objs[0].name); return spots[-1][:2]


PROPS = {}                                                    # name -> (objects, support, kind) for the sweep and the GLB nodes
def prop(name, objs, support, check=True):
    for o in objs: project_uv(o)
    PROPS[name] = (objs, support, check)


# ================================================================ the water bottle (the page's PROP.bottle): 500 ml, 65 x 222 mm
# Its own node at the origin, base centre at (0, 0, 0), axis +y; the page parents it to PROP.bottle at y -0.08 (that
# group's origin is the old bottle's middle, 8 cm over the desk at BOTTLE_AT)
R_ = 0.0325
foot = lathe("bottle_foot", "bottle_steel", [(0.0, 0.0008), (0.024, 0.0008), (0.0275, 0.0), (0.0305, 0.0018), (0.0322, 0.0055), (0.0325, 0.011)], n=48)
body = lathe("bottle_body", "bottle_coat", [(0.0325, 0.011), (0.0326, 0.06), (0.0325, 0.150), (0.0318, 0.160), (0.0296, 0.168),
                                           (0.0262, 0.174), (0.0232, 0.178), (0.0222, 0.181), (0.0222, 0.184)], n=48)
neck = lathe("bottle_neck", "bottle_steel", [(0.0222, 0.184), (0.0214, 0.1845), (0.0214, 0.188)], n=48)
knurl = lambda r, a, h: r + (0.0006 if (h > 0.192 and h < 0.214) and (int(a / (2 * math.pi) * 60) % 2 == 0) else 0.0)
cap = lathe("bottle_cap", "cap_black", [(0.0216, 0.1875), (0.0238, 0.1878), (0.0244, 0.190), (0.0246, 0.193), (0.0246, 0.212), (0.0242, 0.215),
                                        (0.0228, 0.2165), (0.0, 0.2168)], n=60, mod=knurl)
# the carry loop: a flattened ring standing on the cap, its feet in two lugs
ring = [(0.0145 * math.cos(math.pi * i / 27), 0.2165 + 0.0115 * math.sin(math.pi * i / 27)) for i in range(28)]
loop = tube("bottle_loop", "cap_black", [(x, y, 0.0) for x, y in ring], 0.0032, n=8)
lugs = [lathe(f"bottle_lug{s}", "cap_black", [(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.006), (0.0, 0.0065)], n=12) for s in (-1, 1)]
for s, l in zip((-1, 1), lugs): xf([l], loc=(s * 0.0145, 0.2148, 0.0))
# small dents and a slight lean in the coat where it has been knocked about (a real bottle is never a perfect cylinder)
for v in body.data.vertices:
    g = G(v.co); a = math.atan2(g[2], g[0]); h = g[1]
    d = 0.00035 * math.exp(-((a - 2.1) ** 2) / 0.04 - ((h - 0.05) ** 2) / 0.0004) + 0.00025 * math.exp(-((a + 0.7) ** 2) / 0.03 - ((h - 0.12) ** 2) / 0.0003)
    k = 1 - d / max(1e-6, math.hypot(g[0], g[2])); v.co.x *= k; v.co.y *= k
bottle = [foot, body, neck, cap, loop] + lugs + [disc("bottle_contact", 0.046)]
for o in bottle: project_uv(o)
BOTTLE = bottle

# ================================================================ the desk: a notebook with a pen and a pencil, wired earbuds, the charger cable
# The notebook (an A5 binder, 171 x 200 mm) in the desk's back left corner behind the books, a pen and a pencil on its
# cover; the earbuds in the strip behind the keyboard's left end, in front of the left speaker. The dish's and the
# bottle's spots, the keyboard, the mouse and the monitor's foot stay clear
nb = import_scan("binder_notebook", keep=("binder_notebook_closed",)); decimate(nb, 6000)
# the scan's cover carries a round stamped emblem (a logo-like mark): leather from just above it is cloned over it, with
# a feathered edge, in its colour, normal and ARM maps
import numpy as np
def clone_out(prefix, rects, off, feather=10):
    """rects (x0, y0, x1, y1) in 1k maps, from the top; each filled from the same-sized patch off (dx, dy) away"""
    for im in {n.image for m in bpy.data.materials if m.name.startswith(prefix) and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}:
        W_, H_ = im.size; ch = im.channels; a = np.empty(W_ * H_ * ch, np.float32); im.pixels.foreach_get(a); a = a.reshape(H_, W_, ch)[::-1].copy()
        k_ = W_ / 1024
        for (x0, y0, x1, y1) in rects:
            x0, y0, x1, y1 = [int(round(v * k_)) for v in (x0, y0, x1, y1)]; dx, dy = int(off[0] * k_), int(off[1] * k_); f = max(1, int(feather * k_))
            yy, xx = np.mgrid[y0 - f:y1 + f, x0 - f:x1 + f]
            w = np.clip(np.minimum.reduce([xx - (x0 - f), (x1 + f - 1) - xx, yy - (y0 - f), (y1 + f - 1) - yy]) / f, 0, 1)[..., None]
            a[y0 - f:y1 + f, x0 - f:x1 + f] = a[y0 - f:y1 + f, x0 - f:x1 + f] * (1 - w) + a[y0 - f + dy:y1 + f + dy, x0 - f + dx:x1 + f + dx] * w
        im.pixels.foreach_set(a[::-1].ravel()); im.pack(); print("CLONED over", im.name)
clone_out("binder_notebook", [(186, 274, 272, 352)], (0, -100))
place(nb, (-1.742, -1.312), DTOP, ry=0.12)
NB_LO, NB_HI = box_of(nb)
prop("notebook", nb, DTOP)
pen = import_scan("stationery_supplies", keep=("stationery_supplies_pen_blue",))
place(pen, (-1.735, -1.300), NB_HI[1] - 0.0015, ry=0.62)        # lying on the cover (its lowest point just into the cover's curve)
pencil = import_scan("stationery_supplies", keep=("stationery_supplies_pencil_used",))
# (after both imports: a second import of the file reloads its images) the scan prints a maker's name along the barrels: plain barrel cloned over it (the pen's two printings, the pencil's)
for r_, o_ in (((196, 360, 340, 390), (-168, 0)), ((988, 403, 1016, 507), (-42, 0)), ((520, 312, 606, 338), (122, 0))):
    clone_out("stationery_supplies", [r_], o_, feather=4)
place(pencil, (-1.760, -1.345), NB_HI[1] - 0.0010, ry=-0.35)
prop("pen_pencil", pen + pencil, None)

# wired earbuds: two buds (a rounded shell and a stem), a Y split, a jack, the cable lying in loose loops
def bud(nm, at, ry):
    sh = lathe(nm + "_shell", "white_plastic", [(0.0, 0.0), (0.0062, 0.0006), (0.0082, 0.0032), (0.0085, 0.0062), (0.0072, 0.0092), (0.0040, 0.0112), (0.0, 0.0118)], n=20)
    st = lathe(nm + "_stem", "white_plastic", [(0.0, 0.0), (0.0024, 0.0), (0.0026, 0.016), (0.0020, 0.0205), (0.0, 0.021)], n=12)
    xf([st], rx=math.pi / 2); xf([st], loc=(0.0, 0.0028, 0.002))     # the stem lies along +z out of the shell's side
    xf([sh, st], loc=(at[0], DTOP, at[1]), ry=ry); return [sh, st]
E0 = (-1.290, -1.198)                                          # (off the desk mat, whose top is 3 mm over the desk)
buds = bud("bud_l", (E0[0] - 0.022, E0[1] - 0.006), 0.4) + bud("bud_r", (E0[0] + 0.004, E0[1] - 0.020), -0.9)
RC = 0.0015                                                    # the cable: 3 mm across (it reads at the page's distance)
def bezier(p0, d0, p1, d1, n=24):
    """a cubic curve from p0 (leaving along d0) to p1 (arriving along d1), in the desk's plane (x, z)"""
    c0 = (p0[0] + d0[0], p0[1] + d0[1]); c1 = (p1[0] - d1[0], p1[1] - d1[1]); out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * c0[0] + 3 * u * t * t * c1[0] + t ** 3 * p1[0], u ** 3 * p0[1] + 3 * u * u * t * c0[1] + 3 * u * t * t * c1[1] + t ** 3 * p1[1]))
    return out
def lay(start, heading, length, box, seed, ds=0.003):
    """a cable dropped loosely: its curvature eases toward a new random bend every few centimetres, and it turns back
    inside box (x0, x1, z0, z1) as it nears an edge; returns (x, z) points and the last heading"""
    rnd = random.Random(seed); (x, z), th, k, goal = start, heading, 0.0, 0.0; out = [start]
    cx, cz = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
    for i in range(int(length / ds)):
        if i % 12 == 0: goal = rnd.choice((-1, 1)) * rnd.uniform(12, 40)
        edge = min(x - box[0], box[1] - x, z - box[2], box[3] - z)
        if edge < 0.018:                                         # near an edge: bend towards the middle
            to_c = math.atan2(cz - z, cx - x); turn = (to_c - th + math.pi) % (2 * math.pi) - math.pi
            goal = math.copysign(110, turn)
        k += (goal - k) * 0.18; th += k * ds; x += ds * math.cos(th); z += ds * math.sin(th); out.append((x, z))
    return out, th
def lift(path, base_y, r):
    """heights along a path lying on the desk: where it crosses a stretch laid before, it rides over it"""
    ys = [base_y] * len(path)
    for i, (x, z) in enumerate(path):
        for j in range(0, i - 12):
            d = math.hypot(x - path[j][0], z - path[j][1])
            if d < 2.6 * r: ys[i] = max(ys[i], base_y + 2 * r * (1 - d / (2.6 * r)) ** 0.5)
    sm = [sum(ys[max(0, i - 3):i + 4]) / len(ys[max(0, i - 3):i + 4]) for i in range(len(ys))]   # a cable sags into a bump, never a step
    return [max(a, b) if b > base_y else a for a, b in zip(sm, ys)]
SPL = (E0[0] + 0.006, E0[1] + 0.036)                            # the Y split's two ends: the buds' wires in, the lead out (+z)
ear_cable = []
for nm, (bx, bz), ry in (("bud_cable_l", (E0[0] - 0.022, E0[1] - 0.006), 0.4), ("bud_cable_r", (E0[0] + 0.004, E0[1] - 0.020), -0.9)):
    tip = (bx + 0.0225 * math.sin(ry), bz + 0.0225 * math.cos(ry)); d = (math.sin(ry), math.cos(ry))
    path = bezier(tip, (d[0] * 0.03, d[1] * 0.03), (SPL[0], SPL[1]), (0.0, 0.022))
    ear_cable.append(tube(nm, "cable_white", [(x, DTOP + 0.0012, z) for (x, z) in path[::2]], 0.0012, n=8, res=4))
lead, th_end = lay((SPL[0], SPL[1] + 0.0104), math.pi / 2, 0.40, (-1.343, -1.200, -1.188, -1.140), 7)
lead = [(SPL[0], SPL[1] + 0.0104)] + lead
ys = lift(lead, DTOP + RC, RC)
ear_cable.append(tube("bud_cable", "cable_white", [(x, y, z) for (x, z), y in list(zip(lead, ys))[::3] + [(lead[-1], ys[-1])]], RC, n=8, res=4))
split = lathe("bud_split", "white_plastic", [(0.0, 0.0), (0.0024, 0.0), (0.0028, 0.006), (0.0020, 0.010), (0.0, 0.0104)], n=10)
xf([split], rx=math.pi / 2); xf([split], loc=(SPL[0], DTOP + 0.0028, SPL[1]))
jack = lathe("bud_jack", "white_plastic", [(0.0, 0.0), (0.0034, 0.0), (0.0034, 0.016), (0.0018, 0.019), (0.0, 0.019)], n=12)
pin = lathe("bud_jack_pin", "connector", [(0.0, 0.0), (0.0018, 0.0), (0.0018, 0.012), (0.0012, 0.0135), (0.0, 0.0138)], n=10)
jx, jz = lead[-1]
xf([pin], loc=(0, 0.019, 0)); xf([jack, pin], rx=math.pi / 2)        # (along +z, then turned to the cable's last heading)
xf([jack, pin], loc=(jx, DTOP + 0.0034, jz), ry=-(th_end - math.pi / 2))
earbuds = buds + ear_cable + [split, jack, pin]
prop("earbuds", earbuds, DTOP)

# the phone charger: a USB-C brick in the power strip under the desk, its cable along the skirting, up the back wall,
# under the desk's back rail and up through the cable grommet; on the desk it runs along the right edge to a USB-C end
STRIP_TOP = FY + 0.038
brick = lathe("charger", "white_plastic", [(0.0, 0.0), (0.0145, 0.0), (0.0158, 0.002), (0.0160, 0.026), (0.0150, 0.0295), (0.0, 0.030)], n=4,
              mod=None)
xf([brick], ry=math.pi / 4); xf([brick], loc=(-1.062, STRIP_TOP, IZ + 0.037))
cable_pts = [(-1.062, STRIP_TOP + 0.031, IZ + 0.037), (-1.05, STRIP_TOP + 0.036, IZ + 0.030), (-1.02, FY + 0.0035, IZ + 0.024),
             (-0.80, FY + 0.0035, IZ + 0.0235), (-0.52, FY + 0.0035, IZ + 0.0235), (-0.468, FY + 0.012, IZ + 0.0235), (-0.464, 0.40, IZ + 0.0235),
             (-0.462, 0.862, IZ + 0.024), (-0.461, 0.873, IZ + 0.045), (-0.460, 0.874, IZ + 0.068), (-0.460, 0.90, IZ + 0.070),
             (-0.460, DTOP + 0.002, IZ + 0.070), (-0.452, DTOP + 0.0028, IZ + 0.060), (-0.420, DTOP + 0.0024, IZ + 0.056), (-0.392, DTOP + 0.0024, IZ + 0.10),
             (-0.386, DTOP + 0.0024, IZ + 0.24), (-0.388, DTOP + 0.0024, IZ + 0.34), (-0.395, DTOP + 0.0024, IZ + 0.40), (-0.412, DTOP + 0.0024, IZ + 0.425)]
ch_cable = tube("charger_cable", "cable_white", cable_pts, 0.0022, n=8)
end = lathe("charger_end", "white_plastic", [(0.0, 0.0), (0.0040, 0.0), (0.0042, 0.020), (0.0036, 0.023), (0.0, 0.023)], n=12)
usbc = lathe("charger_usbc", "connector", [(0.0, 0.0), (0.0024, 0.0), (0.0024, 0.0065), (0.0, 0.0068)], n=10)
for v in usbc.data.vertices: v.co.y *= 0.42                    # USB-C: a flat oval plug
xf([usbc], loc=(0, 0.023, 0)); xf([end, usbc], rx=-math.pi / 2)
ex, ez = cable_pts[-1][0], cable_pts[-1][2]
xf([end, usbc], loc=(ex - 0.002, DTOP + 0.0043, ez), ry=math.atan2(-(ex - cable_pts[-2][0]), (ez - cable_pts[-2][2])) + math.pi)
prop("charger", [brick], STRIP_TOP)
prop("charger_cable", [ch_cable, end, usbc], None)

# ================================================================ elsewhere in the room
# a glass of water on the window sill (a plain 250 ml tumbler: 68 mm across the rim, 95 mm tall, a thick base), between
# the cat figure and his place at the sill
GL = (-1.868, 0.300)
glass = lathe("glass", "glass", [(0.0, 0.0), (0.0270, 0.0), (0.0292, 0.0012), (0.0300, 0.004), (0.0338, 0.090), (0.0342, 0.0935),   # a thick base,
                                 (0.0338, 0.0952), (0.0329, 0.0958), (0.0320, 0.0950), (0.0316, 0.0930),                          # a rounded rim
                                 (0.0275, 0.0150), (0.0255, 0.0128), (0.0, 0.0120)], n=48)                                       # 2 mm walls
water = lathe("water", "water", [(0.0, 0.0124), (0.0258, 0.0130), (0.0276, 0.0160), (0.0296, 0.0600), (0.0299, 0.0612),        # the meniscus climbs
                                 (0.0290, 0.0608), (0.0, 0.0604)], n=48)                                                          # the wall a little
gc = disc("glass_contact", 0.045)
xf([glass, water, gc], loc=(GL[0], WY0, GL[1]))
prop("glass", [glass, water, gc], WY0)
# an apple on the fridge's top, by the cup noodles
ap = import_scan("food_apple_01"); decimate(ap, 6000); place(ap, (0.555, -1.035), FTOP, ry=1.2)
apc = disc("apple_contact", 0.055); xf([apc], loc=(0.555, FTOP, -1.035))
prop("apple", ap + [apc], FTOP)
# a small succulent in its pot (14 cm) on the bookshelf's middle level, on the stack of books lying flat there (its top, from
# the built room: STACK2_TOP); the top level takes the laptop
STACK2_TOP = 1.0374
pl = import_scan("potted_plant_04")                               # (at 86 %: a 14 cm pot, the gap between the upright books and the side is 15.7 cm)
for o in pl: o.data.transform(Matrix.Scale(0.86, 4)); o.data.update()
PLX, PLZ = fit(pl, [(x, z, ry) for ry in (2.2, 3.0, 3.8, 4.6, 5.4, 0.6, 1.4) for (x, z) in ((0.226, -1.282), (0.224, -1.292), (0.228, -1.272), (0.221, -1.285))], STACK2_TOP)
plc = disc("plant_contact", 0.082); xf([plc], loc=(PLX, STACK2_TOP, PLZ))
prop("succulent_shelf", pl + [plc], STACK2_TOP)

# two balls of crumpled paper that missed the bin, on the floor by the desk's end (clear of its foot rail, the manga
# stack and the place where he crouches at the bin)
mat("paper", srgb("#e4e0d6"), rough=0.85, nor="white_nor.jpg", nstr=0.5, uv=0.04)
def crumple(nm, r, seed, cells=46, sub=5):
    """a sheet crushed into a ball: the inside of 46 randomly tilted planes (flat facets meeting at crisp ridges), cut by
    eleven V-shaped valleys where it was folded; coplanar triangles dissolved, so the facets stay flat and cheap"""
    rnd = random.Random(seed); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0); C = []
    for _ in range(cells):
        c = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        C.append(((c + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.30).normalized(), rnd.uniform(0.86, 1.0)))
    folds = [(Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized(), rnd.uniform(-0.5, 0.5), rnd.uniform(0.06, 0.14), rnd.uniform(0.06, 0.15)) for _ in range(11)]
    for v in bm.verts:
        d = v.co.normalized()
        t = min(h / dn for (n, h) in C for dn in (d.dot(n),) if dn > 0.25)
        t -= sum(a * max(0.0, 1 - abs(d.dot(fc) - off) / w) for (fc, off, a, w) in folds)
        v.co = d * r * max(0.55, t)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(4), verts=bm.verts[:], edges=bm.edges[:]); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for f in bm.faces: f.smooth = False
    return new_obj(nm, bm, "paper")
balls = []
for k, (bx, bz, r) in enumerate(((-0.315, -1.165, 0.029), (-0.236, -1.128, 0.024))):
    o = crumple(f"paper_ball{k}", r, 40 + k); xf([o], loc=(bx, 0, bz), ry=random.Random(9 + k).uniform(0, 6.28))
    lo, hi = box_of([o]); xf([o], loc=(0, FY - lo[1], 0)); balls.append(o)
prop("paper_balls", balls, FY)

# ================================================================ around the room (the coordinator: "sparse per la stanza", not only the desk)
# Each on a surface of the built room (support_at), clear of his routes, the doors' swings and the props the page adds
def slab(name, material, w, d, h, r, bev=0.0, seg=5):
    """a rounded rectangle w (x) by d (z), h tall (y from 0), corner radius r, its top and bottom edges bevelled by bev"""
    bm = bmesh.new(); ring = []
    for cx, cz, a0 in ((w / 2 - r, d / 2 - r, 0.0), (-w / 2 + r, d / 2 - r, math.pi / 2), (-w / 2 + r, -d / 2 + r, math.pi), (w / 2 - r, -d / 2 + r, 1.5 * math.pi)):
        for i in range(seg + 1):
            a = a0 + (math.pi / 2) * i / seg; ring.append(bm.verts.new(B(cx + r * math.cos(a), 0.0, cz + r * math.sin(a))))
    f = bm.faces.new(ring); ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)], vec=Vector((0, 0, h)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bev > 0:
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-7], offset=bev, segments=2, affect='EDGES', profile=0.5, clamp_overlap=True)
    for fc in bm.faces: fc.smooth = abs(fc.normal.z) < 0.99
    return new_obj(name, bm, material)


def cuboid(name, material, x, y, z):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = B(x[0] if v.co.x < 0 else x[1], y[0] if v.co.z < 0 else y[1], z[0] if v.co.y > 0 else z[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); return new_obj(name, bm, material)


def cell_uv(o, u0, v0, u1, v1, front=None):
    """an atlas cell over every face (planar on the face's own axes); front: (u0, v0, u1, v1) for the faces facing +y instead"""
    me = o.data; uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    lo, hi = box_of([o]); sz = [max(1e-6, hi[k] - lo[k]) for k in range(3)]
    for p in me.polygons:
        n = G(p.normal); ax = max(range(3), key=lambda i: abs(n[i])); c = front if (front and ax == 1 and n[1] > 0) else (u0, v0, u1, v1)
        for li in p.loop_indices:
            w = G(o.matrix_world @ me.vertices[me.loops[li].vertex_index].co); a, b = ((0, 2) if ax == 1 else (2, 1) if ax == 0 else (0, 1))
            s, t = (w[a] - lo[a]) / sz[a], (w[b] - lo[b]) / sz[b]
            if ax == 1: t = 1 - t                                       # (the cover's top edge at -z, its far end)
            uvl.data[li].uv = (c[0] + s * (c[2] - c[0]), c[1] + t * (c[3] - c[1]))


def bvh_of(objs):
    V, P = [], []
    for o in objs:
        base = len(V); V += [Vector(G(o.matrix_world @ v.co)) for v in o.data.vertices]; P += [[base + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(V, P)


# the printed matter: an atlas of plain covers (cloth and paper colours, a band, no titles) and a magazine cover (abstract
# shapes, no text, no logo): 256 px, generated here
def print_atlas():
    n = 256; im = bpy.data.images.new("print_atlas", n, n, alpha=False); px = [0.0] * (n * n * 4); rnd = random.Random(5)
    covers = [("#7d2f2a", "#d9c9a3"), ("#2f4858", "#e3dccb"), ("#c9b48a", "#6b3a2e"), ("#55613f", "#efe8d6"), ("#ece7dc", "#c4492f")]
    def put(i, j, c):
        k = (j * n + i) * 4; px[k:k + 4] = [*c, 1.0]
    for row, (base, band) in enumerate(covers):                    # left half: five covers, 128 x 48 px each, from the bottom
        b, bd = srgb(base), srgb(band)
        for j in range(row * 48, row * 48 + 48):
            for i in range(0, 128):
                t = (j - row * 48) / 48; g = 0.94 + 0.06 * rnd.random()        # a linen grain
                c = bd if 0.70 < t < 0.76 else b
                put(i, j, tuple(min(1.0, x * g) for x in c))
    for j in range(240, 256):                                      # a white strip: the magazine's edges
        for i in range(0, 128): put(i, j, (0.86, 0.85, 0.83))
    sky, sun, sea, ink = srgb("#e9b98f"), srgb("#f4efe6"), srgb("#4a8696"), srgb("#1d2b33")
    for j in range(0, 256):                                        # right half: the magazine's cover, a seaside in flat shapes
        for i in range(128, 256):
            u, v = (i - 128) / 128, j / 256
            c = sky if v > 0.42 else sea
            if (u - 0.62) ** 2 + ((v - 0.60) * 1.4) ** 2 < 0.010: c = sun
            if v < 0.42 and abs(math.sin(u * 19 + v * 40)) < 0.06: c = tuple(x * 1.25 for x in sea)
            if 0.08 < u < 0.92 and 0.90 < v < 0.93: c = ink                # a rule where a title would be (no text)
            put(i, j, tuple(min(1.0, x) for x in c))
    im.pixels = px; im.filepath_raw = f"{OUT}/print_atlas.png"; im.file_format = 'PNG'; im.save(); return im
mat("print", (1, 1, 1), rough=0.62, diff_img=print_atlas()); MATS["print"]["nouv"] = 1
# a leaning B5 magazine's gloss is a little higher than the covers', but one material keeps one draw call
mat("glaze", srgb("#2f4b55"), rough=0.22, nor="plastic_nor.jpg", nstr=0.1, mr="plastic_mr.jpg", uv=0.05)
mat("tea", srgb("#3b2312"), rough=0.06)
mat("laptop_alu", srgb("#8f9297"), rough=0.36, metal=1.0, nor="metal_nor.jpg", nstr=0.2, mr="metal_mr.jpg", uv=0.08)
mat("phone_back", srgb("#4c5d6b"), rough=0.32, nor="plastic_nor.jpg", nstr=0.1, mr="plastic_mr.jpg", uv=0.04)
mat("leather", srgb("#5c3b27"), rough=0.55, nor="plastic_nor.jpg", nstr=0.7, mr="plastic_mr.jpg", uv=0.03)
mat("brass", srgb("#b99a5b"), rough=0.32, metal=1.0)

# --- the bedside. The bed's head is against the window wall, so the sill over it and the headboard's cap are his
# night stand: the glass and the alarm clock are on the sill already; a mug of tea joins them, between the cat figure
# and the clock. A phone lies face down on the headboard's cap, past the window, charging: its cable runs off the cap's
# end, down the bed's side to a socket on the window wall by the floor
MUG = (-1.8605, 0.486)                                           # (its back clear of the sash track's rails at x -1.90)
mug = lathe("mug", "glaze", [(0.0, 0.0), (0.0345, 0.0), (0.0372, 0.0018), (0.0386, 0.006), (0.0398, 0.020), (0.0405, 0.088), (0.0400, 0.0935), (0.0378, 0.0945),
                             (0.0365, 0.093), (0.0362, 0.086), (0.0352, 0.012), (0.0300, 0.0085), (0.0, 0.0080)], n=40)
handle = tube("mug_handle", "glaze", [(0.0385, 0.078, 0.0), (0.054, 0.077, 0.0), (0.0625, 0.064, 0.0), (0.0625, 0.040, 0.0), (0.054, 0.027, 0.0), (0.0385, 0.026, 0.0)], 0.0046, n=8)
for o in (mug, handle): o.data.transform(Matrix.Scale(0.95, 4)); o.data.update()
tea = lathe("mug_tea", "tea", [(0.0, 0.059), (0.0338, 0.059), (0.0, 0.0591)], n=40)
mc = disc("mug_contact", 0.046)
xf([mug, handle, tea], ry=-1.25)                                 # (the handle along the sill, towards the clock)
xf([mug, handle, tea, mc], loc=(MUG[0], WY0, MUG[1]))
prop("mug", [mug, handle, tea, mc], WY0)

CAP_Y = 1.1299                                                    # the headboard cap's top (bed_head_cap: x -1.90..-1.83, to z 1.505)
PH = (-1.8636, 1.403)                                             # (a compact phone, 69 x 140 mm: the cap is 70 mm deep)
phone = slab("phone", "connector", 0.0690, 0.140, 0.0078, 0.0095, bev=0.0016)
back = slab("phone_back", "phone_back", 0.0657, 0.1368, 0.0004, 0.0082); xf([back], loc=(0, 0.0078, 0))
cam = slab("phone_cam", "phone_back", 0.0225, 0.046, 0.0013, 0.0095, bev=0.0004); xf([cam], loc=(0.0165, 0.0082, -0.040))
lenses = []
for lz in (-0.051, -0.031):
    l_ = lathe("phone_lens", "cap_black", [(0.0, 0.0), (0.0074, 0.0), (0.0074, 0.0009), (0.0060, 0.0013), (0.0, 0.0013)], n=20); xf([l_], loc=(0.0165, 0.0095, lz)); lenses.append(l_)
port = cuboid("phone_port", "cap_black", (-0.0045, 0.0045), (0.0026, 0.0052), (0.0699, 0.0702))
phone_parts = [phone, back, cam, port] + lenses
xf(phone_parts, ry=0.01); xf(phone_parts, loc=(PH[0], CAP_Y, PH[1]))
pc = disc("phone_contact", 0.075); xf([pc], loc=(PH[0], CAP_Y, PH[1]))
for v in pc.data.vertices: v.co.x = PH[0] + (v.co.x - PH[0]) * 0.45   # (an oval: the cap is 7 cm deep)
prop("phone", phone_parts + [pc], CAP_Y)
def usbc_plug(nm):
    end = lathe(nm, "white_plastic", [(0.0, 0.0), (0.0040, 0.0), (0.0042, 0.020), (0.0036, 0.023), (0.0, 0.023)], n=12)
    pin = lathe(nm + "_pin", "connector", [(0.0, 0.0), (0.0024, 0.0), (0.0024, 0.0065), (0.0, 0.0068)], n=10)
    for v in pin.data.vertices: v.co.y *= 0.42
    xf([pin], loc=(0, 0.023, 0)); return [end, pin]
plug = usbc_plug("phone_plug"); xf(plug, rx=math.pi / 2)            # along +z, the pin first (into the phone's port at its +z end)
xf(plug, ry=math.pi); xf(plug, loc=(PH[0] + 0.0007, CAP_Y + 0.0039, PH[1] + 0.0702 + 0.0230 + 0.0010))
SOCK = (1.555, 0.30)                                              # (z, y): on the window wall between the bed's side (z 1.50) and the room's edge
plate = slab("socket_plate", "white_plastic", 0.120, 0.070, 0.008, 0.006, bev=0.0015)
xf([plate], rz=-math.pi / 2); xf([plate], loc=(IX + 0.0003, SOCK[1], SOCK[0]))
slots = []
for oy in (0.028, -0.028):
    for oz in (-0.0063, 0.0063):
        slots.append(cuboid("socket_slot", "cap_black", (IX + 0.0076, IX + 0.0082), (SOCK[1] + oy - 0.0035, SOCK[1] + oy + 0.0035), (SOCK[0] + oz - 0.0009, SOCK[0] + oz + 0.0009)))
brick2 = slab("charger2", "white_plastic", 0.030, 0.030, 0.026, 0.004, bev=0.0015); xf([brick2], rz=-math.pi / 2); xf([brick2], loc=(IX + 0.008, SOCK[1] + 0.028, SOCK[0]))
prop("socket", [plate, brick2] + slots, None)
BZ1C = 1.505                                                      # the cap's end
cable2_pts = [(IX + 0.034, SOCK[1] + 0.022, SOCK[0]), (IX + 0.046, SOCK[1] - 0.010, SOCK[0] - 0.004), (IX + 0.040, FY + 0.060, SOCK[0] - 0.020),
              (IX + 0.024, FY + 0.090, BZ1C + 0.010), (IX + 0.030, 0.40, BZ1C + 0.0085), (IX + 0.033, 0.80, BZ1C + 0.0085), (IX + 0.035, CAP_Y - 0.012, BZ1C + 0.0085),
              (PH[0] + 0.0007, CAP_Y + 0.0060, BZ1C + 0.0060), (PH[0] + 0.0007, CAP_Y + 0.0039, PH[1] + 0.0702 + 0.0236)]
cable2 = tube("phone_cable", "cable_white", cable2_pts, 0.0019, n=8)
prop("phone_cable", [cable2] + plug, None)

# --- books by the bed: three bunko paperbacks (105 x 148 mm) stacked on the floor at the bed's foot, past the duvet's
# overhang and off his way to the futon spot (x -0.07); a B5 magazine leaning on the bed base beside them
def extrude_profile(nm, material, prof, d, zs=None):
    """a closed cross-section [(x, y)] (glTF) swept along z from -d/2 to d/2 (zs: per-point z insets, for the page block's head and tail)"""
    bm = bmesh.new(); n = len(prof)
    a = [bm.verts.new(B(x, y, -d / 2 + (zs[k] if zs else 0.0))) for k, (x, y) in enumerate(prof)]
    b = [bm.verts.new(B(x, y, d / 2 - (zs[k] if zs else 0.0))) for k, (x, y) in enumerate(prof)]
    for k in range(n):
        f = bm.faces.new([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]]); f.smooth = True
    bm.faces.new(a); bm.faces.new(b[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    o = new_obj(nm, bm, material)
    for f in o.data.polygons: f.use_smooth = abs(G(f.normal)[2]) < 0.9
    return o
def bunko(nm, t, cell, ry, at, y):
    """a bunko paperback (105 x 148 mm): a soft cover round a rounded spine, its front board lifting a little at the fore
    edge, and the cream page block showing at the head, the tail and the fore edge"""
    cv = 0.0007; w, d = 0.105, 0.148; e = t * 0.32; sx = -w / 2 + e
    lift = lambda x: 0.0011 * max(0.0, (x - (w / 2 - 0.03)) / 0.03) ** 2        # the cover's curl at the fore edge
    arc = [(sx - e * math.sin(math.pi * k / 10), t / 2 - (t / 2) * math.cos(math.pi * k / 10)) for k in range(11)]   # the spine, bottom to top
    arc_in = [(sx - (e - cv) * math.sin(math.pi * k / 10), t / 2 - (t / 2 - cv) * math.cos(math.pi * k / 10)) for k in range(11)]
    xs = [sx + (w / 2 - sx) * k / 6 for k in range(1, 7)]
    outer = [(x, 0.0) for x in xs[::-1]] + arc + [(x, t + lift(x)) for x in xs]
    inner = [(x, t - cv + lift(x)) for x in xs[::-1]] + arc_in[::-1] + [(x, cv) for x in xs]
    cover = extrude_profile(nm + "_cover", "print", outer + inner, d)
    fx = w / 2 - 0.0007
    pages_prof = [(sx, cv), (fx, cv), (fx - 0.0006, t / 2), (fx, t - cv), (sx, t - cv), (sx - (e - cv) * 0.9, t / 2)]
    pages = extrude_profile(nm + "_pages", "paper", pages_prof, d, zs=[0.0008] * len(pages_prof))
    u0, v0 = 0.0, cell * 48 / 256; u1, v1 = 0.5, (cell * 48 + 48) / 256
    cell_uv(cover, u0 + 0.01, v0 + 0.01, u1 - 0.01, v1 - 0.01)
    parts = [pages, cover]; xf(parts, ry=ry); xf(parts, loc=(at[0], y, at[1])); return parts
BK = (-0.1265, 0.935); y0_ = support_at(BK[0], BK[1], 0.5)
books = []
for i, (t, cell, ry, dx, dz) in enumerate(((0.0165, 1, 0.025, 0.0, 0.0), (0.0120, 4, -0.020, 0.0012, -0.002), (0.0145, 0, 0.012, -0.0010, 0.003))):
    yb = y0_ + sum((0.0165, 0.0120, 0.0145)[:i]); books += bunko(f"bunko{i}", t, cell, ry + math.pi, (BK[0] + dx, BK[1] + dz), yb)   # spines to the room
bkc = disc("books_contact", 0.10); xf([bkc], loc=(BK[0], y0_, BK[1]))
for v in bkc.data.vertices: v.co.x = BK[0] + (v.co.x - BK[0]) * 0.62
prop("books_floor", books + [bkc], y0_)
MG = (-0.2005, 0.712); mag_h, mag_w, mag_t, lean = 0.257, 0.182, 0.0035, 0.20
mag = cuboid("magazine", "print", (0.0, mag_t), (0.0, mag_h), (-mag_w / 2, mag_w / 2))
cell_uv(mag, 0.01, 241 / 256, 0.49, 254 / 256)
me_ = mag.data; uvl = me_.uv_layers["UVMap"]                       # its cover (the +x face) takes the cover art
for p in me_.polygons:
    if G(p.normal)[0] > 0.5:
        for li in p.loop_indices:
            w = G(me_.vertices[me_.loops[li].vertex_index].co); uvl.data[li].uv = (0.5 + 0.5 * (w[2] + mag_w / 2) / mag_w, (w[1] / mag_h) * (180 / 256) + 38 / 256)
xf([mag], rz=lean)                                                # its top against the bed base (x -0.20), its foot out on the rug
ymg = support_at(MG[0] + mag_h * math.sin(lean), MG[1], 0.5)
lo_, hi_ = box_of([mag]); xf([mag], loc=(MG[0] + 0.0012 - lo_[0], ymg - lo_[1], MG[1]))
prop("magazine", [mag], ymg)

# --- the laptop, closed, on the bookshelf's top level (a 13-inch: 298 x 208 x 16 mm, bead-blasted aluminium, no logo),
# from the level's left side to just short of the magazines leaning at its right
LT = (0.0515, SHELF_TOP_LEVEL, -1.300)                       # (x, y, z)
lb = slab("laptop_base", "laptop_alu", 0.298, 0.208, 0.0084, 0.011, bev=0.0022)
seam = slab("laptop_seam", "cap_black", 0.2955, 0.2055, 0.0010, 0.010); xf([seam], loc=(0, 0.0084, 0))
lid = slab("laptop_lid", "laptop_alu", 0.298, 0.208, 0.0056, 0.011, bev=0.0016); xf([lid], loc=(0, 0.0094, 0))
feet = []
for fx in (-0.12, 0.12):
    for fz in (-0.08, 0.08):
        f_ = lathe("laptop_foot", "cap_black", [(0.0, 0.0), (0.0055, 0.0), (0.0058, 0.0012), (0.0, 0.0015)], n=12); xf([f_], loc=(fx, 0.0, fz)); feet.append(f_)
xf([lb, seam, lid], loc=(0, 0.0015, 0))
laptop = [lb, seam, lid] + feet; xf(laptop, ry=0.012); xf(laptop, loc=LT)
ltc = disc("laptop_contact", 0.17); xf([ltc], loc=LT)
for v in ltc.data.vertices: v.co.y = -LT[2] + (v.co.y + LT[2]) * 0.70     # (B: glTF z is Blender -y)
prop("laptop", laptop + [ltc], SHELF_TOP_LEVEL)

# --- by the door: a wooden bowl for the keys and a wallet, on the stack of shoeboxes (props_tripo2: its top box at
# y 0.485, measured here)
def flat_region(x0, x1, z0, z1, y, step=0.005):
    pts = [(x0 + i * step, z0 + j * step) for i in range(int((x1 - x0) / step) + 1) for j in range(int((z1 - z0) / step) + 1)]
    ok = [(x, z) for (x, z) in pts if (lambda h: h is not None and abs(h - y) < 0.004)(support_at(x, z, 1.0))]
    return (min(p[0] for p in ok), max(p[0] for p in ok), min(p[1] for p in ok), max(p[1] for p in ok)) if ok else None
SB_Y = support_at(1.80, -0.58, 1.0); SB = flat_region(1.60, 2.00, -0.75, -0.40, SB_Y)
print("SHOEBOX TOP", round(SB_Y, 4), [round(v, 3) for v in SB])
bowl = import_scan("wooden_bowl_02"); BW = (SB[0] + 0.088, (SB[2] + SB[3]) / 2)
for o in bowl: o.data.transform(Matrix.Diagonal((1.0, 1.0, 0.55, 1.0))); o.data.update()   # a shallow catch-all (4 cm): the keys show over its rim
place(bowl, BW, SB_Y, ry=0.9); bwc = disc("bowl_contact", 0.085); xf([bwc], loc=(BW[0], SB_Y, BW[1]))
prop("key_bowl", bowl + [bwc], SB_Y)
KD = 0.7; KDIR = (math.cos(KD), -math.sin(KD))                  # the keys' heading (xf's ry turns +x to (cos, -sin))
BB = bvh_of(bowl); DOWN = Vector((0, -1, 0))
def bowl_top(r):
    h = BB.ray_cast(Vector((BW[0] + KDIR[0] * r, SB_Y + 0.2, BW[1] + KDIR[1] * r)), DOWN)[0]; return h.y if h is not None else None
KB = -0.004; inner = bowl_top(KB)                                 # where the bunch lies, flat in the middle
RIM_R, RIM_Y = max(((r / 1000, bowl_top(r / 1000)) for r in range(40, 76) if bowl_top(r / 1000) is not None), key=lambda e: e[1])
print("BOWL INNER", round(inner, 4))
def key(nm, material, L):
    """a flat key, 2 mm thick: a round bow (its hole a dark dot), a shoulder and a blade with cuts; the bow at the origin, the blade along +x"""
    out = [(0.011 * math.cos(math.radians(40 + 280 * i / 14)), 0.0105 * math.sin(math.radians(40 + 280 * i / 14))) for i in range(15)]
    out += [(0.014, -0.0068), (0.016, -0.0045)]
    for k, c in enumerate((0.0, 0.0018, 0.0006, 0.0022, 0.0010, 0.0016)): out.append((0.016 + (L - 0.019) * (k + 0.5) / 6, -0.0045 + c))
    out += [(L - 0.002, -0.0035), (L, -0.0005), (L - 0.001, 0.0030), (0.016, 0.0035), (0.014, 0.0068)]
    bm = bmesh.new(); f = bm.faces.new([bm.verts.new(B(x, 0.0, z)) for (x, z) in out])
    ext = bmesh.ops.extrude_face_region(bm, geom=[f]); bmesh.ops.translate(bm, verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)], vec=Vector((0, 0, 0.002)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); o = new_obj(nm, bm, material)
    hole = lathe(nm + "_hole", "cap_black", [(0.0, 0.0), (0.0028, 0.0), (0.0028, 0.0021), (0.0, 0.0021)], n=10); xf([hole], loc=(-0.0045, -0.00005, 0.0))
    return [o, hole]
k1 = key("key1", "brass", 0.056); k2 = key("key2", "connector", 0.046)
xf(k1, ry=0.2); xf(k2, ry=2.7); xf(k2, loc=(0.002, 0.0021, 0.003))
ringp = [(0.012 * math.cos(2 * math.pi * i / 24) - 0.0045 - 0.012, 0.0012, 0.012 * math.sin(2 * math.pi * i / 24)) for i in range(25)]
kring = tube("key_ring", "connector", ringp, 0.0009, n=6)
fob = slab("key_fob", "leather", 0.022, 0.040, 0.004, 0.006, bev=0.0012); xf([fob], ry=0.6); xf([fob], loc=(-0.026, 0.0, 0.006))
keys = k1 + k2 + [kring, fob]; xf(keys, ry=KD - 0.2); xf(keys, loc=(BW[0] + KDIR[0] * KB, inner + 0.0006, BW[1] + KDIR[1] * KB))
print("KEYS flat at", round(inner, 4), "rim", round(RIM_Y, 4))
prop("keys", keys, None)
WL = (SB[1] - 0.075, (SB[2] + SB[3]) / 2)
wallet = slab("wallet", "leather", 0.112, 0.092, 0.0165, 0.009, bev=0.0035); xf([wallet], ry=-0.25); xf([wallet], loc=(WL[0], SB_Y, WL[1]))
wlc = disc("wallet_contact", 0.075); xf([wlc], loc=(WL[0], SB_Y, WL[1]))
prop("wallet", [wallet, wlc], SB_Y)

# --- rubber boots, a pair standing by the front right corner past the sneakers (Poly Haven, real size: 373 mm tall),
# their toes to the room
boots = []
for k_, dz in (("rubber_boots_l", 0.058), ("rubber_boots_r", -0.058)):
    bt_ = import_scan("rubber_boots", keep=(k_,)); decimate(bt_, 4800)
    lo, hi = box_of(bt_); xs = [G(bt_[0].matrix_world @ v.co) for v in bt_[0].data.vertices]
    shaft = sum(p[2] for p in xs if p[1] > 0.25) / max(1, sum(1 for p in xs if p[1] > 0.25)) - (lo[2] + hi[2]) / 2
    toe_ry = (-math.pi / 2 if shaft < 0 else math.pi / 2)              # the toe (away from the shaft) to -x
    place(bt_, (1.846, 0.800 + dz), FY, ry=toe_ry + (0.06 if dz > 0 else -0.05)); boots += bt_
# the scan's maker's label (a word on each shaft, printed and embossed): its patches in the colour, normal and ARM maps
# get the plain rubber around them (no readable labels in the room)
LABELS = ((446, 48, 504, 74), (646, 398, 704, 424))              # (x0, y0, x1, y1) in the 1k maps, from the top
for im in {n.image for m in bpy.data.materials if m.name.startswith("rubber_boots") and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}:
    W_, H_ = im.size; px = list(im.pixels); ch = im.channels
    for (x0, y0, x1, y1) in LABELS:
        x0, x1, y0, y1 = x0 * W_ // 1024, x1 * W_ // 1024, y0 * H_ // 1024, y1 * H_ // 1024
        ring = [(x, y) for x in range(x0 - 3, x1 + 3) for y in (y0 - 3, y1 + 2)] + [(x, y) for y in range(y0 - 3, y1 + 3) for x in (x0 - 3, x1 + 2)]
        fill = [sorted(px[((H_ - 1 - y) * W_ + x) * ch + c] for (x, y) in ring)[len(ring) // 2] for c in range(ch)]
        for y in range(y0, y1):
            for x in range(x0, x1):
                k = ((H_ - 1 - y) * W_ + x) * ch; px[k:k + ch] = fill
    im.pixels = px; im.pack()
    print("LABEL cleared in", im.name)
btc = [disc("boot_contact", 0.10) for _ in range(2)]
for c, dz in zip(btc, (0.058, -0.058)):
    xf([c], loc=(1.846, FY, 0.800 + dz))
    for v in c.data.vertices: v.co.x = 1.846 + (v.co.x - 1.846) * 1.4; v.co.y = -(0.800 + dz) + (v.co.y + 0.800 + dz) * 0.5
prop("boots", boots + btc, FY)

# --- a laundry hamper in front of the bookshelf: the bamboo basket, its lid off and leaning on it as scanned, at a
# hamper's size (x 1.7: 36 cm across, 34 cm tall; the scan is a 21 cm storage basket)
hamper = import_scan("wicker_basket_02"); decimate([o for o in hamper if "base" in o.name], 6500); decimate([o for o in hamper if "lid" in o.name], 2600)
for o in hamper: o.data.transform(Matrix.Scale(1.3, 4)); o.data.update()   # (a 27 cm hamper: at 1.7 its strips read coarse)
# its own scanned weave, given depth: its ambient occlusion and a cavity term (where the normal map tilts, at the strips'
# edges) multiplied into the colour map, and its normal map at double strength (the coordinator: the drawn twill read flat)
import numpy as np
def maps_of(prefix):
    return {n.image.name: n for m in bpy.data.materials if m.name.startswith(prefix) and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}
def px_of(im):
    a = np.empty(im.size[0] * im.size[1] * im.channels, np.float32); im.pixels.foreach_get(a); return a.reshape(im.size[1], im.size[0], im.channels)
mx = maps_of("wicker_basket_02"); dif = next(n.image for k, n in mx.items() if "diff" in k); nor = next(n.image for k, n in mx.items() if "nor" in k)
arm = bpy.data.images.load(f"{AS}/wicker_basket_02/textures/wicker_basket_02_arm_1k.jpg", check_existing=False); arm.colorspace_settings.name = "Non-Color"
D_, N_ = px_of(dif), px_of(nor)
cav = np.clip(N_[..., 2] * 2 - 1, 0, 1) ** 2.2                        # 1 where the surface faces out, darker at the strips' edges
shade = 0.35 + 0.65 * cav
if arm is not None:
    A_ = px_of(arm)
    if A_.shape[:2] == shade.shape: shade = shade * (0.25 + 0.75 * np.clip(A_[..., 0], 0, 1) ** 1.6)
    bpy.data.images.remove(arm)
D_[..., :3] *= shade[..., None]; dif.pixels.foreach_set(D_.ravel()); dif.pack()
for m in bpy.data.materials:
    if m.name.startswith("wicker_basket_02") and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == 'NORMAL_MAP': n.inputs["Strength"].default_value = 2.0
print("HAMPER maps", dif.name, nor.name, "AO", A_.shape, D_.shape)
HM = (0.115, -0.975)
place(hamper, (HM[0], HM[1]), FY, ry=-math.pi / 2, centre=False)
lo, hi = box_of(hamper); base_o = [o for o in hamper if "base" in o.name]; blo, bhi = box_of(base_o)
xf(hamper, loc=(HM[0] - (blo[0] + bhi[0]) / 2, 0, (-1.165 + 0.004) - blo[2]))       # the basket's back 4 mm off the shelf's plinth
blo, bhi = box_of(base_o); hmc = disc("hamper_contact", 0.17); xf([hmc], loc=((blo[0] + bhi[0]) / 2, FY, (blo[2] + bhi[2]) / 2))
prop("hamper", hamper + [hmc], FY)


# ================================================================ the sweep: supports, walls, room.html's places, his walking graph
KEEP = {"his place at the window": ((-1.93, -1.30), (1.0, 1.95), (-0.24, 0.20)),
        "the delivery bag's spot": ((-0.70, -0.42), (DTOP + 0.004, DTOP + 0.40), (-0.93, -0.80)),
        "the tea bottle's old spot": ((-1.43, -1.33), (DTOP + 0.004, DTOP + 0.30), (-0.95, -0.85)),
        "the dish's spot": ((-1.48, -1.26), (DTOP + 0.004, DTOP + 0.25), (-1.02, -0.84)),
        "the tea bottle's spot": ((-0.87, -0.79), (DTOP + 0.004, DTOP + 0.30), (-0.89, -0.81)),
        "his crouch at the bin": ((-0.85, -0.25), (FY + 0.02, DTOP - 0.04), (-1.08, -0.55)),
        # the props page code put on the desk since (#98 G10d): the keyboard, the mouse and its pad, the monitor's foot
        "the keyboard": ((-1.26, -0.80), (DTOP, DTOP + 0.05), (-1.062, -0.875)),
        "the mouse pad": ((-0.81, -0.59), (DTOP, DTOP + 0.05), (-1.08, -0.88)),
        "the monitor's foot": ((-1.18, -0.94), (DTOP, DTOP + 0.05), (-1.30, -1.15)),
        # room.html's props_tripo.glb (not in the BVH): the sneakers at SNEAKERS_AT (1.70, 1.32), 28 cm long
        "the sneakers": ((1.50, 1.90), (FY, FY + 0.25), (1.10, 1.54)),
        # the doors: the fridge's opens to 90 degrees on its right hinge (0.48 m), the room door's leaf (DOOR_SWING)
        "the fridge door's swing": ((0.45, 0.95), (FY, FTOP), (-0.97, -0.47)),
        "the door's swing": ((1.05, 1.86), (FY, 2.12), (-1.45, -0.72))}
WALK_NODES = {"bs": (-0.36, -0.18), "ds": (-0.62, -0.35), "w": (0.15, -0.12), "c": (0.45, -0.35), "m": (0.35, 0.05), "d": (1.22, -0.92),
              "f": (0.15, 0.75), "sl": (-1.10, -0.06), "g": (-0.62, -0.08), "sill": (-1.56, -0.02), "doorway": (1.76, -0.98), "deskside": (-0.30, -0.40), "deskstand": (-0.68, -0.55)}
WALK_LINKS = [("bs", "ds"), ("bs", "w"), ("ds", "w"), ("w", "m"), ("w", "c"), ("m", "c"), ("c", "d"), ("m", "d"), ("w", "f"), ("m", "f"),
              ("bs", "g"), ("g", "sl"), ("w", "g"), ("sl", "sill"), ("d", "doorway"), ("ds", "deskstand"), ("bs", "deskside"), ("ds", "deskside")]
def walk_hit(lo, hi, R_=0.22):
    for a, b in WALK_LINKS:
        (ax, az), (bx, bz) = WALK_NODES[a], WALK_NODES[b]; n = max(1, int(math.hypot(bx - ax, bz - az) / 0.02))
        for i in range(n + 1):
            x, z = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            if math.hypot(x - min(max(x, lo[0]), hi[0]), z - min(max(z, lo[2]), hi[2])) < R_: return f"{a}-{b}"
    return None
rows, bad, boxes, TRIS = [], 0, {}, {}
for name, (objs, support, check) in PROPS.items():
    lo, hi = box_of(objs); why = []; boxes[name] = [[round(v, 4) for v in lo], [round(v, 4) for v in hi]]
    if lo[0] < IX - 0.03 - 1e-4 or lo[2] < IZ - 1e-4: why.append("into a wall")
    if support is not None and abs(lo[1] - support) > 0.002: why.append(f"{(lo[1] - support) * 1000:+.1f} mm off its support")
    if "cable" in name:                                         # a cable: every point of it, not its box (it runs a long way)
        pts = [G(o.matrix_world @ v.co) for o in objs for v in o.data.vertices]
        hit = {kn for p in pts for kn, (kx, ky, kz) in KEEP.items() if kx[0] < p[0] < kx[1] and ky[0] < p[1] < ky[1] and kz[0] < p[2] < kz[1]}
        why += [f"in {kn}" for kn in sorted(hit)]
        if any(p[1] > FY + 0.02 and p[1] < 1.9 and walk_hit(p, p) for p in pts[::25]): why.append("on his way")
    else:
        for kn, (kx, ky, kz) in KEEP.items():
            if lo[0] < kx[1] and hi[0] > kx[0] and lo[1] < ky[1] and hi[1] > ky[0] and lo[2] < kz[1] and hi[2] > kz[0]: why.append(f"in {kn}")
        if hi[1] > FY + 0.02 and lo[1] < 1.9 and walk_hit(lo, hi): why.append(f"on his way {walk_hit(lo, hi)}")
    if "cable" not in name:                                     # into the built room (its triangles, not boxes): the parts above the support
        hits, V, P = room_hits(objs, support)
        if hits: c = V[P[hits[0][1]][0]]; why.append(f"into the room ({len(hits)} triangle pairs, at {c.x:+.3f} {c.y:.3f} {c.z:+.3f})")
    if support is not None:                                      # resting on its support everywhere it touches down (no edge hangs over air)
        foot = [Vector(G(o.matrix_world @ v.co)) for o in objs if "contact" not in o.name for v in o.data.vertices]
        foot = [p for p in foot if p.y < support + 0.002][::7][:40]
        miss = [p for p in foot if (lambda h: h is None or abs(h - support) > 0.004)(support_at(p.x, p.z, support + 0.03))]
        if foot and len(miss) > 0.25 * len(foot): why.append(f"{len(miss)}/{len(foot)} of its foot off its support (at {miss[0].x:+.3f} {miss[0].z:+.3f})")
    tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons); TRIS[name] = tris
    rows.append(f"{'ok ' if not why else 'BAD'} {name:<16} x {lo[0]:+.3f}..{hi[0]:+.3f}  y {lo[1]:.3f}..{hi[1]:.3f}  z {lo[2]:+.3f}..{hi[2]:+.3f}  {tris:>6} tris  {'; '.join(why)}")
    bad += bool(why)
bt = sum(len(p.vertices) - 2 for o in BOTTLE for p in o.data.polygons); TRIS["bottle"] = bt
rows.append(f"ok  bottle           (the page places it at BOTTLE_AT)  65 x 222 mm  {bt:>6} tris")
rep = "\n".join(rows) + f"\nCLUTTER SWEEP {len(PROPS)} props, {bad} offenders"; print(rep); open(f"{OUT}/clutter_sweep.txt", "w").write(rep + "\n")
if bad: sys.exit(1)

# ================================================================ export: one node per prop (its parts joined), the bottle at the origin
def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join(); objs[0].name = name; objs[0].data.name = name; return objs[0]
nodes = {}
for name, (objs, _, _) in PROPS.items():
    nodes[name] = join(objs, name) if len(objs) > 1 else objs[0]; nodes[name].name = name
nodes["bottle"] = join(BOTTLE, "bottle")
for o in bpy.data.objects:
    if o.type != 'MESH': bpy.data.objects.remove(o)
for k in list(SC.keys()):                                     # (the room's import left its scenes' extras here: not ours)
    if k != "cycles": del SC[k]
SC["boxes"] = json.dumps(boxes); SC["tris"] = json.dumps(TRIS)    # each prop's box and triangles (post_clutter.mjs joins them by material)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=f"{OUT}/props_clutter_raw.glb", export_format='GLB', use_selection=False, export_extras=True, export_yup=True,
                          export_apply=True, export_texcoords=True, export_normals=True, export_tangents=False, export_materials='EXPORT',
                          export_image_format='AUTO', export_cameras=False, export_lights=False)
print("DONE", {k: sum(len(p.vertices) - 2 for p in o.data.polygons) for k, o in nodes.items()})
