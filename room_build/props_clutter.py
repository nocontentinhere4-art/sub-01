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
# the glass and the water in it (alpha blended: three.js transmission costs a whole extra pass)
mat("glass", srgb("#f2f6f6"), rough=0.04, alpha=0.14)
mat("water", srgb("#d6e6ea"), rough=0.02, alpha=0.30)
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
    if not me.materials or me.materials[0].get("nouv"): return
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


def tube(name, material, pts, r, n=8):
    """a cable through glTF points: a NURBS curve (it stays inside its points' hull) turned into a mesh"""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = max(1, n // 4 - 1); cu.resolution_u = 10
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
place(nb, (-1.742, -1.312), DTOP, ry=0.12)
NB_LO, NB_HI = box_of(nb)
prop("notebook", nb, DTOP)
pen = import_scan("stationery_supplies", keep=("stationery_supplies_pen_blue",))
place(pen, (-1.735, -1.300), NB_HI[1] - 0.0015, ry=0.62)        # lying on the cover (its lowest point just into the cover's curve)
pencil = import_scan("stationery_supplies", keep=("stationery_supplies_pencil_used",))
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
y_ = DTOP + 0.0013
pts = [(E0[0] - 0.022 + 0.008, y_, E0[1] + 0.012), (E0[0] - 0.01, y_, E0[1] + 0.030), (E0[0] + 0.006, y_, E0[1] + 0.034)]
pts2 = [(E0[0] + 0.004 + 0.013, y_, E0[1] - 0.004), (E0[0] + 0.020, y_, E0[1] + 0.016), (E0[0] + 0.008, y_, E0[1] + 0.032), (E0[0] + 0.006, y_, E0[1] + 0.034)]
ear_cable = [tube("bud_cable_l", "cable_white", pts, 0.0012, n=6), tube("bud_cable_r", "cable_white", pts2, 0.0012, n=6)]
coil = []                                                       # the main lead: loose loops ending in the jack
for k in range(46):
    t = k / 45; a = 0.3 + t * 2.6 * 2 * math.pi; rr = 0.020 + 0.010 * math.sin(3.1 * t) + 0.004 * random.random()
    coil.append((E0[0] + 0.020 + rr * math.cos(a) * 1.15, y_, E0[1] + 0.047 + rr * math.sin(a) * 0.8))
coil = [(E0[0] + 0.006, y_, E0[1] + 0.034)] + coil
ear_cable.append(tube("bud_cable", "cable_white", coil, 0.0013, n=6))
split = lathe("bud_split", "white_plastic", [(0.0, 0.0), (0.0024, 0.0), (0.0028, 0.006), (0.0020, 0.010), (0.0, 0.0104)], n=10)
xf([split], rx=math.pi / 2); xf([split], loc=(E0[0] + 0.006, DTOP + 0.0028, E0[1] + 0.036))
jx, jz = coil[-1][0], coil[-1][2]
jack = lathe("bud_jack", "white_plastic", [(0.0, 0.0), (0.0034, 0.0), (0.0034, 0.016), (0.0018, 0.019), (0.0, 0.019)], n=12)
pin = lathe("bud_jack_pin", "connector", [(0.0, 0.0), (0.0018, 0.0), (0.0018, 0.012), (0.0012, 0.0135), (0.0, 0.0138)], n=10)
xf([pin], loc=(0, 0.019, 0)); xf([jack, pin], rx=math.pi / 2); xf([jack, pin], loc=(jx, DTOP + 0.0034, jz), ry=-0.7)
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
glass = lathe("glass", "glass", [(0.0, 0.0), (0.0285, 0.0), (0.0298, 0.002), (0.0340, 0.095), (0.0332, 0.0955), (0.0318, 0.094),
                                 (0.0272, 0.0135), (0.0, 0.0125)], n=40)
water = lathe("water", "water", [(0.0, 0.0128), (0.0273, 0.0132), (0.0300, 0.062), (0.0, 0.062)], n=40)
gc = disc("glass_contact", 0.045)
xf([glass, water, gc], loc=(GL[0], WY0, GL[1]))
prop("glass", [glass, water, gc], WY0)
# an apple on the fridge's top, by the cup noodles
ap = import_scan("food_apple_01"); decimate(ap, 6000); place(ap, (0.555, -1.035), FTOP, ry=1.2)
apc = disc("apple_contact", 0.055); xf([apc], loc=(0.555, FTOP, -1.035))
prop("apple", ap + [apc], FTOP)
# a small succulent in its pot on the bookshelf's top level (the shelf's own scan, at its real size)
pl = import_scan("potted_plant_04"); place(pl, (0.03, -1.305), SHELF_TOP_LEVEL, ry=2.2)
plc = disc("plant_contact", 0.095); xf([plc], loc=(0.03, SHELF_TOP_LEVEL, -1.305))
prop("succulent_shelf", pl + [plc], SHELF_TOP_LEVEL)

# two balls of crumpled paper that missed the bin, on the floor by the desk's end (clear of its foot rail, the manga
# stack and the place where he crouches at the bin)
mat("paper", srgb("#efece4"), rough=0.85, nor="white_nor.jpg", nstr=1.2, uv=0.04)
balls = []
for k, (bx, bz, r) in enumerate(((-0.315, -1.165, 0.029), (-0.236, -1.128, 0.024))):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    rnd = random.Random(40 + k); lobes = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized(), rnd.uniform(0.08, 0.2)) for _ in range(14)]
    for v in bm.verts:
        n = v.co.normalized(); d = 1.0
        for (c, a) in lobes: d -= a * max(0.0, n.dot(c) - 0.75) * 4                 # flat facets where the sheet was folded
        d += 0.05 * math.sin(17 * n.x + 5 * n.y) * math.sin(13 * n.z + 3 * n.x)    # small creases
        v.co = n * r * d
    for f in bm.faces: f.smooth = False
    o = new_obj(f"paper_ball{k}", bm, "paper"); xf([o], loc=(bx, 0, bz), ry=rnd.uniform(0, 6.28))
    lo, hi = box_of([o]); xf([o], loc=(0, FY - lo[1], 0)); balls.append(o)
prop("paper_balls", balls, FY)

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
        "the monitor's foot": ((-1.18, -0.94), (DTOP, DTOP + 0.05), (-1.30, -1.15))}
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
rows, bad, boxes = [], 0, {}
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
    tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
    rows.append(f"{'ok ' if not why else 'BAD'} {name:<16} x {lo[0]:+.3f}..{hi[0]:+.3f}  y {lo[1]:.3f}..{hi[1]:.3f}  z {lo[2]:+.3f}..{hi[2]:+.3f}  {tris:>6} tris  {'; '.join(why)}")
    bad += bool(why)
bt = sum(len(p.vertices) - 2 for o in BOTTLE for p in o.data.polygons)
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
SC["boxes"] = json.dumps(boxes)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=f"{OUT}/props_clutter_raw.glb", export_format='GLB', use_selection=False, export_extras=True, export_yup=True,
                          export_apply=True, export_texcoords=True, export_normals=True, export_tangents=False, export_materials='EXPORT',
                          export_image_format='AUTO', export_cameras=False, export_lights=False)
print("DONE", {k: sum(len(p.vertices) - 2 for p in o.data.polygons) for k, o in nodes.items()})
