# blender -b -P build_room.py -- [--nobake]
# Builds SUB-01's room from clean primitives + a few CC0 Poly Haven props, bakes ambient occlusion into a shared
# lightmap atlas, and exports out/room_raw.glb (+ out/ao.png).  Coordinates in the helpers are glTF/three.js world units:
# x right, y up, z towards the viewer; the room spans x -2..2, z -1.6..1.6, floor top at y = FY (= the page's F).
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, Euler
R = os.path.dirname(os.path.abspath(__file__)); TX = f"{R}/tex_final"; AS = f"{R}/assets"; OUT = f"{R}/out"; os.makedirs(OUT, exist_ok=True)
NOBAKE = "--nobake" in sys.argv
FY = 0.16
random.seed(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene

def B(x, y, z): return Vector((x, -z, y))           # glTF -> Blender

# ---------------------------------------------------------------- materials
MATS = {}
def img(name, colour=True):
    im = bpy.data.images.load(f"{TX}/{name}", check_existing=True)
    if not colour: im.colorspace_settings.name = "Non-Color"
    return im
def mat(name, color=(0.8, 0.8, 0.8), rough=0.6, metal=0.0, diff=None, nor=None, nstr=1.0, mr=None, uv=1.0, vcol=False, emit=None, grain=0):
    """uv: metres covered by one texture tile (used by the UV projection); grain: 0 = along x/z as projected, 1 = swap u/v"""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; P = nt.nodes["Principled BSDF"]
    P.inputs["Base Color"].default_value = (*color, 1); P.inputs["Roughness"].default_value = rough; P.inputs["Metallic"].default_value = metal
    if diff:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(diff); nt.links.new(t.outputs["Color"], P.inputs["Base Color"])
    if vcol:
        a = nt.nodes.new("ShaderNodeVertexColor"); a.layer_name = "Col"; nt.links.new(a.outputs["Color"], P.inputs["Base Color"])
    if nor:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(nor, False); n = nt.nodes.new("ShaderNodeNormalMap"); n.inputs["Strength"].default_value = nstr
        nt.links.new(t.outputs["Color"], n.inputs["Color"]); nt.links.new(n.outputs["Normal"], P.inputs["Normal"])
    if mr:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(mr, False); s = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], s.inputs["Color"]); nt.links.new(s.outputs["Green"], P.inputs["Roughness"]); nt.links.new(s.outputs["Blue"], P.inputs["Metallic"])
    if emit:
        P.inputs["Emission Color"].default_value = (*emit[0], 1); P.inputs["Emission Strength"].default_value = emit[1]
    m["uv"] = uv; m["grain"] = grain; MATS[name] = m; return m

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)

mat("floor", diff="floor_diff.jpg", nor="floor_nor.jpg", mr="floor_mr.jpg", uv=1.7)
mat("wall", diff="wall_diff.jpg", nor="wall_nor.jpg", nstr=0.6, rough=0.9, uv=1.4)
mat("cut", color=srgb("#2b2927"), rough=0.95)
mat("oak", diff="oak_diff.jpg", nor="oak_nor.jpg", nstr=0.6, mr="oak_mr.jpg", uv=1.2)
mat("door", diff="door_diff.jpg", nor="oak_nor.jpg", nstr=0.5, mr="oak_mr.jpg", uv=1.2, grain=1)
mat("white", color=srgb("#ece9e2"), rough=0.42)
mat("plastic_black", color=srgb("#19191b"), rough=0.42)
mat("fabric_black", color=srgb("#151517"), rough=0.92, nor="fabric_nor.jpg", nstr=0.8, uv=0.12)
mat("metal_dark", color=srgb("#2a2a2d"), rough=0.38, metal=1.0)
mat("steel", color=srgb("#c3c5c8"), rough=0.28, metal=1.0)
mat("screen", color=srgb("#060708"), rough=0.12)
mat("sheet", diff="sheet_diff.jpg", nor="sheet_nor.jpg", nstr=0.7, rough=0.9, uv=0.26)
mat("duvet", diff="duvet_diff.jpg", nor="duvet_nor.jpg", nstr=0.9, rough=0.95, uv=0.28)
mat("curtain", diff="curtain_diff.jpg", nor="curtain_nor.jpg", nstr=0.8, rough=0.95, uv=0.27)
mat("rug", diff="rug_diff.jpg", nor="rug_nor.jpg", rough=1.0, uv=0.32)
mat("painted", color=(1, 1, 1), rough=0.65, vcol=True)
mat("posters", diff="posters.png", rough=0.55)

# ---------------------------------------------------------------- mesh helpers
STATIC = []          # objects joined into the one static mesh (baked AO)
def new_obj(name, bm, material, static=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o)
    if isinstance(material, (list, tuple)):
        for m in material: me.materials.append(MATS[m])
    else: me.materials.append(MATS[material])
    if static: STATIC.append(o)
    return o

def project_uv(o, layer="UVMap"):
    """box projection in world space: 1 texture tile = material['uv'] metres"""
    me = o.data; uvl = me.uv_layers.get(layer) or me.uv_layers.new(name=layer)
    M = o.matrix_world; N = M.to_3x3().inverted_safe().transposed()
    for p in me.polygons:
        m = me.materials[p.material_index] if me.materials else None
        s = m.get("uv", 1.0) if m else 1.0; g = m.get("grain", 0) if m else 0
        n = (N @ p.normal); ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            w = M @ me.vertices[me.loops[li].vertex_index].co          # Blender world: x, y(-z gl), z(up)
            gx, gy, gz = w.x, w.z, -w.y
            if ax == 2: u, v = gx, gz              # horizontal face (Blender z = up)
            elif ax == 0: u, v = gz, gy            # facing +-x
            else: u, v = gx, gy                    # facing +-z (glTF)
            if g: u, v = v, u
            uvl.data[li].uv = (u / s, v / s)

def cuboid(bm, x0, x1, y0, y1, z0, z1):
    """a box in glTF coords into bmesh; returns its faces"""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    for v in vs:
        gx = x0 if v.co.x < 0 else x1; gy = y0 if v.co.z < 0 else y1; gz = z0 if v.co.y > 0 else z1
        v.co = B(gx, gy, gz)
    return list({f for v in vs for f in v.link_faces})

def box(name, material, x, y, z, bevel=0.0, seg=2, static=True, mat_by_face=None, smooth=True):
    """x, y, z: (min, max) in glTF coords.  mat_by_face: {'top':i,'bottom':i,'side':i} with material list"""
    bm = bmesh.new(); faces = cuboid(bm, x[0], x[1], y[0], y[1], z[0], z[1])
    if mat_by_face:
        for f in faces:
            f.normal_update(); nz = f.normal.z
            f.material_index = mat_by_face.get("top" if nz > 0.5 else "bottom" if nz < -0.5 else "side", 0)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    o = new_obj(name, bm, material, static)
    if smooth and bevel > 0:
        for p in o.data.polygons: p.use_smooth = True
    project_uv(o); return o

def cyl(name, material, c, r, y0, y1, n=24, r1=None, axis="y", static=True, cap=True, smooth=True):
    """cylinder (or cone with r1) along glTF y (or x/z) from y0 to y1 centred at c=(x,z) (or (y,z)/(x,y))"""
    bm = bmesh.new(); r1 = r if r1 is None else r1
    ring0, ring1 = [], []
    for i in range(n):
        a = 2 * math.pi * i / n; ca, sa = math.cos(a), math.sin(a)
        if axis == "y": p0 = B(c[0] + r * ca, y0, c[1] + r * sa); p1 = B(c[0] + r1 * ca, y1, c[1] + r1 * sa)
        elif axis == "x": p0 = B(y0, c[0] + r * ca, c[1] + r * sa); p1 = B(y1, c[0] + r1 * ca, c[1] + r1 * sa)
        else: p0 = B(c[0] + r * ca, c[1] + r * sa, y0); p1 = B(c[0] + r1 * ca, c[1] + r1 * sa, y1)
        ring0.append(bm.verts.new(p0)); ring1.append(bm.verts.new(p1))
    for i in range(n):
        j = (i + 1) % n; f = bm.faces.new([ring0[i], ring0[j], ring1[j], ring1[i]]); f.smooth = smooth
    if cap: bm.faces.new(ring1); bm.faces.new(list(reversed(ring0)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = new_obj(name, bm, material, static); project_uv(o); return o

def lathe(name, material, prof, c, y0, n=32, static=True, close_top=False):
    """profile [(r, h), ...] revolved around the vertical axis at c=(x,z), from y0"""
    bm = bmesh.new(); rings = []
    for (r, h) in prof:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n; ring.append(bm.verts.new(B(c[0] + r * math.cos(a), y0 + h, c[1] + r * math.sin(a))))
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            if prof[k][0] == 0 and prof[k + 1][0] == 0: continue
            f = bm.faces.new([rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]]); f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = new_obj(name, bm, material, static); project_uv(o); return o

def set_vcol(o, rgb):
    me = o.data; a = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    for d in a.data: d.color = (*rgb, 1)

def transform(o, loc=(0, 0, 0), ry=0.0, pivot=(0, 0, 0)):
    """rotate about glTF y through pivot, then translate by loc (glTF)"""
    M = Matrix.Translation(B(*loc)) @ Matrix.Translation(B(*pivot)) @ Matrix.Rotation(ry, 4, 'Z') @ Matrix.Translation(-B(*pivot))
    o.data.transform(M); o.data.update()

def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join(); objs[0].name = name; return objs[0]

def marker(name, pos, rot=(0, 0, 0), **props):
    e = bpy.data.objects.new(name, None); SC.collection.objects.link(e); e.location = B(*pos)
    e.rotation_mode = 'YXZ'
    # glTF Euler (rx, ry, rz) order YXZ -> Blender: rotation about gl y = Blender z, gl x = Blender x, gl z = Blender -y
    q = (Matrix.Rotation(rot[1], 4, 'Z') @ Matrix.Rotation(rot[0], 4, 'X') @ Matrix.Rotation(-rot[2], 4, 'Y')).to_quaternion()
    e.rotation_mode = 'QUATERNION'; e.rotation_quaternion = q
    for k, v in props.items(): e[k] = v
    return e

# ================================================================ the room shell
X0, X1, Z0, Z1 = -2.0, 2.0, -1.6, 1.6
WALL_T, H = 0.15, 2.39
IX, IZ = -1.9, -1.45                          # inner faces of the left (window) and back walls
box("floor", ["floor", "cut"], (X0, X1), (0, FY), (Z0, Z1), mat_by_face={"top": 0, "side": 1, "bottom": 1})
# walls: interior face = plaster, the cut ends and tops = dark
def wall_box(name, x, y, z):
    o = box(name, ["wall", "cut"], x, y, z)
    for p in o.data.polygons:
        n = p.normal; c = p.center
        interior = (n.x > 0.5 and abs(c.x - IX) < 1e-3) or (n.y < -0.5 and abs(-c.y - IZ) < 1e-3)   # +x face at IX, +z(gl) face at IZ
        p.material_index = 0 if interior else 1
    project_uv(o); return o
WZ0, WZ1, WY0, WY1 = -0.62, 0.90, 1.27, 2.10   # window opening (z range, y range)
wall_box("wall_back", (X0, X1), (0, H), (Z0, IZ))
wall_box("wall_l_below", (X0, IX), (0, WY0), (IZ, Z1))
wall_box("wall_l_above", (X0, IX), (WY1, H), (IZ, Z1))
wall_box("wall_l_a", (X0, IX), (WY0, WY1), (IZ, WZ0))
wall_box("wall_l_b", (X0, IX), (WY0, WY1), (WZ1, Z1))
# the window reveals (inside the opening) are plaster too
for o in [bpy.data.objects[n] for n in ("wall_l_below", "wall_l_above", "wall_l_a", "wall_l_b")]:
    for p in o.data.polygons:
        c = p.center; n = p.normal
        if (abs(c.z - WY0) < 1e-3 and n.z > 0.5 and WZ0 < -c.y < WZ1) or (abs(c.z - WY1) < 1e-3 and n.z < -0.5 and WZ0 < -c.y < WZ1) \
           or (abs(-c.y - WZ0) < 1e-3 and n.y > 0.5) or (abs(-c.y - WZ1) < 1e-3 and n.y < -0.5): p.material_index = 0
    project_uv(o)
# skirting boards
DOOR_X0, DOOR_X1 = 1.05, 1.85                 # door casing span on the back wall
box("skirt_back_a", "white", (IX, DOOR_X0), (FY, FY + 0.065), (IZ, IZ + 0.012), bevel=0.003, seg=1)
box("skirt_back_b", "white", (DOOR_X1, X1), (FY, FY + 0.065), (IZ, IZ + 0.012), bevel=0.003, seg=1)
box("skirt_left", "white", (IX, IX + 0.012), (FY, FY + 0.065), (IZ + 0.012, Z1), bevel=0.003, seg=1)

# ================================================================ window
for nm, x, y, z in [("win_casing_t", (IX, IX + 0.014), (WY1, WY1 + 0.05), (WZ0 - 0.05, WZ1 + 0.05)),
                    ("win_casing_a", (IX, IX + 0.014), (WY0, WY1), (WZ0 - 0.05, WZ0)),
                    ("win_casing_b", (IX, IX + 0.014), (WY0, WY1), (WZ1, WZ1 + 0.05)),
                    ("win_sill", (IX - 0.03, IX + 0.06), (WY0 - 0.025, WY0), (WZ0 - 0.07, WZ1 + 0.07))]:
    box(nm, "oak", x, y, z, bevel=0.003, seg=1)
# aluminium sliding sashes, recessed in the opening; two panes overlapping in the middle
SASH = 0.03
def sash(nm, x, z0, z1):
    box(nm + "_t", "steel", x, (WY1 - SASH, WY1), (z0, z1), bevel=0.002, seg=1)
    box(nm + "_b", "steel", x, (WY0, WY0 + SASH), (z0, z1), bevel=0.002, seg=1)
    box(nm + "_l", "steel", x, (WY0, WY1), (z0, z0 + SASH), bevel=0.002, seg=1)
    box(nm + "_r", "steel", x, (WY0, WY1), (z1 - SASH, z1), bevel=0.002, seg=1)
sash("sash_a", (-1.975, -1.95), WZ0, 0.17)
sash("sash_b", (-1.945, -1.92), 0.11, WZ1)
box("sash_track", "steel", (-1.985, -1.915), (WY0 - 0.004, WY0 + 0.006), (WZ0, WZ1))
box("sash_latch", "steel", (-1.918, -1.905), (1.66, 1.70), (0.13, 0.145), bevel=0.002, seg=1)
# the sky behind the window: a marker; the page puts its sky shader plane here
marker("SURF_window", (-2.012, (WY0 + WY1) / 2, (WZ0 + WZ1) / 2), (0, math.pi / 2, 0), w=WZ1 - WZ0 + 0.06, h=WY1 - WY0 + 0.06, mullion=-1.0)
# curtain rod and two gathered linen curtains (pleats from a sine, wider at the hem)
ROD_Y = WY1 + 0.11
cyl("curtain_rod", "metal_dark", (ROD_Y, IX + 0.07), 0.009, WZ0 - 0.32, WZ1 + 0.36, n=12, axis="z")
for zc in (WZ0 - 0.32, WZ1 + 0.36):
    cyl("rod_end", "metal_dark", (ROD_Y, IX + 0.07), 0.016, zc - 0.012, zc + 0.012, n=12, axis="z")
    box("rod_bracket", "metal_dark", (IX, IX + 0.075), (ROD_Y - 0.006, ROD_Y + 0.006), (zc + (0.04 if zc < 0 else -0.04) - 0.006, zc + (0.04 if zc < 0 else -0.04) + 0.006), bevel=0.002, seg=1)
def curtain(nm, za, zb, side):
    """a gathered panel between za..zb (z), hanging from the rod to the sill; side: which way the folds open"""
    bm = bmesh.new(); nz, ny = 40, 26; top = ROD_Y - 0.01; bot = WY0 - 0.07; folds = 6.5
    grid = []
    for j in range(ny + 1):
        t = j / ny; y = top + (bot - top) * t; row = []
        for i in range(nz + 1):
            s = i / nz; z = za + (zb - za) * s
            amp = 0.022 + 0.018 * t                                  # deeper folds lower down
            x = IX + 0.07 + amp * math.sin(2 * math.pi * folds * s + 0.4 * t * side) + 0.006 * math.sin(7.3 * s + 3 * t)
            z += side * 0.035 * t * t * (s - 0.5)                    # a slight flare at the hem
            row.append(bm.verts.new(B(x, y, z)))
        grid.append(row)
    for j in range(ny):
        for i in range(nz):
            f = bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]); f.smooth = True
    o = new_obj(nm, bm, "curtain")
    md = o.modifiers.new("solid", "SOLIDIFY"); md.thickness = 0.006; md.offset = 0
    project_uv(o); return o
curtain("curtain_a", WZ0 - 0.30, WZ0 + 0.05, -1)
curtain("curtain_b", WZ1 - 0.05, WZ1 + 0.34, 1)

# ================================================================ desk
DX0, DX1, DZ0, DZ1, DTOP = -1.86, -0.36, IZ + 0.01, -0.80, 0.97
box("desk_top", "oak", (DX0, DX1), (DTOP - 0.03, DTOP), (DZ0, DZ1), bevel=0.004, seg=2)
for lx in (DX0 + 0.04, DX1 - 0.04):           # black steel side frames: two legs, a foot and a top rail
    for lz in (DZ0 + 0.05, DZ1 - 0.05):
        box("desk_leg", "metal_dark", (lx - 0.02, lx + 0.02), (FY + 0.02, DTOP - 0.03), (lz - 0.012, lz + 0.012), bevel=0.003, seg=1)
    box("desk_foot", "metal_dark", (lx - 0.02, lx + 0.02), (FY, FY + 0.025), (DZ0 + 0.02, DZ1 - 0.02), bevel=0.003, seg=1)
    box("desk_rail", "metal_dark", (lx - 0.02, lx + 0.02), (DTOP - 0.06, DTOP - 0.03), (DZ0 + 0.03, DZ1 - 0.03), bevel=0.002, seg=1)
box("desk_back_rail", "metal_dark", (DX0 + 0.06, DX1 - 0.06), (DTOP - 0.09, DTOP - 0.03), (DZ0 + 0.04, DZ0 + 0.055), bevel=0.002, seg=1)

# monitor: thin bezel on a stand, slightly turned towards the chair
MON_C = (-1.06, 1.33, -1.19); MON_RY = 0.10; MON_RX = -0.06; SW, SH = 0.64, 0.37
def mon_part(o):
    """parts are built facing +z at the origin (screen centre = 0), then tilted and turned into place"""
    M = Matrix.Translation(B(*MON_C)) @ Matrix.Rotation(MON_RY, 4, 'Z') @ Matrix.Rotation(MON_RX, 4, 'X')
    o.data.transform(M); o.data.update(); project_uv(o); return o
mon_part(box("mon_body", "plastic_black", (-SW / 2 - 0.012, SW / 2 + 0.012), (-SH / 2 - 0.014, SH / 2 + 0.012), (-0.022, 0.0), bevel=0.004, seg=2))
mon_part(box("mon_screen", "screen", (-SW / 2, SW / 2), (-SH / 2, SH / 2), (0.0, 0.0015)))
mon_part(box("mon_back", "plastic_black", (-0.16, 0.16), (-0.12, 0.10), (-0.05, -0.022), bevel=0.012, seg=3))
mon_part(box("mon_chin_logo", "steel", (-0.012, 0.012), (-SH / 2 - 0.0095, -SH / 2 - 0.006), (0.0, 0.0012)))
# stand: neck down to an oval-ish base plate (not tilted)
nb = box("mon_neck", "plastic_black", (MON_C[0] - 0.025, MON_C[0] + 0.025), (DTOP + 0.01, MON_C[1] - 0.02), (MON_C[2] - 0.075, MON_C[2] - 0.055), bevel=0.006, seg=2)
transform(nb, ry=MON_RY, pivot=(MON_C[0], 0, MON_C[2]))
bp = cyl("mon_base", "plastic_black", (MON_C[0], MON_C[2] - 0.035), 0.11, DTOP, DTOP + 0.012, n=32)
bp.data.transform(Matrix.Translation(B(MON_C[0], 0, MON_C[2] - 0.035)) @ Matrix.Diagonal((1.0, 0.62, 1.0, 1.0)) @ Matrix.Translation(-B(MON_C[0], 0, MON_C[2] - 0.035)))
transform(bp, ry=MON_RY, pivot=(MON_C[0], 0, MON_C[2])); project_uv(bp)
# the screen's exact place for the page (centre of the glass, Euler YXZ), slightly in front of the glass
marker("SURF_monitor", tuple(Vector(MON_C) + Vector((math.sin(MON_RY) * 0.002, 0, math.cos(MON_RY) * 0.002))), (MON_RX, MON_RY, 0), w=SW, h=SH)

# keyboard (tenkeyless): body + keycaps (vertex coloured), on a felt desk mat with a mouse
KB_C = (-1.07, -0.97); KB_RY = 0.06
mat_o = box("deskmat", "fabric_black", (-1.47, -0.67), (DTOP, DTOP + 0.003), (-1.12, -0.84), bevel=0.0015, seg=1)
kb = box("kb_body", "plastic_black", (-0.18, 0.18), (DTOP + 0.003, DTOP + 0.022), (-0.065, 0.065), bevel=0.004, seg=2)
transform(kb, loc=(KB_C[0], 0, KB_C[1]), ry=KB_RY); project_uv(kb)
caps = []
P = 0.0188
rows = [[1] * 13, [1] * 13 + [2], [1.5] + [1] * 12 + [1.5], [1.75] + [1] * 11 + [2.25], [2.25] + [1] * 10 + [2.75], [1.25] * 3 + [6.25] + [1.25] * 4]
for ri, row in enumerate(rows):
    x = -0.168; zc = -0.054 if ri == 0 else -0.034 + (ri - 1) * P
    for ki, wu in enumerate(row):
        wdt = wu * P
        if x + wdt > 0.17: break
        k = box("key", "painted", (x + 0.0012, x + wdt - 0.0012), (DTOP + 0.022, DTOP + 0.030), (zc - P / 2 + 0.0012, zc + P / 2 - 0.0012), bevel=0.0018, seg=1)
        accent = (ri == 0 and ki == 0) or (ri == 3 and ki == len(row) - 1)
        set_vcol(k, srgb("#e2621b") if accent else srgb("#2c2d31") if ri else srgb("#3a3b40"))
        transform(k, loc=(KB_C[0], 0, KB_C[1]), ry=KB_RY); caps.append(k); x += wdt
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
for v in bm.verts:
    v.co = Vector((v.co.x * 0.031, v.co.y * 0.058, max(v.co.z, -0.2) * 0.02))
    if v.co.y < 0: v.co.z *= 0.92
bm.transform(Matrix.Translation(B(-0.76, DTOP + 0.004 + 0.004, -0.95)))
mouse = new_obj("mouse", bm, "plastic_black"); [setattr(p, "use_smooth", True) for p in mouse.data.polygons]; project_uv(mouse)
# speakers: small wooden boxes with a black front, a woofer and a tweeter
def speaker(nm, x, z, ry):
    parts = [box(nm + "_box", "oak", (-0.065, 0.065), (0, 0.20), (-0.075, 0.075), bevel=0.006, seg=2),
             box(nm + "_front", "plastic_black", (-0.058, 0.058), (0.007, 0.193), (0.075, 0.079), bevel=0.003, seg=1)]
    w = lathe(nm + "_woofer", "plastic_black", [(0.046, 0), (0.044, 0.004), (0.03, 0.002), (0.012, -0.006), (0.0, -0.004)], (0, 0), 0, n=28)
    w.data.transform(Matrix.Translation(B(0, 0.075, 0.079)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')); parts.append(w)
    t = lathe(nm + "_tweet", "steel", [(0.016, 0), (0.014, 0.003), (0.006, 0.006), (0.0, 0.007)], (0, 0), 0, n=20)
    t.data.transform(Matrix.Translation(B(0, 0.158, 0.079)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')); parts.append(t)
    for o in parts: transform(o, loc=(x, DTOP, z), ry=ry); project_uv(o)
speaker("spk_l", -1.52, -1.30, 0.22)
speaker("spk_r", -0.58, -1.30, -0.18)
# mug and pen cup
lathe("mug", "white", [(0.0, 0.0), (0.036, 0.0), (0.040, 0.004), (0.041, 0.095), (0.037, 0.096), (0.036, 0.012), (0.0, 0.012)], (-0.50, -0.98), DTOP, n=28)
bpy.ops.mesh.primitive_torus_add(major_radius=0.026, minor_radius=0.0065, major_segments=20, minor_segments=8, location=B(-0.50 + 0.045, DTOP + 0.05, -0.98), rotation=(math.pi / 2, 0, 0))
th = bpy.context.active_object; th.data.materials.append(MATS["white"]); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for p in th.data.polygons: p.use_smooth = True
bm = bmesh.new(); bm.from_mesh(th.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < -0.50 + 0.045 - 0.012], context='VERTS'); bm.to_mesh(th.data); bm.free()
STATIC.append(th); project_uv(th)
lathe("pencup", "plastic_black", [(0.0, 0.0), (0.034, 0.0), (0.034, 0.10), (0.031, 0.10), (0.031, 0.006), (0.0, 0.006)], (-0.47, -1.33), DTOP, n=24)
for i, (col, tilt) in enumerate([("#2f6fd6", 0.10), ("#d63b2f", -0.12), ("#f2c12e", 0.05), ("#222222", -0.04), ("#3aa860", 0.14)]):
    pen = cyl("pen", "painted", (0, 0), 0.0045, 0.0, 0.15 if i != 2 else 0.17, n=8)
    set_vcol(pen, srgb(col)); a = 2 * math.pi * i / 5
    pen.data.transform(Matrix.Translation(B(-0.47 + 0.012 * math.cos(a), DTOP + 0.012, -1.33 + 0.012 * math.sin(a))) @ Matrix.Rotation(tilt, 4, 'X') @ Matrix.Rotation(tilt * 0.7, 4, 'Y'))
# a couple of books lying on the desk
for i, (w, d, h, col) in enumerate([(0.21, 0.28, 0.028, "#2d4a6b"), (0.19, 0.25, 0.022, "#c9a86a"), (0.17, 0.23, 0.018, "#8c3b32")]):
    y = DTOP + sum(b[2] for b in [(0, 0, 0.028), (0, 0, 0.022), (0, 0, 0.018)][:i])
    bk = box("desk_book", "painted", (-w / 2, w / 2), (y, y + h), (-d / 2, d / 2), bevel=0.0015, seg=1); set_vcol(bk, srgb(col))
    transform(bk, loc=(-1.70, 0, -1.02), ry=0.25 + 0.12 * i)
# trash bin under the desk
lathe("bin", "plastic_black", [(0, 0), (0.105, 0), (0.12, 0.30), (0.114, 0.30), (0.10, 0.008), (0, 0.008)], (-0.55, -1.22), FY, n=28)

# ================================================================ office chair (black fabric + black plastic)
CH_C = (-1.13, -0.585); CH_RY = 0.54; SEAT_TOP = 0.665
chair = []
def cpart(o): chair.append(o); return o
# five-star base with casters
for i in range(5):
    a = 2 * math.pi * i / 5
    bm = bmesh.new(); faces = cuboid(bm, 0.0, 0.29, -0.022, 0.012, -0.022, 0.022)
    for v in bm.verts:
        g = Vector((v.co.x, v.co.z, -v.co.y)); t = g.x / 0.29
        g.y += 0.05 - 0.03 * t                    # rises towards the hub
        g.z *= (1.0 - 0.35 * t); v.co = B(g.x, g.y, g.z)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.006, segments=2, affect='EDGES', clamp_overlap=True)
    leg = new_obj("ch_leg", bm, "plastic_black"); [setattr(p, "use_smooth", True) for p in leg.data.polygons]
    leg.data.transform(Matrix.Rotation(a, 4, 'Z')); cpart(leg)
    cx, cz = 0.29 * math.cos(a), -0.29 * math.sin(a)
    cpart(box("ch_fork", "plastic_black", (cx - 0.012, cx + 0.012), (0.03, 0.065), (cz - 0.016, cz + 0.016), bevel=0.004, seg=1))
    for s in (-1, 1):
        w = cyl("ch_wheel", "plastic_black", (0.03, cz + s * 0.014), 0.027, cx - 0.008, cx + 0.008, n=16, axis="x")
        cpart(w)
cpart(cyl("ch_hub", "plastic_black", (0, 0), 0.05, 0.03, 0.09, n=24, r1=0.04))
cpart(cyl("ch_gas_sleeve", "plastic_black", (0, 0), 0.032, 0.08, 0.30, n=20, r1=0.03))
cpart(cyl("ch_gas", "metal_dark", (0, 0), 0.022, 0.28, 0.37, n=16))
cpart(box("ch_mech", "plastic_black", (-0.12, 0.12), (0.35, 0.41), (-0.13, 0.12), bevel=0.01, seg=2))
cpart(box("ch_lever", "metal_dark", (0.12, 0.2), (0.375, 0.385), (-0.06, -0.05), bevel=0.003, seg=1))
# seat cushion: a soft rounded slab (subdivided, edges rounded)
seat = box("ch_seat", "fabric_black", (-0.25, 0.25), (0.41, 0.505), (-0.25, 0.23), bevel=0.035, seg=4)
for v in seat.data.vertices:                                   # dished top, rolled front edge
    g = Vector((v.co.x, v.co.z, -v.co.y))
    if g.y > 0.47: g.y -= 0.012 * (1 - (g.x / 0.25) ** 2) * (1 - ((g.z + 0.01) / 0.24) ** 2)
    v.co = B(*g)
cpart(seat)
# backrest: a curved, padded panel on a plastic spine
bm = bmesh.new(); nx, ny = 14, 16; grid = []
for j in range(ny + 1):
    t = j / ny; y = 0.60 + 0.56 * t; row = []
    hw = 0.215 + 0.03 * math.sin(math.pi * min(1, t * 1.2)) - 0.04 * max(0, t - 0.8) / 0.2
    for i in range(nx + 1):
        s = i / nx * 2 - 1; x = s * hw
        z = 0.26 + 0.06 * s * s - 0.025 * math.sin(math.pi * t) * (1 - s * s) + 0.03 * t   # curved around the back, lumbar bulge, reclined
        row.append(bm.verts.new(B(x, y, z)))
    grid.append(row)
for j in range(ny):
    for i in range(nx): bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
back = new_obj("ch_back", bm, "fabric_black")
for p in back.data.polygons: p.use_smooth = True
md = back.modifiers.new("solid", "SOLIDIFY"); md.thickness = 0.045; md.offset = 1.0
md2 = back.modifiers.new("bev", "BEVEL"); md2.width = 0.012; md2.segments = 3; md2.limit_method = 'ANGLE'
cpart(back)
spine = box("ch_spine", "plastic_black", (-0.035, 0.035), (0.38, 0.84), (0.24, 0.27), bevel=0.01, seg=2)
for v in spine.data.vertices:
    g = Vector((v.co.x, v.co.z, -v.co.y)); t = (g.y - 0.38) / 0.46
    g.z += 0.08 * t * t + 0.05 * t + (0.0 if g.y > 0.5 else -0.15 * (0.5 - g.y) / 0.04 * 0)
    v.co = B(*g)
cpart(spine)
cpart(box("ch_spine_foot", "plastic_black", (-0.04, 0.04), (0.37, 0.41), (0.08, 0.27), bevel=0.01, seg=2))
# armrests: posts + pads
for s in (-1, 1):
    cpart(box("ch_arm_post", "plastic_black", (s * 0.255 - 0.018, s * 0.255 + 0.018), (0.38, 0.68), (-0.02, 0.06), bevel=0.008, seg=2))
    cpart(box("ch_arm_bar", "plastic_black", (s * 0.15 - 0.02, s * 0.27), (0.375, 0.41), (0.0, 0.05), bevel=0.008, seg=2))
    cpart(box("ch_arm_pad", "plastic_black", (s * 0.255 - 0.04, s * 0.255 + 0.04), (0.68, 0.71), (-0.13, 0.11), bevel=0.012, seg=3))
# the chair moves (he pulls it out and pushes it back): it is NOT part of the static mesh but one object of its own,
# "chair", whose origin is the pivot on the floor under the gas lift. Its parts are placed in the room for the UV
# projection, then joined and moved back into the object's own space; it gets its own materials and AO (self-occlusion)
CH_M = Matrix.Translation(B(CH_C[0], FY, CH_C[1])) @ Matrix.Rotation(CH_RY, 4, 'Z')
for o in chair:
    o.data.transform(CH_M); o.data.update(); project_uv(o)
    STATIC.remove(o)
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
CHAIR = join(chair, "chair"); CHAIR.data.name = "chair"
CHAIR.data.transform(CH_M.inverted()); CHAIR.matrix_world = CH_M
for i, m in enumerate(CHAIR.data.materials):    # own copies: glTF keeps occlusion per material, and the chair has its own
    c = m.copy(); c.name = "chair_" + m.name; CHAIR.data.materials[i] = c

# ================================================================ bed (storage bed, mattress, sheet, pillow, duvet)
BX0, BX1, BZ0, BZ1 = -1.90, -0.20, 0.25, 1.50
BASE_Y, MAT_Y = 0.55, 0.82
box("bed_base", "oak", (BX0 + 0.04, BX1), (FY + 0.03, BASE_Y), (BZ0, BZ1), bevel=0.006, seg=2)
box("bed_plinth", "plastic_black", (BX0 + 0.08, BX1 - 0.04), (FY, FY + 0.035), (BZ0 + 0.04, BZ1 - 0.04))
for (x0, x1) in ((-1.80, -1.04), (-1.00, -0.25)):            # drawers facing the room (-z)
    box("bed_drawer", "oak", (x0, x1), (FY + 0.06, BASE_Y - 0.05), (BZ0 - 0.012, BZ0), bevel=0.004, seg=2)
    box("bed_drawer_grip", "metal_dark", ((x0 + x1) / 2 - 0.08, (x0 + x1) / 2 + 0.08), (BASE_Y - 0.10, BASE_Y - 0.088), (BZ0 - 0.02, BZ0 - 0.012), bevel=0.002, seg=1)
box("bed_head", "oak", (BX0, BX0 + 0.04), (FY + 0.03, 1.13), (BZ0, BZ1), bevel=0.008, seg=2)
mattress = box("mattress", "sheet", (BX0 + 0.045, BX1 - 0.01), (BASE_Y, MAT_Y), (BZ0 + 0.01, BZ1 - 0.01), bevel=0.05, seg=5)
# pillow: a box puffed up in the middle (thickness ~ (1-u^4)(1-v^4)), resting at the head end
bm = bmesh.new(); nu, nv = 18, 22; PW, PL, PT = 0.42, 0.64, 0.12
top, bot = [], []
for j in range(nv + 1):
    rt, rb = [], []
    for i in range(nu + 1):
        u = i / nu * 2 - 1; v = j / nv * 2 - 1
        h = PT / 2 * ((1 - u ** 4) * (1 - v ** 4)) ** 0.6 + 0.004
        x = u * PW / 2 * (1 - 0.04 * (1 - v * v)); z = v * PL / 2 * (1 - 0.05 * (1 - u * u))
        rt.append(bm.verts.new(Vector((x, -z, h)))); rb.append(bm.verts.new(Vector((x, -z, -h * 0.55))))
    top.append(rt); bot.append(rb)
for j in range(nv):
    for i in range(nu):
        bm.faces.new([top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]])
        bm.faces.new([bot[j][i], bot[j + 1][i], bot[j + 1][i + 1], bot[j][i + 1]])
edge = [(0, i) for i in range(nu)] + [(j, nu) for j in range(nv)] + [(nv, i) for i in range(nu, 0, -1)] + [(j, 0) for j in range(nv, 0, -1)]
for k in range(len(edge)):
    (j0, i0), (j1, i1) = edge[k], edge[(k + 1) % len(edge)]
    try: bm.faces.new([top[j0][i0], bot[j0][i0], bot[j1][i1], top[j1][i1]])
    except ValueError: pass
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.transform(Matrix.Translation(B(-1.58, MAT_Y + 0.045, 0.87)) @ Matrix.Rotation(0.06, 4, 'Z') @ Matrix.Rotation(-0.05, 4, 'Y'))
pillow = new_obj("pillow", bm, "sheet"); [setattr(p, "use_smooth", True) for p in pillow.data.polygons]; project_uv(pillow)

# duvet: cloth simulation draped over the mattress (applied, then thickened)
def duvet():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=56, y_subdivisions=60, size=1.0, location=(0, 0, 0))
    d = bpy.context.active_object; d.name = "duvet"
    L, W = 1.30, 1.62                                          # along x, along z
    d.scale = (L, W, 1); bpy.ops.object.transform_apply(scale=True)
    d.location = B(-0.85, MAT_Y + 0.12, (BZ0 + BZ1) / 2 + 0.01)
    # a soft fold where it is turned back at the head end
    for v in d.data.vertices:
        gx = v.co.x
        if gx < -L / 2 + 0.16: v.co.z += 0.03
    bpy.ops.object.transform_apply(location=True)
    for o in (mattress, pillow, bpy.data.objects["bed_base"], bpy.data.objects["bed_head"], bpy.data.objects["floor"]):
        c = o.modifiers.new("col", "COLLISION"); o.collision.thickness_outer = 0.006; o.collision.cloth_friction = 8
    cl = d.modifiers.new("cloth", "CLOTH"); s = cl.settings
    s.quality = 8; s.mass = 0.35; s.tension_stiffness = 20; s.compression_stiffness = 20; s.shear_stiffness = 8; s.bending_stiffness = 0.6
    s.air_damping = 2.0; cl.collision_settings.distance_min = 0.006; cl.collision_settings.use_self_collision = False
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = 60
    for f in range(1, 46): SC.frame_set(f)
    bpy.context.view_layer.objects.active = d; bpy.ops.object.modifier_apply(modifier="cloth")
    for o in (mattress, pillow, bpy.data.objects["bed_base"], bpy.data.objects["bed_head"], bpy.data.objects["floor"]):
        for m in list(o.modifiers):
            if m.type == 'COLLISION': o.modifiers.remove(m)
    SC.frame_set(1)
    d.data.materials.append(MATS["duvet"])
    md = d.modifiers.new("solid", "SOLIDIFY"); md.thickness = 0.035; md.offset = 1.0; md.use_even_offset = True
    for p in d.data.polygons: p.use_smooth = True
    STATIC.append(d); project_uv(d)
    return d
DUVET = duvet()

# ================================================================ bookshelf with books
SX0, SX1, SZ0, SZ1, STOP = -0.12, 0.32, IZ + 0.005, -1.17, 2.12
T = 0.018
box("shelf_side_l", "oak", (SX0, SX0 + T), (FY, STOP), (SZ0, SZ1), bevel=0.002, seg=1)
box("shelf_side_r", "oak", (SX1 - T, SX1), (FY, STOP), (SZ0, SZ1), bevel=0.002, seg=1)
box("shelf_top", "oak", (SX0, SX1), (STOP - T, STOP), (SZ0, SZ1), bevel=0.002, seg=1)
box("shelf_back", "oak", (SX0 + T, SX1 - T), (FY + 0.05, STOP - T), (SZ0, SZ0 + 0.006))
box("shelf_plinth", "oak", (SX0 + T, SX1 - T), (FY, FY + 0.06), (SZ1 - 0.03, SZ1 - 0.012))
LEVELS = [FY + 0.06, 0.56, 0.94, 1.32, 1.70]
for y in LEVELS: box("shelf_board", "oak", (SX0 + T, SX1 - T), (y, y + T), (SZ0 + 0.006, SZ1), bevel=0.0015, seg=1)
PAL = ["#2d3e57", "#a33b2e", "#d8c9a7", "#3f5b45", "#c58b3a", "#1f1f24", "#6c5a7a", "#e9e4d8", "#8a4b2f", "#46708c", "#b9a27a", "#59302c"]
def books_row(x0, x1, y, depth_max=0.21, lean_end=True, fill=0.9):
    x = x0 + 0.004; n = 0
    while x < x1 - 0.03 and (x - x0) / (x1 - x0) < fill:
        th = random.uniform(0.016, 0.042); hh = random.uniform(0.17, 0.27); dd = random.uniform(0.15, depth_max)
        if y + hh > y + 0.33: hh = 0.3
        b = box("book", "painted", (x, x + th), (y + T, y + T + hh), (SZ1 - 0.012 - dd, SZ1 - 0.012), bevel=0.0012, seg=1)
        set_vcol(b, srgb(random.choice(PAL))); x += th + 0.0015; n += 1
    if lean_end and x < x1 - 0.06:                     # one book leaning on the row
        th, hh, dd = 0.024, 0.22, 0.17
        b = box("book", "painted", (0, th), (0, hh), (-dd, 0), bevel=0.0012, seg=1); set_vcol(b, srgb(random.choice(PAL)))
        b.data.transform(Matrix.Translation(B(x + 0.003, y + T, SZ1 - 0.012)) @ Matrix.Rotation(-0.42, 4, 'Y')); project_uv(b)
def books_stack(xc, y, n):
    yy = y + T
    for i in range(n):
        w, d, h = random.uniform(0.17, 0.22), random.uniform(0.13, 0.18), random.uniform(0.02, 0.04)
        b = box("book", "painted", (-w / 2, w / 2), (yy, yy + h), (-d / 2, d / 2), bevel=0.0012, seg=1); set_vcol(b, srgb(random.choice(PAL)))
        transform(b, loc=(xc, 0, SZ1 - 0.11), ry=random.uniform(-0.15, 0.15)); yy += h
books_row(SX0 + T, SX1 - T, LEVELS[1], fill=0.95)
books_row(SX0 + T, SX1 - T - 0.13, LEVELS[2], fill=0.9); books_stack(SX1 - T - 0.085, LEVELS[2], 3)
books_row(SX0 + T + 0.12, SX1 - T, LEVELS[3], fill=1.0, lean_end=False); books_stack(SX0 + T + 0.07, LEVELS[3], 2)
books_row(SX0 + T, SX1 - T, LEVELS[0], depth_max=0.24, fill=0.6)
# a storage box on the bottom right
b = box("shelf_box", "painted", (SX1 - T - 0.16, SX1 - T - 0.005), (LEVELS[0] + T, LEVELS[0] + T + 0.2), (SZ1 - 0.25, SZ1 - 0.01), bevel=0.003, seg=1); set_vcol(b, srgb("#cfc4ae"))

# ================================================================ small fridge (two doors) with things on top
FX0, FX1, FZ0, FZ1, FTOP = 0.45, 0.93, IZ + 0.02, -0.97, 1.27
box("fridge_body", "white", (FX0, FX1), (FY + 0.012, FTOP), (FZ0, FZ1 - 0.03), bevel=0.012, seg=3)
box("fridge_door_lo", "white", (FX0 + 0.004, FX1 - 0.004), (FY + 0.02, 0.905), (FZ1 - 0.031, FZ1), bevel=0.01, seg=3)
box("fridge_door_hi", "white", (FX0 + 0.004, FX1 - 0.004), (0.915, FTOP - 0.008), (FZ1 - 0.031, FZ1), bevel=0.01, seg=3)
box("fridge_grip_lo", "steel", (FX0 + 0.03, FX0 + 0.045), (0.62, 0.86), (FZ1, FZ1 + 0.022), bevel=0.004, seg=2)
box("fridge_grip_hi", "steel", (FX0 + 0.03, FX0 + 0.045), (0.95, 1.10), (FZ1, FZ1 + 0.022), bevel=0.004, seg=2)
for fx in (FX0 + 0.04, FX1 - 0.04):
    for fz in (FZ0 + 0.05, FZ1 - 0.06): cyl("fridge_foot", "plastic_black", (fx, fz), 0.015, FY, FY + 0.013, n=10)
# cup noodles stacked on top + a tissue box
for i in range(2):
    cn = lathe("cupnoodle", "painted", [(0.0, 0.0), (0.038, 0.0), (0.047, 0.10), (0.049, 0.103), (0.0, 0.103)], (0.58, -1.18), FTOP + i * 0.103, n=24)
    set_vcol(cn, srgb("#f2efe8" if i else "#d9442f"))
tb = box("tissues", "painted", (0.70, 0.88), (FTOP, FTOP + 0.075), (-1.33, -1.22), bevel=0.003, seg=1); set_vcol(tb, srgb("#9fc2c9"))
tt = box("tissue_top", "white", (0.76, 0.82), (FTOP + 0.075, FTOP + 0.095), (-1.29, -1.26), bevel=0.008, seg=2)
# a photo strip stuck on the freezer door (poster atlas, region D)
def poster_quad(nm, x0, x1, y0, y1, zf, uv0, uv1, ry=0.0, pivot=None):
    bm = bmesh.new(); vs = [bm.verts.new(B(x, y, zf)) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    f = bm.faces.new(vs); o = new_obj(nm, bm, "posters"); uvl = o.data.uv_layers.new(name="UVMap")
    (u0, v0), (u1, v1) = uv0, uv1
    for li, (u, v) in zip(o.data.polygons[0].loop_indices, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))): uvl.data[li].uv = (u, v)
    return o
poster_quad("photostrip", 0.60, 0.80, 1.06, 1.16, FZ1 + 0.0015, (683 / 1024, 1 - 512 / 512), (1.0, 1 - 341 / 512))

# ================================================================ door, casing, handle, hooks, switch, mat
LX0, LX1, LY1 = 1.11, 1.79, 2.10
box("door_leaf", "door", (LX0, LX1), (FY + 0.008, LY1), (IZ, IZ + 0.035), bevel=0.004, seg=2)
for (y0, y1) in ((0.30, 1.05), (1.20, 1.96)):                # two raised panels
    box("door_panel", "door", (LX0 + 0.09, LX1 - 0.09), (y0, y1), (IZ + 0.035, IZ + 0.041), bevel=0.005, seg=2)
for nm, x, y in (("door_casing_l", (DOOR_X0, LX0), (FY, LY1 + 0.06)), ("door_casing_r", (LX1, DOOR_X1), (FY, LY1 + 0.06)),
                 ("door_casing_t", (DOOR_X0, DOOR_X1), (LY1, LY1 + 0.06))):
    box(nm, "white", x, y, (IZ, IZ + 0.022), bevel=0.003, seg=1)
cyl("door_rose", "steel", (LX1 - 0.07, 1.02), 0.026, IZ + 0.035, IZ + 0.045, n=24, axis="z")
lever = box("door_lever", "steel", (LX1 - 0.19, LX1 - 0.065), (1.008, 1.03), (IZ + 0.055, IZ + 0.072), bevel=0.006, seg=2)
cyl("door_lever_neck", "steel", (LX1 - 0.07, 1.02), 0.009, IZ + 0.04, IZ + 0.07, n=12, axis="z")
for hy in (0.45, 1.85):
    box("door_hinge", "steel", (LX0 - 0.006, LX0 + 0.006), (hy, hy + 0.09), (IZ + 0.01, IZ + 0.03), bevel=0.002, seg=1)
# hook rail on the door with a tote bag and a cap
box("hook_rail", "oak", (LX0 + 0.16, LX0 + 0.52), (1.70, 1.76), (IZ + 0.041, IZ + 0.056), bevel=0.003, seg=1)
for hx in (LX0 + 0.22, LX0 + 0.34, LX0 + 0.46):
    hk = cyl("hook", "metal_dark", (hx, 1.735), 0.006, IZ + 0.056, IZ + 0.10, n=10, axis="z")
    cyl("hook_tip", "metal_dark", (hx, IZ + 0.10), 0.006, 1.735, 1.765, n=10)
def tote(xc):
    """a canvas tote hanging from a hook: a slightly bulged bag + two straps"""
    bm = bmesh.new(); nx, ny = 10, 14; grid = []
    for j in range(ny + 1):
        t = j / ny; row = []
        for i in range(nx + 1):
            s = i / nx * 2 - 1; x = xc + s * (0.17 + 0.015 * t)
            y = 1.62 - 0.40 * t
            z = IZ + 0.06 + 0.035 * (1 - s * s) * math.sin(math.pi * min(1, t * 1.1)) + 0.02 * t
            row.append(bm.verts.new(B(x, y, z)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx): bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
    o = new_obj("tote", bm, "painted"); md = o.modifiers.new("solid", "SOLIDIFY"); md.thickness = 0.03; md.offset = -1
    [setattr(p, "use_smooth", True) for p in o.data.polygons]; set_vcol(o, srgb("#d9cfb8")); project_uv(o)
    for s in (-1, 1):                                          # straps up to the hook
        st = box("tote_strap", "painted", (-0.012, 0.012), (0, 0.17), (-0.003, 0.003)); set_vcol(st, srgb("#cdbf9f"))
        st.data.transform(Matrix.Translation(B(xc + s * 0.09, 1.60, IZ + 0.065)) @ Matrix.Rotation(-s * 0.48, 4, 'Y')); project_uv(st)
tote(LX0 + 0.34)
# light switch by the door, doormat in front of it
box("switch_plate", "white", (0.93, 1.00), (1.17, 1.29), (IZ, IZ + 0.008), bevel=0.003, seg=2)
box("switch_rocker", "white", (0.945, 0.985), (1.19, 1.27), (IZ + 0.008, IZ + 0.013), bevel=0.002, seg=1)
dm = box("doormat", "painted", (1.08, 1.82), (FY, FY + 0.012), (-1.40, -0.98), bevel=0.004, seg=2); set_vcol(dm, srgb("#45403a"))

# ================================================================ rug, posters, air conditioner
rug = box("rug", "rug", (-0.50, 0.95), (FY, FY + 0.012), (-0.62, 0.85), bevel=0.006, seg=2)
def framed(nm, xc, yc, w, h, uv0, uv1):
    F_ = 0.016
    box(nm + "_frame", "plastic_black", (xc - w / 2 - F_, xc + w / 2 + F_), (yc - h / 2 - F_, yc + h / 2 + F_), (IZ, IZ + 0.018), bevel=0.002, seg=1)
    poster_quad(nm, xc - w / 2, xc + w / 2, yc - h / 2, yc + h / 2, IZ + 0.0185, uv0, uv1)
framed("poster_a", -1.06, 1.97, 0.32, 0.48, (0, 0), (341 / 1024, 1))
framed("poster_b", -0.56, 1.86, 0.26, 0.39, (341 / 1024, 0), (682 / 1024, 1))
framed("poster_c", -1.60, 1.97, 0.24, 0.24, (683 / 1024, 1 - 341 / 512), (1.0, 1.0))
box("ac_body", "white", (0.36, 1.00), (2.02, 2.29), (IZ, IZ + 0.21), bevel=0.03, seg=4)
box("ac_vent", "plastic_black", (0.40, 0.96), (2.035, 2.06), (IZ + 0.17, IZ + 0.205), bevel=0.006, seg=2)
box("ac_flap", "white", (0.40, 0.96), (2.03, 2.05), (IZ + 0.185, IZ + 0.215), bevel=0.006, seg=2)
mat("led", color=(0.1, 0.6, 0.3), rough=0.4, emit=((0.2, 1.0, 0.5), 2.0))
box("ac_led", "led", (0.93, 0.94), (2.08, 2.09), (IZ + 0.209, IZ + 0.212))

# ================================================================ Poly Haven props (kept as their own meshes)
PROPS = []
def import_asset(k, loc, ry=0.0, scale=1.0, keep=None, drop=()):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f"{AS}/{k}/{k}.gltf")
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type == 'MESH' and (any(d in o.name for d in drop) or (keep and not any(kk in o.name for kk in keep))):
            bpy.data.objects.remove(o); new.remove(o)
    root = bpy.data.objects.new(k, None); SC.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.location = B(*loc); root.rotation_euler = (0, 0, ry); root.scale = (scale,) * 3
    PROPS.extend(o for o in new if o.type == 'MESH'); return root, new
# desk lamp: base at the back-left corner, its head reaching over towards the keyboard
lamp_root, lamp_objs = import_asset("desk_lamp_arm_01", (-1.74, DTOP, -1.30), ry=0.0, scale=0.8)
bpy.context.view_layer.update()
lm = [o for o in lamp_objs if o.type == 'MESH'][0]
def head_centre():
    me = lm.data; idx = [i for i, m in enumerate(me.materials) if m and m.name.endswith("_light")]
    ps = [lm.matrix_world @ p.center for p in me.polygons if p.material_index in idx]
    return sum(ps, Vector()) / len(ps) if ps else None
# turn the lamp so its head points at the keyboard
hc = head_centre(); base = lamp_root.location.copy()
d0 = Vector((hc.x - base.x, hc.y - base.y)); want = Vector((-1.25 - (-1.74), -(-1.05) - (1.30)))   # Blender xy towards (x=-1.25, z=-1.05)
ang = math.atan2(want.y, want.x) - math.atan2(d0.y, d0.x)
lamp_root.rotation_euler = (0, 0, ang); bpy.context.view_layer.update()
hc = head_centre(); print("LAMP HEAD (blender)", tuple(round(v, 3) for v in hc))
marker("SURF_lamp", (hc.x, hc.z - 0.02, -hc.y))
# plants: a philodendron on the floor by the window wall, a succulent on the desk
pr, po = import_asset("potted_plant_02", (-1.66, FY, -0.36), ry=0.8, scale=0.85, drop=("dirt",))
d = cyl("plant_soil", "painted", (-1.66, -0.36), 0.172, FY + 0.27, FY + 0.272, n=28); set_vcol(d, srgb("#2a2018"))
import_asset("potted_plant_04", (-0.48, DTOP, -1.14), ry=0.3, scale=0.9)
import_asset("wall_clock", (0.68, 1.70, IZ + 0.0), ry=0.0, scale=0.85)
import_asset("alarm_clock_01", (-1.87, WY0, 0.62), ry=-math.pi / 2 + 0.35, scale=0.8)
import_asset("cardboard_box_01", (0.10, STOP, -1.31), ry=0.1, scale=0.62)
import_asset("office_notepads", (-0.47, DTOP, -0.92), ry=0.3, keep=("sticky_stack",))

# ================================================================ finish: modifiers applied, static parts joined
bpy.context.view_layer.update()
for o in STATIC:
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
for o in STATIC: project_uv(o)
STATIC_OBJS = [o for o in STATIC if o.name in bpy.data.objects]
# tiny parts (keycaps, pens, wheels...) get no AO texels: flag them, so the atlas spends its pixels on big surfaces
for o in STATIC_OBJS:
    area = sum(p.area for p in o.data.polygons) * (o.matrix_world.to_scale()[0] ** 2)
    a = o.data.attributes.new("small", 'INT', 'FACE')
    for d in a.data: d.value = 1 if area < 0.006 else 0
room = join(STATIC_OBJS, "room_static"); room.data.name = "room_static"
# lightmap UVs for the ambient occlusion bake
uv2 = room.data.uv_layers.new(name="AO")
room.data.uv_layers.active = uv2
small = [d.value for d in room.data.attributes["small"].data]
for p in room.data.polygons:                     # faces nobody looks at: undersides, the outside of the two walls
    n, c = p.normal, p.center
    if (n.z < -0.9 and c.z < FY + 0.06) or (n.x < -0.9 and c.x < X0 + 1e-3) or (n.y > 0.9 and c.y > -Z0 - 1e-3): small[p.index] = 1
for p in room.data.polygons: p.select = not small[p.index]
bpy.ops.object.select_all(action='DESELECT'); room.select_set(True); bpy.context.view_layer.objects.active = room
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.002, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.002, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')
uv2 = room.data.uv_layers["AO"]                  # (re-fetched: edit mode rebuilt the mesh data)
for p in room.data.polygons:                     # keep a white corner (u, v > 0.988) for the tiny parts
    for li in p.loop_indices:
        uv2.data[li].uv = (0.995, 0.995) if small[p.index] else (uv2.data[li].uv[0] * 0.985, uv2.data[li].uv[1] * 0.985)
room.data.attributes.remove(room.data.attributes["small"])
room.data.uv_layers.active = room.data.uv_layers["AO"]       # (removing an attribute can move the active UV map)
print("bake UV", room.data.uv_layers.active.name, [u.name for u in room.data.uv_layers])
print("small faces", sum(small), "of", len(small))
print("STATIC tris", sum(len(p.vertices) - 2 for p in room.data.polygons), "materials", [m.name for m in room.data.materials])

# the chair's own AO atlas (small: one object)
cuv = CHAIR.data.uv_layers.new(name="AO")
bpy.ops.object.select_all(action='DESELECT'); CHAIR.select_set(True); bpy.context.view_layer.objects.active = CHAIR
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
CHAIR.data.uv_layers.active = CHAIR.data.uv_layers["AO"]
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')
CHAIR.data.uv_layers.active = CHAIR.data.uv_layers["AO"]
print("CHAIR tris", sum(len(p.vertices) - 2 for p in CHAIR.data.polygons), "materials", [m.name for m in CHAIR.data.materials],
      "pivot", tuple(round(v, 4) for v in CHAIR.location), "rot z", round(CHAIR.rotation_euler.z, 4))

def bake_ao(obj, size, path, hide):
    """AO of `obj` into its "AO" UV set, with the objects in `hide` left out of the render"""
    for o in hide: o.hide_render = True
    img = bpy.data.images.new(obj.name + "_ao", size, size, alpha=False, float_buffer=False); img.colorspace_settings.name = "Non-Color"
    for m in obj.data.materials:
        nt = m.node_tree; t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.name = "BAKE"
        for n in nt.nodes: n.select = False
        t.select = True; nt.nodes.active = t
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers["AO"]
    bpy.ops.object.bake(type='AO', margin=6, uv_layer="AO")
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    for m in obj.data.materials: m.node_tree.nodes.remove(m.node_tree.nodes["BAKE"])
    for o in hide: o.hide_render = False

if not NOBAKE:
    SC.render.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = int(os.environ.get("AO_SAMPLES", "128"))
    w = bpy.data.worlds.new("w"); SC.world = w; w.light_settings.distance = 0.35
    SC.render.bake.margin = 6; SC.render.bake.use_selected_to_active = False
    # the room without the chair (it moves: no chair-shaped AO footprint may stay behind on the floor; the real-time
    # shadows ground it), the props occlude; then the chair on its own (self-occlusion only, true wherever it stands)
    bake_ao(room, 2048, f"{OUT}/ao_raw.png", [CHAIR])
    bake_ao(CHAIR, 512, f"{OUT}/ao_chair.png", [o for o in SC.objects if o is not CHAIR and o.type == 'MESH'])
for o in (room, CHAIR):
    o.data.uv_layers.active = o.data.uv_layers["UVMap"]; o.data.uv_layers["UVMap"].active_render = True
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=f"{OUT}/room_raw.glb", export_format='GLB', use_selection=False, export_extras=True, export_yup=True,
                          export_apply=True, export_texcoords=True, export_normals=True, export_tangents=False, export_materials='EXPORT',
                          export_image_format='AUTO', export_cameras=False, export_lights=False, export_vertex_color='MATERIAL')
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/room.blend")
print("DONE")
