"""The room's soft goods at game quality (#98 G4): socks and a towel on the pinch hanger, the hand towel in terry cloth,
the duvet (cloth-simulated, turned back at the head end, box-quilted), the pillow (a sewn case with its seam and a head
dent), the mattress with its fitted sheet, the curtains (pencil pleats, hems), the rug and its binding, the floor cushion
(tufted, piped), the hoodie and the tote on the door hooks, the backpack, and two clothes: jeans dropped by the bed's
foot and a T-shirt thrown on the bed (cloth-simulated).

Called from build_room.py:  `import props_soft as PS; PS.bind(globals())` right after the materials, then one call per
item where its old code was. Everything here is geometry built from code (CC0) with Poly Haven CC0 fabric textures
prepared by tex_prep.py (credits: web/room/CREDITS.md). Coordinates in the builders are glTF/three.js world units like the
rest of the build (x right, y up, z towards the viewer); `Bv` converts a glTF Vector into Blender's.

Names, origins and node structure that web/room.html relies on are untouched: the hoodie's and the tote's parts join the
"hangers" node (origin at the door hinge), the pillow and the mattress keep their names (the duvet's cloth sim collides
with them), the curtains are "curtain_a" / "curtain_b" and the rug is "rug" for the prop sweep.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

G = None            # build_room.py's globals (live: names defined later in the build are read when a builder runs)


def bind(ns):
    global G, B, mat, MATS, new_obj, project_uv, box, cyl, transform, set_vcol, STATIC, SC, srgb
    G = ns
    B, mat, MATS, new_obj, project_uv, box, cyl = ns["B"], ns["mat"], ns["MATS"], ns["new_obj"], ns["project_uv"], ns["box"], ns["cyl"]
    transform, set_vcol, STATIC, SC, srgb = ns["transform"], ns["set_vcol"], ns["STATIC"], ns["SC"], ns["srgb"]
    materials()


def Bv(v): return B(v.x, v.y, v.z)
def gl(v): return Vector((v.x, v.z, -v.y))          # Blender -> glTF


# ---------------------------------------------------------------- materials (fabrics; all textures from tex_prep.py)
def fab(name, sheen=0.0, **kw):
    """a fabric: build_room's mat() plus a sheen (KHR_materials_sheen: the soft rim light of fibres)"""
    m = mat(name, **kw)
    if sheen:
        P = m.node_tree.nodes["Principled BSDF"]
        P.inputs["Sheen Weight"].default_value = sheen; P.inputs["Sheen Roughness"].default_value = 0.6
    return m


def materials():
    fab("sheet", diff="sheet_diff.jpg", nor="sheet_nor.jpg", nstr=0.7, rough=0.9, uv=0.26)                      # cotton jersey (white)
    fab("duvet", diff="duvet_diff.jpg", nor="duvet_nor.jpg", nstr=0.9, rough=0.95, uv=0.28, sheen=0.25)         # waffle pique, slate
    fab("curtain", diff="curtain_diff.jpg", nor="curtain_nor.jpg", nstr=0.8, rough=0.95, uv=0.27, sheen=0.45)   # rough linen, light
    fab("rug", diff="rug_diff.jpg", nor="rug_nor.jpg", rough=1.0, uv=0.32, sheen=0.3)                           # wool herringbone
    fab("hoodie", diff="hoodie_diff.jpg", nor="hoodie_nor.jpg", nstr=0.9, rough=0.95, uv=0.27, sheen=0.3)       # jogging melange
    fab("rib", color=srgb("#4f5560"), rough=0.95, nor="rib_nor.jpg", nstr=1.0, uv=0.045, sheen=0.3)             # ribbed cuffs and hem
    fab("bag", vcol=True, rough=0.78, nor="bag_nor.jpg", nstr=0.8, uv=0.09, sheen=0.15)                          # polyester weave (colour per vertex: body, piping, webbing)
    fab("cushion", diff="cushion_diff.jpg", nor="sheet_nor.jpg", nstr=0.8, rough=0.95, uv=0.26, sheen=0.25)     # cotton, mustard
    fab("knit", vcol=True, rough=0.95, nor="knit_nor.jpg", nstr=1.0, uv=0.075, sheen=0.4)                       # socks (colour per vertex)
    fab("terry", diff="terry_diff.jpg", nor="terry_nor.jpg", nstr=1.0, rough=1.0, uv=0.18, sheen=0.5)           # the towel
    fab("canvas", diff="canvas_diff.jpg", nor="curtain_nor.jpg", nstr=0.7, rough=0.9, uv=0.27)                  # the tote
    fab("denim", diff="denim_diff.jpg", nor="denim_nor.jpg", nstr=0.9, rough=0.9, uv=0.27)                      # jeans
    fab("jersey", vcol=True, rough=0.92, nor="sheet_nor.jpg", nstr=0.7, uv=0.26, sheen=0.25)                    # T-shirt, mattress ticking, sneakers' canvas
    fab("fleece", diff="fleece_diff.jpg", nor="fleece_nor.jpg", nstr=1.0, rough=1.0, uv=0.27, sheen=0.55)      # the throw blanket


# ---------------------------------------------------------------- builders (glTF coordinates in, Blender meshes out)
def smooth01(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a))) if b != a else float(x >= b)
    return t * t * (3 - 2 * t)


def bump(x, c, w):
    """1 at c, 0 beyond c +- w (smooth)"""
    return max(0.0, 1 - ((x - c) / w) ** 2) ** 2


def nz(p, scale=1.0, seed=0.0):
    """smooth noise in -1..1 at a glTF point"""
    return noise.noise(Vector((p.x * scale + seed * 7.1, p.y * scale + seed * 3.3, p.z * scale - seed * 5.7)))


def grid_obj(nm, material, grid, static=True, flip=False):
    """a sheet from rows of glTF points: face (j,i)-(j,i+1)-(j+1,i+1)-(j+1,i); its normal is (along i) x (along j)"""
    bm = bmesh.new(); V = [[bm.verts.new(Bv(p)) for p in row] for row in grid]
    for j in range(len(V) - 1):
        for i in range(len(V[j]) - 1):
            q = [V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i]]
            f = bm.faces.new(q[::-1] if flip else q); f.smooth = True
    return new_obj(nm, bm, material, static)


def tube_obj(nm, material, rings, static=True, cap=(False, False), closed=False):
    """a tube through rings of glTF points (same count each); cap: a face on the first / last ring; closed: a loop (the
    last ring joins the first). Collapsed rings (a tiny radius) become a pole."""
    bm = bmesh.new(); R = [[bm.verts.new(Bv(p)) for p in ring] for ring in rings]; n = len(rings[0])
    if closed: R.append(R[0])
    for k in range(len(R) - 1):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new([R[k][i], R[k][j], R[k + 1][j], R[k + 1][i]]); f.smooth = True
    if cap[0]: bm.faces.new(list(reversed(R[0]))).smooth = True
    if cap[1]: bm.faces.new(R[-1]).smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=5e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return new_obj(nm, bm, material, static)


def frames(pts, ref):
    """per point of a glTF polyline: (tangent, width axis, the third axis). ref: a Vector made perpendicular to the
    tangent, or "h": the width axis horizontal (up x tangent; the third axis then points up for a path lying flat)"""
    out = []; up = Vector((0, 1, 0))
    for k in range(len(pts)):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        w = up.cross(t) if ref == "h" else ref - ref.dot(t) * t
        w = w.normalized() if w.length > 1e-6 else t.orthogonal().normalized()
        out.append((t, w, t.cross(w).normalized()))
    return out


def ring(c, ax_a, ax_b, a, b, n, fn=None, p=2.0):
    """an ellipse (or a superellipse, p > 2: squarer) of half-axes a along ax_a and b along ax_b; fn(theta) scales"""
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n; ct, st = math.cos(th), math.sin(th)
        if p != 2.0: ct, st = math.copysign(abs(ct) ** (2 / p), ct), math.copysign(abs(st) ** (2 / p), st)
        r = 1.0 if fn is None else fn(th)
        pts.append(c + ax_a * (a * r * ct) + ax_b * (b * r * st))
    return pts


def tube_along(nm, material, path, a, b, n=12, ref=Vector((0, 1, 0)), taper=None, fn=None, static=True, cap=(False, False), p=2.0):
    """a tube of elliptical section (a along ref's projection, b across) along a glTF polyline; taper(k, N) scales"""
    F = frames(path, ref); rings = []
    for k, (c, (t, w, nn)) in enumerate(zip(path, F)):
        s = 1.0 if taper is None else taper(k / max(1, len(path) - 1))
        aa, bb = (a * s, b * s) if not isinstance(s, tuple) else (a * s[0], b * s[1])
        rings.append(ring(c, w, nn, aa, bb, n, fn=(lambda th, k=k: fn(th, k / max(1, len(path) - 1))) if fn else None, p=p))
    return tube_obj(nm, material, rings, static=static, cap=cap)


def paint(o, fn, by_index=False):
    """per-vertex colour: fn(glTF position) -> linear rgb (or fn(vertex index) with by_index)"""
    me = o.data; a = me.color_attributes.get("Col") or me.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    for pg in me.polygons:
        for li in pg.loop_indices:
            vi = me.loops[li].vertex_index
            a.data[li].color = (*(fn(vi) if by_index else fn(gl(me.vertices[vi].co))), 1)


def displace(o, fn):
    """move every vertex along its normal by fn(glTF position, glTF normal)"""
    me = o.data; me.update()
    for v in me.vertices:
        d = fn(gl(v.co), gl(v.normal))
        if d: v.co += v.normal * d


def unspike(o, tol=0.05, rounds=4):
    """after a cloth simulation: a vertex the solver shot away (pinched between colliders) is put back among its
    neighbours; repeated, so a stray cluster collapses onto the cloth"""
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); total = 0
    for _ in range(rounds):
        moves = []
        for v in bm.verts:
            nb = [e.other_vert(v).co for e in v.link_edges]
            if not nb: continue
            mean = sum(nb, Vector()) / len(nb)
            if (v.co - mean).length > tol: moves.append((v, mean))
        for v, mean in moves: v.co = mean
        total += len(moves)
        if not moves: break
    bm.to_mesh(o.data); bm.free(); o.data.update()
    if total: print(o.name + ": put back", total, "stray vertices")


def smooth_mesh(o, factor=0.4, repeat=1):
    bm = bmesh.new(); bm.from_mesh(o.data)
    for _ in range(repeat): bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(o.data); bm.free(); o.data.update()


def thin(o):
    """a thin thing (piping, a cord, a strap): its AO islands would get no texel, so the bake gives it the white corner"""
    o["ao_small"] = 1; return o


def sheet(o, thickness, even=True):
    """a thin cloth sheet: thickened symmetrically, without rim faces (their islands get no AO texel and render black);
    even=False for a simulated cloth with sharp folds (an even thickness shoots out at a fold)"""
    md = o.modifiers.new("solid", "SOLIDIFY"); md.thickness = thickness; md.offset = 0; md.use_even_offset = even; md.use_rim = False
    return md


def rounded_rect(y0, y1, z0, z1, r, ins, levels, n_top=10, n_bot=4, n_arc=5):
    """points (y, z) around a rounded rectangle shrunk by `ins` (corner radius r - ins), counter-clockwise seen from +x,
    with the same count for every `ins`: the sides keep the given y levels (constant: y0 + r .. y1 - r)"""
    rc = max(1e-4, r - ins); Y0, Y1, Z0, Z1 = y0 + ins, y1 - ins, z0 + ins, z1 - ins; pts = []
    def arc(cy, cz, a0, a1, k0, k1):
        for k in range(k0, k1):
            a = math.radians(a0 + (a1 - a0) * k / n_arc); pts.append((cy + rc * math.sin(a), cz + rc * math.cos(a)))
    for k in range(n_top + 1): pts.append((Y1, (Z1 - rc) + ((Z0 + rc) - (Z1 - rc)) * k / n_top))      # top, front to back
    arc(Y1 - rc, Z0 + rc, 90, 180, 1, n_arc + 1)                                                        # top-back corner
    for y in reversed(levels): pts.append((y, Z0))                                                      # back side, down (interior levels)
    arc(Y0 + rc, Z0 + rc, 180, 270, 0, n_arc + 1)
    for k in range(1, n_bot + 1): pts.append((Y0, (Z0 + rc) + ((Z1 - rc) - (Z0 + rc)) * k / n_bot))   # bottom, back to front
    arc(Y0 + rc, Z1 - rc, 270, 360, 1, n_arc + 1)
    for y in levels: pts.append((y, Z1))                                                                # front side, up
    arc(Y1 - rc, Z1 - rc, 0, 90, 0, n_arc)
    return pts


# ================================================================ curtains: pencil-pleat heading, hems, a linen that lets light in
def curtain(nm, za, zb, side):
    """a gathered linen panel between za..zb (z), hanging from the rod to just above the sill. The heading is gathered
    into ten pencil pleats that merge into four soft folds towards the hem; the hem, the heading and the side hems are
    double (thicker), the hem edge waves a little with the folds, and the panel flares slightly at the bottom."""
    ROD_Y, IX, WY0 = G["ROD_Y"], G["IX"], G["WY0"]
    nz_, ny = 48, 26; top = ROD_Y - 0.012; bot = WY0 + 0.0012; W = zb - za; x0 = IX + 0.07; grid = []
    for j in range(ny + 1):
        t = j / ny; y = top + (bot - top) * t; row = []
        k = min(1.0, t / 0.75) ** 0.8                                   # 0 at the heading (pleats) -> 1 lower down (folds)
        for i in range(nz_ + 1):
            s = i / nz_; z = za + W * s; ph = 2 * math.pi * 8 * s
            f_top = math.sin(ph) + 0.10 * math.sin(3 * ph)                                       # pencil pleats (soft enough for the shell)
            f_low = math.sin(2 * math.pi * 4.0 * s + 0.6 + 0.5 * side) + 0.3 * math.sin(2 * math.pi * 1.5 * s + 2.0)
            x = x0 + (1 - k) * 0.017 * f_top + k * 0.036 * f_low + 0.004 * nz(Vector((s * 5, t * 3, side)))
            zz = z + side * 0.03 * t * t * (s - 0.5) + 0.003 * math.sin(ph) * (1 - k)            # flare; the pleats gather z too
            yy = y + (0.004 * (0.5 + 0.5 * math.sin(2 * math.pi * 4.0 * s + 0.6 + 0.5 * side + 1.0)) if j == ny else 0)
            row.append(Vector((x, yy, zz)))
        grid.append(row)
    o = grid_obj(nm, "curtain", grid)
    vg = o.vertex_groups.new(name="hem")
    for v in o.data.vertices:
        p = gl(v.co); hem = p.y < bot + 0.06 or p.y > top - 0.07 or abs(p.z - za) < 0.025 or abs(p.z - zb) < 0.025
        vg.add([v.index], 1.0 if hem else 0.0, 'REPLACE')
    md = sheet(o, 0.010); md.vertex_group = "hem"; md.thickness_vertex_group = 0.5          # double hems and heading: 10 mm, the panel 5 mm
    return o


def curtains():
    WZ0, WZ1 = G["WZ0"], G["WZ1"]
    curtain("curtain_a", WZ0 - 0.30, WZ0 + 0.05, -1)
    curtain("curtain_b", WZ1 - 0.05, WZ1 + 0.34, 1)


# ================================================================ the bed's soft parts: mattress + fitted sheet, pillow, duvet
def mattress():
    """the mattress as a soft rounded slab (rings along its length): the fitted sheet covers the top and the sides down
    to its elastic hem, 7 cm above the base, with a 3 mm step at the hem; below it the mattress ticking shows. The
    sheet's top is faintly wrinkled."""
    BX0, BX1, BZ0, BZ1, BASE_Y, MAT_Y = (G[k] for k in ("BX0", "BX1", "BZ0", "BZ1", "BASE_Y", "MAT_Y"))
    x0, x1, z0, z1, y0, y1, r = BX0 + 0.045, BX1 - 0.01, BZ0 + 0.01, BZ1 - 0.01, BASE_Y, MAT_Y, 0.05
    band = y0 + 0.07
    levels = [band - 0.004, band, band + 0.004, (band + y1 - r) / 2]              # the sides' interior points (y0 + r .. y1 - r are the arcs')
    ends = [r * (1 - math.cos(math.radians(a))) for a in (0, 12, 25, 40, 56, 73, 90)]           # ring spacing around the ends
    xs = [x0 + d for d in ends] + [x0 + r + (x1 - x0 - 2 * r) * k / 34 for k in range(1, 34)] + [x1 - d for d in reversed(ends)]
    rings = []
    for x in xs:
        d = min(x - x0, x1 - x); ins = r - math.sqrt(max(0.0, r * r - (r - d) ** 2)) if d < r else 0.0
        rings.append([Vector((x, y, z)) for (y, z) in rounded_rect(y0, y1, z0, z1, r, ins, levels)])
    o = tube_obj("mattress", ["sheet", "jersey"], rings, cap=(True, True))
    me = o.data
    for pg in me.polygons:                                        # the ticking below the sheet's hem
        pg.material_index = 1 if gl(pg.center).y < band - 0.001 else 0
    paint(o, lambda p: srgb("#aeb3bd"))
    random.seed(31)
    displace(o, lambda p, n: 0.003 * smooth01(band - 0.004, band + 0.004, p.y) +                   # the sheet's own thickness
             (0.005 * nz(p, 6.0, 1) + 0.0025 * nz(p, 16.0, 2) if n.y > 0.7 and y0 + 0.2 < p.y else 0.0))   # wrinkles on top
    return o


def pillow():
    """a pillow in its case: a soft superellipse body (flatter underneath), the side seam as a thin piped ridge, the
    case's envelope flap at one end (a step), a head dent and small wrinkles"""
    MAT_Y = G["MAT_Y"]
    PW, PL, PT = 0.42, 0.64, 0.15; nv, nth = 40, 44; rings = []               # lofted: a filled pillow, 15 cm at the middle
    for j in range(nv + 1):
        v = j / nv * 2 - 1; e = max(0.0, 1 - abs(v) ** 4)
        a = PW / 2 * (0.06 + 0.94 * e ** 0.35); h = PT / 2 * (0.02 + 0.98 * e ** 0.5); zc = v * PL / 2 * (1 - 0.03 * e)
        pts = []
        for i in range(nth):
            th = 2 * math.pi * i / nth; c, s = math.cos(th), math.sin(th)
            x = a * math.copysign(abs(c) ** (2 / 2.0), c); y = h * math.copysign(abs(s) ** (2 / 2.0), s)
            if y < 0: y *= 0.7                                                   # a little flatter underneath
            pts.append(Vector((x, y, zc)))
        rings.append(pts)
    o = tube_obj("pillow", "sheet", rings, cap=(True, True))
    random.seed(32)
    def d(p, n):
        out = 0.0
        if n.y > 0.3: out += 0.002 * smooth01(0.17, 0.21, p.z)                   # the envelope flap of the case (a soft step)
        if abs(n.y) < 0.6: out += 0.003 * bump(abs(p.x), PW / 2, 0.03)            # the side seam's piping
        return out + 0.0035 * nz(p, 9.0, 3) + 0.0015 * nz(p, 24.0, 4)
    displace(o, d)
    for v in o.data.vertices:                                                     # the dent where his head rests: straight down, so the top never crosses itself
        p = gl(v.co)
        if p.y > 0.005: v.co.z -= 0.018 * math.exp(-(p.x * p.x * 0.7 + (p.z + 0.06) ** 2) / 0.05) * smooth01(0.0, 0.03, p.y)
    o.data.transform(Matrix.Translation(B(-1.58, MAT_Y + 0.006 + 0.7 * PT / 2 + 0.004, 0.87)) @ Matrix.Rotation(0.06, 4, 'Z') @ Matrix.Rotation(-0.05, 4, 'Y'))
    o.data.update(); return o


def duvet(mattress_o, pillow_o):
    """the duvet: a cloth simulation dropped flat onto the bed gives its lower face; the slab is then built explicitly
    (a lower face, an upper face 3 cm above it along the normal, a rim), with its head end turned back over itself:
    the lower face continues round the outside of the fold (radius 4 cm) and becomes the flap's top, the upper face
    round the inside (radius 1 cm) and becomes the flap's underside, laid back over the main part. Subtle box quilting
    (5 x 6 channels, stitch lines 2 mm down, puffs 6 mm up) and small wrinkles on the faces that show.
    web/room.html lifts this duvet over him (#108) by vertex height: on the mattress the lower face lies at ~0.838 m and
    the upper at ~0.868 m (its REF); the parts hanging over the bed's sides are below 0.80 m."""
    BZ0, BZ1, MAT_Y = G["BZ0"], G["BZ1"], G["MAT_Y"]
    NX, NY = 68, 70; L, W = 1.30, 1.54; TH = 0.03; R_IN = 0.010; R_OUT = R_IN + TH; R_MID = R_IN + TH / 2
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=NX, y_subdivisions=NY, size=1.0, location=(0, 0, 0))
    d = bpy.context.active_object; d.name = "duvet_sim"
    d.scale = (L, W, 1); bpy.ops.object.transform_apply(scale=True)
    me = d.data
    uv0 = [(v.co.x / L + 0.5, v.co.y / W + 0.5) for v in me.vertices]          # the flat duvet's own coordinates
    nc = len({round(u, 5) for u, _ in uv0}); nr = len({round(w, 5) for _, w in uv0})
    ij = [(round(u * (nc - 1)), round(w * (nr - 1))) for u, w in uv0]; at = {k: n for n, k in enumerate(ij)}
    xf = -L / 2 + 0.24; i_f = round((xf + L / 2) / L * (nc - 1))               # the fold line, on a grid column
    d.location = B(-0.85, MAT_Y + 0.13, (BZ0 + BZ1) / 2 + 0.01); bpy.ops.object.transform_apply(location=True)
    colliders = [mattress_o, pillow_o, bpy.data.objects["bed_base"], bpy.data.objects["bed_head"], bpy.data.objects["floor"]]
    for o in colliders:
        o.modifiers.new("col", "COLLISION"); o.collision.thickness_outer = 0.004; o.collision.cloth_friction = 10
    cl = d.modifiers.new("cloth", "CLOTH"); s = cl.settings
    s.quality = 8; s.mass = 0.4; s.tension_stiffness = 20; s.compression_stiffness = 20; s.shear_stiffness = 8; s.bending_stiffness = 1.0
    s.air_damping = 2.0; cl.collision_settings.distance_min = 0.008; cl.collision_settings.use_self_collision = False
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = 60
    for f in range(1, 48): SC.frame_set(f)
    bpy.context.view_layer.objects.active = d; bpy.ops.object.modifier_apply(modifier="cloth")
    for o in colliders:
        for m in list(o.modifiers):
            if m.type == 'COLLISION': o.modifiers.remove(m)
    SC.frame_set(1)
    unspike(d, 0.06); smooth_mesh(d, 0.35, 1); me = d.data
    pos = [v.co.copy() for v in me.vertices]; nrm = [v.normal.copy() for v in me.vertices]   # Blender coords; normals point up / outward
    P = lambda i, j: pos[at[(i, j)]]; N = lambda i, j: nrm[at[(i, j)]]
    def row_avg(fn, i, j, k=2):                                                     # smoothed along the rows: no sawtooth at the fold
        js = range(max(0, j - k), min(nr - 1, j + k) + 1); return sum((fn(i, jj) for jj in js), Vector()) / len(js)
    dx = L / (nc - 1); lower, upper = {}, {}                                        # the two faces of the slab, per grid point
    rows = {}
    for j in range(nr):
        Pm = [P(i, j) for i in range(i_f, nc)]; S = [0.0]
        for a_, b_ in zip(Pm, Pm[1:]): S.append(S[-1] + (b_ - a_).length)
        rows[j] = (Pm, S)
    random.seed(46); cu, cw = L / 5, W / 6
    def puff(u, w):
        fu, fw = (u * L / cu) % 1.0, (w * W / cw) % 1.0; border = min(1.0, min(u, 1 - u) * L / 0.07, min(w, 1 - w) * W / 0.07)
        return border * (0.008 * math.sin(math.pi * fu) * math.sin(math.pi * fw) - 0.002) + (1 - border) * 0.004
    for n, (i, j) in enumerate(ij):
        u, w = uv0[n]
        if i >= i_f:                                                                 # the main part: lies on the bed
            lo = P(i, j); nn = N(i, j)
            lower[(i, j)] = lo; upper[(i, j)] = lo + nn * (TH + puff(u, w) + 0.003 * nz(gl(lo), 7.0, 4))
        else:                                                                        # the flap: round the fold, then back over the top
            P0 = row_avg(P, i_f, j); nn = row_avg(N, i_f, j).normalized(); T = (row_avg(P, i_f + 1, j) - P0).normalized()
            dist = (i_f - i) * dx; C = P0 + nn * (TH + R_IN)                       # the fold's centre (above the upper face at the fold line)
            if dist < math.pi * R_MID:
                th = dist / R_MID
                upper[(i, j)] = C - nn * (R_IN * math.cos(th)) + T * (R_IN * math.sin(th))      # inside of the fold
                lower[(i, j)] = C - nn * (R_OUT * math.cos(th)) + T * (R_OUT * math.sin(th))    # outside of the fold (what shows)
            else:
                Pm, S = rows[j]; s_ = dist - math.pi * R_MID
                m = max(0, min(len(S) - 2, next((k for k in range(len(S) - 1) if S[k + 1] > s_), len(S) - 2)))
                t = (s_ - S[m]) / max(1e-6, S[m + 1] - S[m]); base = Pm[m].lerp(Pm[m + 1], t)
                nb = (row_avg(N, i_f + m, j) * (1 - t) + row_avg(N, min(nc - 1, i_f + m + 1), j) * t).normalized()
                upper[(i, j)] = base + nb * (TH + 2 * R_IN)                                       # the flap's underside, 2 cm over the main part
                lower[(i, j)] = base + nb * (2 * TH + 2 * R_IN + puff(u, w) + 0.003 * nz(gl(base), 7.0, 5))   # the flap's top (the old lower face)
    bpy.data.objects.remove(d)
    bm = bmesh.new(); VL = {k: bm.verts.new(v) for k, v in lower.items()}; VU = {k: bm.verts.new(v) for k, v in upper.items()}
    for i in range(nc - 1):
        for j in range(nr - 1):
            bm.faces.new([VL[(i, j)], VL[(i + 1, j)], VL[(i + 1, j + 1)], VL[(i, j + 1)]]).smooth = True
            bm.faces.new([VU[(i, j)], VU[(i, j + 1)], VU[(i + 1, j + 1)], VU[(i + 1, j)]]).smooth = True
    rim = [(0, j) for j in range(nr)] + [(i, nr - 1) for i in range(1, nc)] + [(nc - 1, j) for j in range(nr - 2, -1, -1)] + [(i, 0) for i in range(nc - 2, 0, -1)]
    for k in range(len(rim)):
        a_, b_ = rim[k], rim[(k + 1) % len(rim)]
        bm.faces.new([VL[a_], VU[a_], VU[b_], VL[b_]]).smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = new_obj("duvet", bm, "duvet")
    return o


# ================================================================ rug: a thick pile with a bound edge, a little uneven
def rug():
    FY = G["FY"]; x0, x1, z0, z1 = -0.50, 0.95, -0.62, 0.85; tp, bw = 0.013, 0.025
    n = 22; grid = []
    random.seed(33)
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x = x0 + bw + (x1 - x0 - 2 * bw) * i / n; z = z0 + bw + (z1 - z0 - 2 * bw) * j / n
            row.append(Vector((x, FY + tp + 0.0025 * nz(Vector((x, 0, z)), 4.0, 5) + 0.001 * nz(Vector((x, 0, z)), 17.0, 6), z)))
        grid.append(row)
    bm = bmesh.new(); V = [[bm.verts.new(Bv(p)) for p in row] for row in grid]
    for j in range(n):
        for i in range(n): bm.faces.new([V[j][i], V[j + 1][i], V[j + 1][i + 1], V[j][i + 1]]).smooth = True
    rim = [V[0][i] for i in range(n)] + [V[j][n] for j in range(n)] + [V[n][i] for i in range(n, 0, -1)] + [V[j][0] for j in range(n, 0, -1)]
    low = [bm.verts.new(Vector((v.co.x, v.co.y, Bv(Vector((0, FY, 0))).z))) for v in rim]
    for k in range(len(rim)):
        k2 = (k + 1) % len(rim); bm.faces.new([rim[k], low[k], low[k2], rim[k2]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    pile = new_obj("rug", bm, "rug")
    # the binding: a cotton tape sewn around the edge, a touch lower than the pile
    tb = tp - 0.002
    for (xa, xb, za, zb) in ((x0, x1, z0, z0 + bw), (x0, x1, z1 - bw, z1), (x0, x0 + bw, z0 + bw, z1 - bw), (x1 - bw, x1, z0 + bw, z1 - bw)):
        b = box("rug", "painted", (xa, xb), (FY, FY + tb), (za, zb), bevel=0.003, seg=2); set_vcol(b, srgb("#4a4440"))
    return pile


# ================================================================ floor cushion (zabuton): tufted at five points, piped edge
def cushion():
    FY = G["FY"]; W, L, T = 0.55, 0.58, 0.09; nu = nv = 20
    tufts = [(0, 0), (0.17, 0.17), (-0.17, 0.17), (0.17, -0.17), (-0.17, -0.17)]
    def h_of(x, z, top):
        u, v = x / (W / 2), z / (L / 2); h = T / 2 * ((1 - u ** 4) * (1 - v ** 4)) ** 0.5 + 0.004
        h *= 1.0 if top else 0.55
        for (tx, tz) in tufts:
            dd = math.hypot(x - tx, z - tz); ph = math.atan2(z - tz, x - tx)
            h *= 1 - 0.7 * math.exp(-dd * dd / (2 * 0.026 ** 2))                           # the tuft pulls the cover in
            h += 0.004 * math.cos(5 * ph + tx * 9) * math.exp(-dd / 0.07) * smooth01(0.02, 0.05, dd)   # gathers around it
        return h + 0.0015 * nz(Vector((x, 0, z)), 12.0, 7)
    top, bot = [], []
    for j in range(nv + 1):
        rt, rb = [], []
        for i in range(nu + 1):
            u = i / nu * 2 - 1; v = j / nv * 2 - 1
            x = u * W / 2 * (1 - 0.04 * (1 - v * v)); z = v * L / 2 * (1 - 0.04 * (1 - u * u))
            rt.append(Vector((x, h_of(x, z, True), z))); rb.append(Vector((x, -h_of(x, z, False), z)))
        top.append(rt); bot.append(rb)
    bm = bmesh.new(); Tv = [[bm.verts.new(Bv(p)) for p in r] for r in top]; Bb = [[bm.verts.new(Bv(p)) for p in r] for r in bot]
    for j in range(nv):
        for i in range(nu):
            bm.faces.new([Tv[j][i], Tv[j][i + 1], Tv[j + 1][i + 1], Tv[j + 1][i]]).smooth = True
            bm.faces.new([Bb[j][i], Bb[j + 1][i], Bb[j + 1][i + 1], Bb[j][i + 1]]).smooth = True
    edge = [(0, i) for i in range(nu)] + [(j, nu) for j in range(nv)] + [(nv, i) for i in range(nu, 0, -1)] + [(j, 0) for j in range(nv, 0, -1)]
    for k in range(len(edge)):
        (j0, i0), (j1, i1) = edge[k], edge[(k + 1) % len(edge)]
        bm.faces.new([Tv[j0][i0], Bb[j0][i0], Bb[j1][i1], Tv[j1][i1]]).smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    body = new_obj("cushion", bm, "cushion")
    path = [(top[j][i] + bot[j][i]) / 2 for (j, i) in edge]                                  # the piping along the side seam
    pipe = thin(tube_along("cushion_pipe", "cushion", path + path[:1], 0.0045, 0.0045, n=8, ref="h"))
    parts = [body, pipe]
    for o in parts: transform(o, loc=(1.32, 0, 0.98), ry=0.28)
    G["settle"](parts, FY); [project_uv(o) for o in parts]
    return parts


# ================================================================ the laundry pinch hanger: socks with heels and toes, a terry towel
def sock(nm, clip, y_top, ry, colour, heel, stripes=()):
    """a sock pinched at the cuff by a clip at (x, z) = clip, hanging from y_top: the cuff gathers to the clip and its
    edges droop, ribbing round the cuff, a flat leg, the heel bulging at the bend, the foot dangling forward (+x, turned
    by ry) and a rounded toe. heel: the heel-and-toe colour; stripes: (from, to, colour) along the length (m)."""
    n = 24; L_leg, R_b, phi, L_foot = 0.150, 0.03, 0.55, 0.095
    L_bend = R_b * phi; Ltot = L_leg + L_bend + L_foot
    def centre(dist):
        if dist < L_leg: return Vector((0, -dist, 0))
        if dist < L_leg + L_bend:
            a = (dist - L_leg) / R_b; return Vector((R_b * (1 - math.cos(a)), -L_leg - R_b * math.sin(a), 0))
        e = dist - L_leg - L_bend
        return Vector((R_b * (1 - math.cos(phi)), -L_leg - R_b * math.sin(phi), 0)) + Vector((math.sin(phi), -math.cos(phi), 0)) * e
    N = 22; dists = [Ltot * (k / N) ** 0.85 for k in range(N + 1)]                   # denser rings near the cuff
    path = [centre(dd) for dd in dists]
    F = frames(path, Vector((1, 0, 0)))
    rings = []; ring_col = []
    for k, (dd, c, (t, w, nn)) in enumerate(zip(dists, path, F)):
        col = colour
        for (d0, d1, sc) in stripes:
            if d0 <= dd <= d1: col = sc
        if heel and (abs(dd - (L_leg + L_bend * 0.5)) < 0.03 or dd > Ltot - 0.045): col = heel
        ring_col.append(srgb(col))
        pinch = smooth01(0.0, 0.032, dd)
        a = 0.006 + 0.034 * pinch; b = 0.0035 + 0.0085 * pinch
        a *= 1 - 0.09 * bump(dd, 0.064, 0.012)                                       # the cuff's elastic edge
        full = smooth01(L_leg - 0.02, L_leg + L_bend, dd); a += 0.004 * full; b += 0.004 * full
        toe = (dd - (Ltot - 0.036)) / 0.036
        k_toe = math.sqrt(max(1e-6, 1 - toe * toe)) if toe > 0 else 1.0
        if k == N: k_toe = 0.01
        a *= k_toe; b *= k_toe
        ribw = smooth01(0.008, 0.016, dd) * (1 - smooth01(0.050, 0.060, dd))
        heel_amp = 0.55 * bump(dd, L_leg + L_bend * 0.5, 0.05)
        droop = 0.016 * (1 - smooth01(0.0, 0.05, dd))
        pts = []
        for i in range(n):
            th = 2 * math.pi * i / n; ct, st = math.cos(th), math.sin(th)
            r = 1 + 0.11 * math.cos(8 * th) * ribw + heel_amp * max(0.0, -ct) ** 1.5
            p = c + w * (a * r * ct) + nn * (b * (1 + 0.5 * heel_amp * max(0.0, -ct)) * st)
            p.y -= droop * abs(ct) ** 1.5                                                # the cuff's edges hang below the clip
            pts.append(p)
        rings.append(pts)
    o = tube_obj(nm, "knit", rings, cap=(True, False))
    displace(o, lambda p, nrm: 0.0012 * nz(p, 40.0, 8))
    paint(o, lambda vi: ring_col[min(N, vi // n)], by_index=True)          # (the toe's collapsed ring is the last vertex)
    o.data.transform(Matrix.Translation(B(clip[0], y_top, clip[1])) @ Matrix.Rotation(ry, 4, 'Z')); o.data.update()
    return o


def towel(c0, c1, y_top):
    """a hand towel in terry cloth, pinched by two clips (c0, c1) near the middle of its top edge: it hangs flat between
    them with a slight sag, the corners outside the clips droop and fold forward, soft vertical folds grow towards the
    wavy bottom edge, and the dobby border shows as a low ridge near the hem"""
    W, Lh = 0.30, 0.36; nu, nv = 26, 22
    chord = math.hypot(c1[0] - c0[0], c1[1] - c0[1]); h = chord / 2; out = W / 2 - h
    grid = []
    for j in range(nv + 1):
        t = j / nv; row = []
        for i in range(nu + 1):
            s = i / nu; z = -W / 2 + W * s; dz = max(0.0, abs(z) - h) / out
            droop = 0.055 * dz ** 1.6; sag = 0.008 * (1 - (z / h) ** 2) if abs(z) < h else 0.0
            y = y_top - droop - sag - t * (Lh - 0.3 * droop)
            x = (0.010 * math.sin(2 * math.pi * 2.3 * s + 1.1 * t) * (0.25 + 0.75 * t) + 0.004 * nz(Vector((s * 4, t * 3, 0)), 1.0, 9)
                 + 0.014 * dz ** 1.5 * (1 - t))                                                     # the drooping corners fold forward (+x: into the room)
            zz = z - math.copysign(0.03 * dz ** 1.5 * (1 - 0.5 * t), z)
            if j == nv: y += 0.004 * (0.5 + 0.5 * math.sin(2 * math.pi * 2.3 * s + 1.1))            # a wavy hem
            if 0.84 < t < 0.92: x += 0.0015                                                          # the dobby border
            row.append(Vector((x, y, zz)))
        grid.append(row)
    o = grid_obj("towel", "terry", grid); sheet(o, 0.006)
    ry = math.atan2(c1[0] - c0[0], c1[1] - c0[1])
    if math.cos(ry) < 0: ry += math.pi                                   # its folds and corners come forward into the room, never into the window wall
    transform(o, loc=((c0[0] + c1[0]) / 2, 0, (c0[1] + c1[1]) / 2), ry=ry)
    return o


def socks_and_towel(clips, PH):
    """clips: the pinch clips' (x, z) round the hanger ring (8); PH: the ring's centre (x, y, z). Two pairs of socks on
    clips 1, 2, 5, 6 (their feet point away from the ring's centre, clear of the window wall and of each other) and the
    towel between clips 3 and 4."""
    y_top = PH[1] - 0.045 + 0.012
    pairs = [(1, "#2d2f36", "#8d9099", ((0.012, 0.018, "#c9c6bd"), (0.024, 0.030, "#c9c6bd"))),
             (2, "#2d2f36", "#8d9099", ((0.012, 0.018, "#c9c6bd"), (0.024, 0.030, "#c9c6bd"))),
             (5, "#d9d3c6", "#8e8a84", ()), (6, "#d9d3c6", "#8e8a84", ())]
    for k, col, heel, stripes in pairs:
        cx, cz = clips[k]; a = math.atan2(cz - PH[2], max(0.25, abs(cx - PH[0])) if cx < PH[0] else cx - PH[0])   # never towards the window wall
        sock("sock", (cx, cz), y_top, -a + random.uniform(-0.15, 0.15), col, heel, stripes)
    towel(clips[3], clips[4], y_top)


# ================================================================ the door hooks: a hoodie, a canvas tote
def tube_pts(pts, n=10):
    """a smooth polyline through control points (Catmull-Rom), n samples per span"""
    P = [pts[0]] + list(pts) + [pts[-1]]; out = []
    for k in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[k - 1], P[k], P[k + 1], P[k + 2]
        for i in range(n):
            t = i / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2]); return out


def sim_cloth(o, colliders, pins=(), frames=60, mass=0.25, tension=25, bending=0.3, self_col=False, friction=10, damping=2.0, quality=8):
    """a cloth simulation of `o` with the vertex indices `pins` held where they are, against the colliders; applied"""
    if pins:
        vg = o.vertex_groups.new(name="pin"); vg.add(list(pins), 1.0, 'REPLACE')
    for c in colliders:
        c.modifiers.new("col", "COLLISION"); c.collision.thickness_outer = 0.004; c.collision.cloth_friction = friction
    cl = o.modifiers.new("cloth", "CLOTH"); s = cl.settings
    s.quality = quality; s.mass = mass; s.tension_stiffness = tension; s.compression_stiffness = tension; s.shear_stiffness = tension / 3
    s.bending_stiffness = bending; s.air_damping = damping
    if pins: s.vertex_group_mass = "pin"
    cl.collision_settings.distance_min = 0.005; cl.collision_settings.use_self_collision = self_col
    if self_col: cl.collision_settings.self_distance_min = 0.004; cl.collision_settings.self_friction = 5
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = frames + 10
    for f in range(1, frames): SC.frame_set(f)
    bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.modifier_apply(modifier="cloth")
    for c in colliders:
        for m in list(c.modifiers):
            if m.type == 'COLLISION': c.modifiers.remove(m)
    SC.frame_set(1); o.vertex_groups.clear(); unspike(o, 0.025, rounds=8)


def garment_tube(nm, material, rings, cap_end=False):
    """a garment's tube (a body, a sleeve) from rings of glTF points; returns the object and the vertex index of each
    (ring, point)"""
    bm = bmesh.new(); V = [[bm.verts.new(Bv(p)) for p in r] for r in rings]; n = len(rings[0])
    for k in range(len(V) - 1):
        for i in range(n):
            j = (i + 1) % n; bm.faces.new([V[k][i], V[k][j], V[k + 1][j], V[k + 1][i]]).smooth = True
    if cap_end: bm.faces.new(V[-1]).smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.verts.index_update()
    ids = [[v.index for v in r] for r in V]
    return new_obj(nm, bm, material), ids


def hoodie(HX):
    """a men's hoodie (M: 70 cm long, 55 cm across the chest, 62 cm sleeves) hung on the door's left hook (HX) by
    the back of its hood: Blender cloth simulations in turn. The body hangs from its neckline, its weight pulling the
    shoulders into a slope and the fabric into folds that run down from the neck, resting on the door; the sleeves
    hang from the shoulders down the sides, against the body, gathering at the ribbed cuffs; the hood, caught on the
    hook a hand's width above the neck, folds over it and down; two drawstrings hang from the neck. The ribbed hem and
    cuffs are "rib". Returns its parts (they join the "hangers" node)."""
    IZ = G["IZ"]; random.seed(41); parts = []
    door = [bpy.data.objects["door_leaf"]] + [o for o in STATIC if o.name.split(".")[0] in ("hook", "hook_tip", "hook_rail")]
    HY, HZ = 1.765, IZ + 0.10                                                      # the hook's tip
    NECK_Y = HY - 0.10; ZC = IZ + 0.103; L, HALF, DEP = 0.70, 0.275, 0.05
    # --- the body: a flattened tube, the neckline gathered (pinned), out to the full chest below the shoulders
    NR, NP = 26, 36; rings = []
    for k in range(NR + 1):
        t = k / NR; y = NECK_Y - L * t
        hw = 0.085 + (HALF - 0.085) * smooth01(0.0, 0.16, t); dp = 0.032 + (DEP - 0.032) * smooth01(0.0, 0.12, t)
        if t > 0.93: hw *= 0.94                                                    # the ribbed hem hugs
        rings.append([Vector((HX + hw * math.cos(2 * math.pi * i / NP) * (1 + 0.01 * random.uniform(-1, 1)), y, ZC + dp * math.sin(2 * math.pi * i / NP))) for i in range(NP)])
    body, bid = garment_tube("hoodie", ["hoodie", "rib"], rings)
    sim_cloth(body, door, pins=bid[0], frames=55, mass=0.3, tension=30, bending=0.25, friction=12)
    smooth_mesh(body, 0.4, 2)
    for pg in body.data.polygons: pg.material_index = 1 if gl(pg.center).y < NECK_Y - L * 0.935 + 0.0 else 0
    parts.append(body)
    me = body.data
    BP = lambda k, i: gl(me.vertices[bid[k][i % NP]].co)
    # --- the sleeves: sewn into upright armholes at the shoulders, hanging down the sides just outside the body
    lo_, hi_ = None, None
    for sg in (1, -1):
        side = max if sg > 0 else min
        sh = side((BP(k, i) for k in range(3, 7) for i in range(NP)), key=lambda q: q.x)   # the shoulder's outermost point
        SL, NS, NQ = 0.60, 18, 14
        zf = max(BP(k, NP // 4).z for k in range(4, 12)) + 0.012                     # just in front of the body's front
        ctrl = [Vector((sh.x - sg * 0.05, sh.y - 0.02, zf - 0.035)), Vector((sh.x - sg * 0.03, sh.y - 0.12, zf + 0.004)),
                Vector((sh.x - sg * 0.03, sh.y - 0.38, zf + 0.004)), Vector((sh.x - sg * 0.05, sh.y - 0.03 - SL * 0.97, zf + 0.01))]
        path = resample(tube_pts(ctrl, 8), NS + 1)
        F = frames(path, Vector((0, 0, 1)))
        srings = []
        for k, (c, (t_, w_, n_)) in enumerate(zip(path, F)):
            u = k / NS; a_ = 0.07 - 0.028 * u - (0.006 if u > 0.9 else 0.0); b_ = (0.022 - 0.006 * u) * (0.25 + 0.75 * smooth01(0.0, 0.12, u))   # the top tucked flat into the shoulder
            srings.append(ring(c, w_, n_, b_, a_, NQ))                              # flat: the wide axis across the arm, in the door's plane
        sl, sid = garment_tube("hoodie_sleeve", ["hoodie", "rib"], srings)
        sim_cloth(sl, door, pins=sid[0] + sid[1], frames=50, mass=0.25, tension=30, bending=0.25, friction=6, quality=10)
        smooth_mesh(sl, 0.5, 3)
        for pg in sl.data.polygons: pg.material_index = 1 if gl(pg.center).y < path[0].y - SL * 0.92 else 0
        parts.append(sl)
    # --- the hood: a shell standing up from the back of the neck, caught on the hook, folding over it
    nu, nv = 18, 16; hood = bmesh.new(); HV = []
    for j in range(nv + 1):
        v = j / nv; row = []
        for i in range(nu + 1):
            u = i / nu; ang = math.pi * u                                           # round the back of the head
            r = 0.115 * (0.55 + 0.45 * math.sin(math.pi * min(1.0, v * 1.1)))
            x = HX - r * math.cos(ang); z = ZC + 0.015 + 0.09 * math.sin(ang) * (1 - 0.6 * v) * 0.5
            y = NECK_Y + 0.33 * v
            row.append(hood.verts.new(Bv(Vector((x, y, z)))))
        HV.append(row)
    for j in range(nv):
        for i in range(nu): hood.faces.new([HV[j][i], HV[j][i + 1], HV[j + 1][i + 1], HV[j + 1][i]]).smooth = True
    hood.verts.index_update()
    rim = [HV[0][i].index for i in range(nu + 1)]
    hk = [HV[j][i].index for j in range(nv + 1) for i in range(nu + 1) if (gl(HV[j][i].co) - Vector((HX, HY - 0.005, HZ))).length < 0.045]
    ho = new_obj("hoodie_hood", hood, "hoodie")
    for vi in hk:                                                                  # the hood's back seam rests on the hook's tip
        v = ho.data.vertices[vi]; g = gl(v.co); v.co = Bv(Vector((g.x, max(g.y, HY - 0.002), HZ + 0.008)))
    sim_cloth(ho, door + [body], pins=rim + hk, frames=55, mass=0.2, tension=25, bending=0.6, friction=12)
    smooth_mesh(ho, 0.5, 2)
    parts.append(ho)
    for o in parts: sheet(o, 0.004, even=False)
    # --- drawstrings from the neck's front, hanging over the body
    for sg in (-1, 1):
        p0 = BP(1, NP // 4) + Vector((sg * 0.03, 0, 0.006))
        path = tube_pts([p0, p0 + Vector((sg * 0.006, -0.12, 0.004)), p0 + Vector((sg * 0.012, -0.26, 0.006)), p0 + Vector((sg * 0.010, -0.33, 0.007))], 6)
        st = thin(tube_along("hoodie_string", "painted", path, 0.0028, 0.0028, n=6, cap=(False, True))); set_vcol(st, srgb("#ece8e0")); parts.append(st)
    return parts


def tote(xc, extra_colliders=()):
    """a canvas tote (38 x 38 cm, an 8 cm bottom gusset) on the right hook, a Blender cloth simulation: the bag is pinned
    only where its handles are sewn on, so between them the opening sags, the top corners outside them fold over and
    down, the nearly empty body falls into soft folds that run down from the handles, and it rests against the door
    (and the hoodie beside it). The handles, cotton webbing, go up from their seams and over the hook's tip. Parts are
    named "tote" / "tote_strap" (they join the "hangers" node)."""
    IZ = G["IZ"]; random.seed(42)
    W, Hh, Dg = 0.38, 0.38, 0.055; TOP = 1.50; Z0 = IZ + 0.049                       # (the door leaf's panels reach IZ + 0.043)
    def depth(y): return 0.014 + (Dg - 0.014) * smooth01(TOP - 0.20, TOP - Hh, y)       # the gusset folds in at the top when it hangs
    NW, ND, NV = 16, 4, 17
    per = []                                                                       # the bag's girth: front (+z) left to right, side, back right to left, side
    for i in range(NW): per.append((-W / 2 + W * i / NW, 1.0, "f"))
    for i in range(ND): per.append((W / 2, 1.0 - i / ND, "s"))
    for i in range(NW): per.append((W / 2 - W * i / NW, 0.0, "b"))
    for i in range(ND): per.append((-W / 2, i / ND, "s"))
    bm = bmesh.new(); R = []
    for j in range(NV + 1):
        y = TOP - Hh * j / NV
        R.append([bm.verts.new(Bv(Vector((xc + x + 0.002 * nz(Vector((x, y, z)), 30.0, 50), y, Z0 + z * depth(y))))) for (x, z, _) in per])
    n = len(per)
    for j in range(NV):
        for i in range(n):
            k = (i + 1) % n; bm.faces.new([R[j][i], R[j][k], R[j + 1][k], R[j + 1][i]]).smooth = True
    be = [e for e in bm.edges if e.is_boundary and all(v in set(R[-1]) for v in e.verts)]   # the bottom: a grid of quads
    bmesh.ops.grid_fill(bm, edges=be, use_interp_simple=True)
    for f in bm.faces: f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.verts.index_update()
    pin_ids = [R[0][i].index for i, (x, z, sd) in enumerate(per) if sd in "fb" and abs(abs(x) - 0.085) < 0.016]
    top_ids = [v.index for v in R[0]]
    o = new_obj("tote", bm, "canvas")
    vg = o.vertex_groups.new(name="pin"); vg.add(pin_ids, 1.0, 'REPLACE')
    colliders = [bpy.data.objects["door_leaf"]]
    for c in colliders:
        c.modifiers.new("col", "COLLISION"); c.collision.thickness_outer = 0.004; c.collision.cloth_friction = 8
    cl = o.modifiers.new("cloth", "CLOTH"); s_ = cl.settings
    s_.quality = 8; s_.mass = 0.2; s_.tension_stiffness = 55; s_.compression_stiffness = 55; s_.shear_stiffness = 15; s_.bending_stiffness = 4.0
    s_.air_damping = 4.0; s_.vertex_group_mass = "pin"
    cl.collision_settings.distance_min = 0.005; cl.collision_settings.use_self_collision = True; cl.collision_settings.self_distance_min = 0.003
    cl.collision_settings.self_friction = 5; s_.quality = 12
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = 80
    for fr in range(1, 61): SC.frame_set(fr)
    bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.modifier_apply(modifier="cloth")
    for c in colliders:
        for m in list(c.modifiers):
            if m.type == 'COLLISION': c.modifiers.remove(m)
    SC.frame_set(1); o.vertex_groups.clear()
    unspike(o, 0.02, rounds=8)
    me = o.data
    hood_x = [max(gl(o_.matrix_world @ v.co).x for v in o_.data.vertices) + 0.01 for o_ in extra_colliders[:1]] if extra_colliders else []
    for v in me.vertices:                                                          # never into the door leaf
        g = gl(v.co)
        if g.z < IZ + 0.047: g.z = IZ + 0.047
        if hood_x and g.x < hood_x[0] and g.z > IZ + 0.098: g.z = IZ + 0.098              # behind the hoodie on the next hook
        v.co = Bv(g)
    me.update(); sheet(o, 0.003)
    # the handles: from their seams (the pinned spots, front and back) up over the hook's tip
    hook = Vector((xc, 1.762, IZ + 0.098))
    for sd, zz in (("f", Z0 + 0.014), ("b", Z0)):
        a_, b_ = Vector((xc - 0.085, TOP - 0.01, zz)), Vector((xc + 0.085, TOP - 0.01, zz))
        pts = []
        for k in range(15):
            u = k / 14; e = math.sin(math.pi * u)
            p = a_.lerp(b_, u); p = p.lerp(Vector((xc + (u - 0.5) * 0.03, hook.y + 0.004 * e, hook.z + (0.006 if sd == "f" else -0.006))), e ** 0.55)
            pts.append(p)
        pts[0].y -= 0.02; pts[-1].y -= 0.02                                         # sewn onto the inside of the hem
        thin(tube_along("tote_strap", "canvas", pts, 0.0018, 0.0125, n=8, ref=Vector((0, 0, 1)), cap=(True, True)))
    return o


# ================================================================ the backpack by the bed's foot (#98 soft props, second pass)
def tube_framed(nm, material, path, wdir, ndir, a, b, n=8, cap=(False, False), p=2.0, static=True, taper=None):
    """a tube along a glTF polyline with explicit frames: per point a width axis wdir[k] (half-size a) and a height
    axis ndir[k] (half-size b); p > 2 squares the section (a padded strap, a zip's coil); taper(u) -> (sa, sb)"""
    rings = []
    for k, c in enumerate(path):
        sa, sb = taper(k / max(1, len(path) - 1)) if taper else (1.0, 1.0)
        rings.append(ring(c, wdir[k], ndir[k], a * sa, b * sb, n, p=p))
    return tube_obj(nm, material, rings, static=static, cap=cap)


def strip_framed(nm, material, path, wdir, ndir, w, t, static=True):
    """a flat strap (webbing, a zip's tape) of width w and thickness t along a polyline with explicit frames: a closed
    four-sided section, so it shows from both sides without a solidify"""
    return tube_framed(nm, material, path, wdir, ndir, w / 2, t / 2, n=4, cap=(True, True), p=12.0, static=static)


def polyline_frames(path, up):
    """per point (tangent, width axis = up x tangent, height axis): up[k] is the surface normal under the point"""
    out = []
    for k in range(len(path)):
        t = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
        w = up[k].cross(t); w = w.normalized() if w.length > 1e-6 else t.orthogonal().normalized()
        out.append((t, w, t.cross(w).normalized()))
    return out


def resample(pts, n):
    """n points evenly spaced by arc length along a polyline (open)"""
    S = [0.0]
    for a_, b_ in zip(pts, pts[1:]): S.append(S[-1] + (b_ - a_).length)
    out = []
    for k in range(n):
        s = S[-1] * k / (n - 1); m = max(0, min(len(S) - 2, next((j for j in range(len(S) - 1) if S[j + 1] >= s), len(S) - 2)))
        t = (s - S[m]) / max(1e-9, S[m + 1] - S[m]); out.append(pts[m].lerp(pts[m + 1], t))
    return out


def pack_outline(W, H, rt, rb, n):
    """the front panel's outline (z, y): a "tombstone", top corners of radius rt, bottom ones rb; n points evenly by
    arc length, starting at the bottom's middle and going towards +z (up the +z side, over the top, down the -z side)"""
    d = []; hw = W / 2
    def arc(cz, cy, r, a0, a1, k=24):
        for j in range(k): a = math.radians(a0 + (a1 - a0) * j / k); d.append(Vector((cz + r * math.cos(a), cy + r * math.sin(a))))
    def line(p0, p1, k=24):
        for j in range(k): d.append(Vector(p0).lerp(Vector(p1), j / k))
    line((0, 0), (hw - rb, 0)); arc(hw - rb, rb, rb, -90, 0); line((hw, rb), (hw, H - rt)); arc(hw - rt, H - rt, rt, 0, 90)
    line((hw - rt, H), (-(hw - rt), H)); arc(-(hw - rt), H - rt, rt, 90, 180); line((-hw, H - rt), (-hw, rb)); arc(-(hw - rb), rb, rb, 180, 270)
    line((-(hw - rb), 0), (0, 0)); d.append(Vector((0, 0)))
    return resample(d, n + 1)[:-1]


def backpack():
    """an everyday day pack (~18 L: 45 cm tall, 30 cm wide, 14 cm deep), no brand: standing on the floor by the bed's
    foot end, its back panel towards the bed. Sewn like a real one: a front and a back panel ("tombstone" outlines) and
    a gusset running round the sides and over the top, piped seams where they meet. The body is a Blender cloth
    simulation with a little air pressure and the weight of what is inside, so it settles: the bottom spreads on the
    floor, the half-empty top slumps and creases. On it: the main zip along the gusset over the top (tape, coil, two
    sliders with pulls), a zipped front pocket, a webbing grab handle, and two padded shoulder straps that hang down
    behind it and spill out onto the floor (webbing, ladder-lock buckles, loose tails)."""
    FY, BX1 = G["FY"], G["BX1"]; n0 = len(STATIC); random.seed(43)
    W, H, D, NO = 0.30, 0.45, 0.14, 40
    OUT = pack_outline(W, H, 0.115, 0.05, NO); CY = 0.20
    # rings from the back panel's middle (a pole) out to its seam, across the gusset, in from the front seam to the
    # front panel's middle: (scale of the outline about its centre, depth x, tag)
    PANEL = (0.0, 0.13, 0.26, 0.39, 0.51, 0.62, 0.72, 0.81, 0.88, 0.94)
    spec = [(s, -0.010 * (1 - s * s), "back") for s in PANEL]
    spec += [(0.975, -0.003, "back"), (0.995, 0.006, "seam_b")]
    spec += [(1.0, x, "gusset") for x in (0.026, 0.049, 0.072, 0.095, 0.116)]
    spec += [(0.995, D - 0.006, "seam_f"), (0.975, D + 0.004, "front")]
    spec += [(s, D + 0.026 * (1 - s * s), "front") for s in reversed(PANEL)]
    KB = next(k for k, r in enumerate(spec) if r[2] == "seam_b"); KF = next(k for k, r in enumerate(spec) if r[2] == "seam_f")
    KZ = KB + 3                                                                   # the gusset's middle ring: the main zip
    # the pack's place: back panel 5 cm off the bed's foot end, turned a little towards the room, leaning back 2 degrees
    RY = -0.22; ORG = Vector((BX1 + 0.055, FY, 1.255))
    Mrot = Matrix.Rotation(RY, 3, 'Y') @ Matrix.Rotation(0.035, 3, 'Z')
    def L2W(p): return ORG + Mrot @ p                                             # pack-local glTF -> world glTF
    def settle_shape(x, y, z):
        """what its weight does: the bottom spreads on the floor, the half-empty top sinks and tips a little forward"""
        lo = 1 - smooth01(0.0, 0.13, y)
        z *= 1 + 0.07 * lo; x = D / 2 + (x - D / 2) * (1 + 0.12 * lo)
        t = smooth01(0.22, H, y)
        u = z / (W / 2)
        y -= 0.034 * t ** 1.4 + 0.018 * t ** 3 * max(0.0, 1 - u * u)            # (the top's middle dips most: nothing under it)
        x += 0.026 * t * t - 0.008 * t * (1 - abs(u))
        return Vector((x, max(0.0, y), z))
    bm = bmesh.new(); idx = {}
    for k, (s, x, _) in enumerate(spec):
        if s == 0.0:
            v = bm.verts.new(Bv(L2W(settle_shape(x, CY, 0)))); idx.update({(k, i): v for i in range(NO)})
        else:
            for i, q in enumerate(OUT): idx[(k, i)] = bm.verts.new(Bv(L2W(settle_shape(x, CY + (q.y - CY) * s, q.x * s))))
    for k in range(len(spec) - 1):
        for i in range(NO):
            j = (i + 1) % NO; q = [idx[(k, i)], idx[(k, j)], idx[(k + 1, j)], idx[(k + 1, i)]]
            q = list(dict.fromkeys(q))                                           # (at a pole: a triangle)
            bm.faces.new(q).smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.verts.index_update()
    vid = {key: v.index for key, v in idx.items()}
    body = new_obj("bag_body", bm, "bag")
    Minv = Mrot.inverted()
    def creases(p, n):
        """slump folds across the upper front and the gusset over the top, pinches at the top corners, the padding's
        give on the back panel, and the weave's small irregularity"""
        lp = Minv @ (p - ORG); t = smooth01(0.20, 0.42, lp.y); u = lp.z / (W / 2); ln = Minv @ n
        d = 0.0065 * t * math.sin(2 * math.pi * lp.y / 0.07 + 1.8 * u + 2.2 * nz(p, 5.0, 34)) * (1 - 0.5 * abs(u))
        d += 0.004 * t * bump(abs(u), 0.75, 0.3) * math.sin(2 * math.pi * (lp.x / 0.05 + lp.y / 0.06))
        if ln.x < -0.6: d += -0.002 * (math.sin(math.pi * lp.y / 0.11) ** 2)                 # the back's padded channels
        return d + 0.0015 * nz(p, 14.0, 35) + 0.0007 * nz(p, 40.0, 36)
    displace(body, creases)
    me = body.data; me.update()
    P = lambda k, i: gl(me.vertices[vid[(k, i % NO)]].co)
    Nn = lambda k, i: gl(me.vertices[vid[(k, i % NO)]].normal).normalized()
    Mw = Mrot                                                                      # pack-local directions in the world
    XL, YL, ZL = Mw @ Vector((1, 0, 0)), Vector((0, 1, 0)), Mw @ Vector((0, 0, 1))
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    def hit(y, z, side):                                                          # the body's surface seen from the front (+1) or the back (-1)
        o = L2W(Vector((0.5 * side + D / 2, y, z))); r = bvh.ray_cast(Bv(o), Bv(-XL * side))
        return (gl(r[0]), gl(r[1]).normalized()) if r[0] is not None else (L2W(Vector((D / 2 + side * D / 2, y, z))), XL * side)
    # body colour: slate, a little lighter and dustier at the bottom, a shade darker in the creases
    def body_col(p):
        lp = Mrot.inverted() @ (p - ORG)
        if lp.y < 0.045: return tuple(c * (1 + 0.05 * nz(p, 9.0, 31)) for c in srgb("#23272d"))   # the base: a heavier, darker fabric
        return tuple(c * (1 + 0.06 * nz(p, 9.0, 31)) * (1 + 0.12 * smooth01(0.30, 0.45, lp.y)) for c in srgb("#46536a"))
    paint(body, body_col)
    # piping round both panels
    for k in (KB, KF):
        path = [P(k, i) + Nn(k, i) * 0.0012 for i in range(NO)]
        o = thin(tube_along("bag_piping", "bag", path + path[:1], 0.0032, 0.0032, n=5, ref="h")); paint(o, lambda p: srgb("#262a30"))
    # the main zip: along the gusset's middle, from the +z side 16 cm up, over the top, down to the same height on -z
    top = [i for i in range(NO) if OUT[i].y > 0.16]
    zi = list(range(top[0], top[-1] + 1))
    path = [P(KZ, i) + Nn(KZ, i) * 0.0010 for i in zi]; up = [Nn(KZ, i) for i in zi]
    F = polyline_frames(path, up); wd = [f[1] for f in F]; nd = [f[2] for f in F]
    strip_framed("bag_zip_tape", "bag", path, wd, nd, 0.022, 0.0016); paint(STATIC[-1], lambda p: srgb("#2c3442"))
    tube_framed("bag_zip", "plastic_black", [p + n * 0.0012 for p, n in zip(path, nd)], wd, nd, 0.0035, 0.0012, n=6, p=3.0)
    def slider(c, t, w, n, flip):
        """a zip slider on the coil and its pull: a rubber-coated tab lying along the zip"""
        Mx = Matrix((t, w, n)).transposed()
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            q = Vector((v.co.x * 0.026, v.co.y * 0.011, v.co.z * 0.007 + 0.0045))
            if q.x * flip > 0.0: q.y *= 0.7                                      # tapers to the pull's end
            v.co = Bv(c + Mx @ q)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0018, segments=1, affect='EDGES', clamp_overlap=True)
        new_obj("bag_slider", bm, "metal_dark")
        pull = [c + t * (flip * (0.012 + 0.045 * u)) for u in (0.0, 0.33, 0.66, 1.0)]
        pn = []
        for k, q in enumerate(pull):                                          # lying on the bag, wherever it curves
            loc, nn = bvh.find_nearest(Bv(q))[:2]; nn = gl(nn).normalized(); pull[k] = gl(loc) + nn * (0.0085 - 0.005 * k / 3); pn.append(nn)
        Fp = polyline_frames(pull, pn)
        strip_framed("bag_pull", "bag", pull, [f[1] for f in Fp], [f[2] for f in Fp], 0.011, 0.003); paint(STATIC[-1], lambda p: srgb("#17191c"))
    mid = len(path) // 2
    for kk, fl in ((mid - 3, 1), (mid + 3, -1)):                                 # the two sliders meet a little off the top
        slider(path[kk], F[kk][0], F[kk][1], F[kk][2], fl)
    # the front pocket: a shallow pouch on the front panel's lower half, piped, zipped across its top
    nu, nv = 12, 10; PU, PV0, PV1 = 0.115, 0.045, 0.245
    def pocket_pt(u, v, lift=0.0):
        a2, b2 = u, 2 * v - 1; m = max(abs(a2), abs(b2))                       # the square onto a superellipse: rounded corners
        if m > 1e-6:
            dx, dy = a2 / m, b2 / m; f = (abs(dx) ** 5 + abs(dy) ** 5) ** (-1 / 5); u, v = a2 * f, (b2 * f + 1) / 2
        p, n = hit(PV0 + (PV1 - PV0) * v, u * PU, 1)
        h = 0.0015 + 0.030 * max(0.0, 1 - abs(u) ** 2.5) ** 0.6 * max(0.0, 1 - abs(2 * v - 1) ** 2.5) ** 0.6
        h += 0.0018 * nz(p, 18.0, 33) * (1 - abs(u)) * (1 - abs(2 * v - 1))
        return p + n * (h + lift), n
    grid = [[pocket_pt(-1 + 2 * i / nu, j / nv)[0] for i in range(nu + 1)] for j in range(nv + 1)]
    pk = grid_obj("bag_pocket", "bag", grid, flip=True); sheet(pk, 0.002); paint(pk, body_col)
    rim = [(-1 + 2 * i / nu, 0.0) for i in range(nu)] + [(1.0, j / nv) for j in range(nv)] + [(1 - 2 * i / nu, 1.0) for i in range(nu)] + [(-1.0, 1 - j / nv) for j in range(nv)]
    path = [pocket_pt(u, v, 0.0005)[0] for (u, v) in rim]
    o = thin(tube_along("bag_piping", "bag", path + path[:1], 0.003, 0.003, n=5, ref="h")); paint(o, lambda p: srgb("#262a30"))
    zp = [pocket_pt(-0.82 + 1.64 * i / 16, 0.84) for i in range(17)]
    path = [p + n * 0.0008 for p, n in zp]; F = polyline_frames(path, [n for _, n in zp]); wd = [f[1] for f in F]; nd = [f[2] for f in F]
    strip_framed("bag_zip_tape", "bag", path, wd, nd, 0.020, 0.0016); paint(STATIC[-1], lambda p: srgb("#2c3442"))
    tube_framed("bag_zip", "plastic_black", [p + n * 0.0012 for p, n in zip(path, nd)], wd, nd, 0.003, 0.0011, n=6, p=3.0)
    slider(path[13], F[13][0], F[13][1], F[13][2], -1)
    # a stretch mesh bottle pocket low on the +z side: elastic band at its top, gathered, bulging a little
    def side_hit(y, x):
        o = L2W(Vector((x, y, 0.6))); r = bvh.ray_cast(Bv(o), Bv(-ZL))
        return (gl(r[0]), gl(r[1]).normalized()) if r[0] is not None else (L2W(Vector((x, y, W / 2))), ZL)
    grid = []
    for j in range(9):
        t = j / 8; y = 0.05 + 0.15 * t; row = []
        for i in range(9):
            u = i / 8; x = 0.012 + (D - 0.024) * u; p, n = side_hit(y, x)
            h = 0.003 + 0.022 * math.sin(math.pi * u) ** 0.7 * smooth01(0.0, 0.25, t) * (1 - 0.35 * smooth01(0.75, 1.0, t))
            h += 0.002 * math.sin(2 * math.pi * 3.5 * u) * smooth01(0.7, 1.0, t)            # gathered by the elastic
            row.append(p + n * h)
        grid.append(row)
    sp = grid_obj("bag_side_pocket", "bag", grid, flip=True); sheet(sp, 0.002); paint(sp, lambda p: srgb("#2a313c"))
    band = [grid[-1][i] for i in range(9)]; Fb = polyline_frames(band, [side_hit(0.2, 0.012 + (D - 0.024) * i / 8)[1] for i in range(9)])
    strip_framed("bag_band", "bag", band, [f[1] for f in Fb], [f[2] for f in Fb], 0.012, 0.003); paint(STATIC[-1], lambda p: srgb("#1d2026"))
    # the grab handle: a webbing loop over the top, at the back seam
    it = max(range(NO), key=lambda i: OUT[i].y)
    a_, b_ = P(KB + 1, it - 2), P(KB + 1, it + 2); na = (Nn(KB + 1, it - 2) + Nn(KB + 1, it + 2)).normalized()
    hp = [a_.lerp(b_, u) + na * (0.004 + 0.026 * math.sin(math.pi * u) ** 0.8) for u in [j / 10 for j in range(11)]]
    F = polyline_frames(hp, [na] * len(hp))
    strip_framed("bag_handle", "bag", hp, [f[1] for f in F], [f[2] for f in F], 0.025, 0.0025); paint(STATIC[-1], lambda p: srgb("#1d1f22"))
    # the shoulder straps: padded from the top of the back panel down behind the pack, onto the floor and out to the
    # side in a loose loop; then the webbing from a ladder-lock buckle back to the panel's bottom corner, its tail loose
    for sg in (-1, 1):
        ta, tn = hit(0.355, sg * 0.04, -1); ba, bn = hit(0.035, sg * 0.125, -1)
        back = -XL; T_ = FY + 0.007                                            # a strap lying on the floor: its middle 7 mm up
        ctrl = [ta + tn * 0.008, ta + tn * 0.012 - YL * 0.06 + ZL * sg * 0.02,
                L2W(Vector((-0.035, 0.17, sg * 0.10))), L2W(Vector((-0.05, 0.05, sg * 0.14)))]
        ctrl = [Vector((c.x, max(c.y, T_), c.z)) for c in ctrl]
        floor_pts = [L2W(Vector((-0.06 + 0.10 * u, 0, sg * (0.19 + 0.06 * math.sin(math.pi * u) + 0.02 * u)))) for u in (0.0, 0.45, 0.9)]
        ctrl += [Vector((q.x, T_, q.z)) for q in floor_pts]
        pad = resample(tube_pts(ctrl, 8), 28)
        ups = []
        for k, q in enumerate(pad):                                           # its flat side: against the pack up high, on the floor down low
            fl = smooth01(FY + 0.04, FY + 0.12, q.y)
            ups.append((tn * fl + YL * (1 - fl)).normalized())
        F = polyline_frames(pad, ups)
        o = tube_framed("bag_strap", "bag", pad, [f[1] for f in F], [f[2] for f in F], 0.032, 0.0065, n=8, p=3.2, cap=(True, True),
                        taper=lambda u: (0.75 + 0.25 * smooth01(0.0, 0.15, u) - 0.2 * smooth01(0.75, 1.0, u), 1 - 0.45 * smooth01(0.8, 1.0, u)))
        paint(o, lambda p: srgb("#2f353d"))
        e = pad[-1]; te = F[-1][0]; we = F[-1][1]
        # the buckle at the padded part's end
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); Mx = Matrix((te, we, YL)).transposed()
        for v in bm.verts: v.co = Bv(e + te * 0.014 + Mx @ Vector((v.co.x * 0.018, v.co.y * 0.03, v.co.z * 0.006)))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.002, segments=1, affect='EDGES', clamp_overlap=True)
        new_obj("bag_buckle", bm, "plastic_black")
        # webbing: from the buckle back along the floor to the bottom corner anchor (rising onto the panel there)
        w0 = e + te * 0.03; w1 = Vector((ba.x, T_ - 0.004, ba.z)) + bn * 0.03
        wctrl = [w0, w0.lerp(w1, 0.5) + we * sg * 0.03, w1, ba + bn * 0.004 + YL * 0.004]
        wctrl = [Vector((c.x, max(c.y, FY + 0.0015), c.z)) for c in wctrl]
        web = resample(tube_pts(wctrl, 6), 16); F = polyline_frames(web, [YL] * len(web))
        strip_framed("bag_web", "bag", web, [f[1] for f in F], [f[2] for f in F], 0.025, 0.0018); paint(STATIC[-1], lambda p: srgb("#1b1d20"))
        tail = [w0 + te * 0.01, w0 + te * 0.06 - we * sg * 0.015, w0 + te * 0.10 - we * sg * 0.035]
        tail = [Vector((c.x, FY + 0.0012, c.z)) for c in tail]
        strip_framed("bag_web", "bag", tail, [we] * 3, [YL] * 3, 0.025, 0.0018); paint(STATIC[-1], lambda p: srgb("#1b1d20"))
    parts = [o for o in STATIC[n0:]]
    G["settle"](parts, FY); [project_uv(o) for o in parts]
    return parts


# ================================================================ clothes: jeans dropped by the bed's foot, a T-shirt on the bed
def pants_flat(waist=0.20, hip=0.245, thigh=0.125, hem=0.095, length=1.02, rise=0.27, cell=0.025):
    """a pair of trousers laid flat (front over back, as one sheet) in the xz plane, the waist at z = 0 and the legs
    towards -z: (half) widths of the waist, the hips, a leg at the thigh and at the hem; returns a bmesh"""
    def hw(z): return waist + (hip - waist) * smooth01(0.0, 0.18, -z)
    def lw(z): return thigh + (hem - thigh) * smooth01(rise + 0.03, length, -z)
    def inside(x, z):
        if z > 0 or z < -length: return False
        if -z < rise: return abs(x) < hw(z)
        xc = hip - lw(z) + 0.012 * smooth01(rise, length, -z)                     # the legs part a little below the crotch
        return abs(abs(x) - xc) < lw(z)
    nx, nz_ = int(2 * (hip + 0.03) / cell), int(length / cell)
    bm = bmesh.new(); V = {}
    for j in range(nz_ + 1):
        for i in range(nx + 1): V[(j, i)] = bm.verts.new(Bv(Vector((-(hip + 0.03) + cell * i, 0, -cell * j))))
    for j in range(nz_):
        for i in range(nx):
            c = sum((gl(V[(j + dj, i + di)].co) for dj in (0, 1) for di in (0, 1)), Vector()) / 4
            if inside(c.x, c.z): bm.faces.new([V[(j, i)], V[(j, i + 1)], V[(j + 1, i + 1)], V[(j + 1, i)]]).smooth = True
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    edge = [v for v in bm.verts if v.is_boundary]
    for _ in range(3): bmesh.ops.smooth_vert(bm, verts=edge, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    return bm


def centre_xz(o):
    """move a built mesh so its footprint is centred on the origin (before turning and placing it)"""
    ps = [gl(v.co) for v in o.data.vertices]; c = sum(ps, Vector()) / len(ps)
    o.data.transform(Matrix.Translation(B(-c.x, 0, -c.z))); o.data.update()


def bunch(bm, length, pitch=0.17, squeeze=0.45, lift=0.09, seed=0.0):
    """trousers stepped out of: concertinaed along the legs before the drop (they fall into a heap, not flat)"""
    for v in bm.verts:
        g = gl(v.co); t = -g.z / length
        z = g.z * squeeze + 0.04 * math.sin(2 * math.pi * g.z / pitch + seed)
        y = lift * abs(math.sin(math.pi * g.z / pitch + seed)) + 0.12 * t + 0.03 * nz(g, 4.0, 60 + seed)
        x = g.x * (0.9 + 0.1 * math.cos(2 * math.pi * t)) + 0.03 * math.sin(2 * math.pi * 1.7 * t + seed)
        v.co = Bv(Vector((x, y, z)))


def jeans():
    """a pair of jeans dropped where he stepped out of them, by the bed's foot: a flat jeans pattern (waist, seat, two
    legs) concertinaed and dropped as cloth (self-collision), heavy denim, so it lies in a heap of real folds"""
    FY = G["FY"]; random.seed(44)
    bm = pants_flat(); bunch(bm, 1.02, pitch=0.17, squeeze=0.48, lift=0.10, seed=0.7)
    o = new_obj("jeans", bm, "denim"); centre_xz(o)
    o.data.transform(Matrix.Translation(B(0.47, FY + 0.10, 1.30)) @ Matrix.Rotation(1.75, 4, 'Z')); o.data.update()
    drop_cloth(o, [bpy.data.objects["floor"]], frames=40, mass=0.45, tension=40, bending=4.0, self_col=True, friction=15, floor_y=FY + 0.003)
    smooth_mesh(o, 0.35, 2)
    centre_xz(o); o.data.transform(Matrix.Translation(B(0.44, 0, 1.30))); o.data.update()   # the heap where it fell (the solver lets it slide on the flat floor)
    sheet(o, 0.006, even=False); G["settle"]([o], FY); project_uv(o)
    return [o]


def joggers(colliders):
    """grey joggers left on the floor cushion: the same trouser pattern (elastic waist, tapered legs, ribbed cuffs),
    concertinaed and dropped as cloth onto the cushion and the throw"""
    FY = G["FY"]
    bm = pants_flat(waist=0.19, hip=0.25, thigh=0.13, hem=0.06, length=0.98, cell=0.025)
    for f in bm.faces:                                                             # the ribbed waistband and cuffs
        z = gl(f.calc_center_median()).z; f.material_index = 1 if (z > -0.04 or z < -0.98 + 0.07) else 0
    bunch(bm, 0.98, pitch=0.15, squeeze=0.5, seed=2.1)
    o = new_obj("joggers", bm, "jersey"); centre_xz(o)                               # (cotton jersey, grey melange in the vertex colour: no extra draw call)
    cuff = {pg.index for pg in o.data.polygons if pg.material_index == 1}
    for pg in o.data.polygons: pg.material_index = 0
    ca = o.data.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
    for pg in o.data.polygons:
        for li in pg.loop_indices:
            g = gl(o.data.vertices[o.data.loops[li].vertex_index].co); k = 0.82 if pg.index in cuff else 1.0
            ca.data[li].color = (*(c * k * (1 + 0.08 * nz(g, 30.0, 61)) for c in srgb("#8b8f96")), 1)
    o.data.transform(Matrix.Translation(B(1.30, FY + 0.20, 0.98)) @ Matrix.Rotation(1.2, 4, 'Z')); o.data.update()
    drop_cloth(o, colliders, frames=60, mass=0.3, tension=20, bending=0.6, self_col=True, friction=15, floor_y=FY + 0.003, gap=0.012)
    smooth_mesh(o, 0.35, 2)
    # nothing under what it lies on: a vertex the solver let sink into the throw or the cushion comes back up onto it
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(c, dg) for c in colliders[:2]]
    for v in o.data.vertices:
        g = gl(v.co); top = None
        for tr in trees:
            r = tr.ray_cast(Bv(Vector((g.x, 0.6, g.z))), Bv(Vector((0, -1, 0))))
            if r[0] is not None: top = max(top or 0.0, gl(r[0]).y)
        if top is not None and g.y < top + 0.004: v.co = Bv(Vector((g.x, top + 0.004, g.z)))
    o.data.update(); smooth_mesh(o, 0.2, 1)
    sheet(o, 0.004, even=False); project_uv(o)
    return o



def tee_flat():
    """a flat T-shirt cut from a grid (body, sleeves, a round neck), at the origin in the xz plane (its length along z,
    the neck towards +z), a little crumpled"""
    random.seed(45)
    nx, nzz = 32, 32; hw, hl, sw = 0.22, 0.28, 0.29
    def inside(x, z):
        if x * x + (z - hl) ** 2 < 0.07 ** 2: return False                                  # the neck
        if abs(x) <= hw and -hl <= z <= hl: return True
        return abs(x) <= sw and 0.09 + 0.05 * (abs(x) - hw) / (sw - hw) <= z <= hl - 0.03   # sleeves
    bm = bmesh.new(); V = {}
    for j in range(nzz + 1):
        for i in range(nx + 1):
            V[(j, i)] = bm.verts.new(Bv(Vector((-sw + 2 * sw * i / nx, 0, -hl + 2 * hl * j / nzz))))
    for j in range(nzz):
        for i in range(nx):
            c = sum((gl(V[(j + dj, i + di)].co) for dj in (0, 1) for di in (0, 1)), Vector()) / 4
            if inside(c.x, c.z): bm.faces.new([V[(j, i)], V[(j, i + 1)], V[(j + 1, i + 1)], V[(j + 1, i)]]).smooth = True
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    edge = [v for v in bm.verts if v.is_boundary]
    for _ in range(4): bmesh.ops.smooth_vert(bm, verts=edge, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)   # a smooth outline, not grid steps
    return bm


def unstretch(o, max_edge, rounds=10):
    """after a cloth simulation: a vertex dragged off by a collider (a sleeve snagged on an armrest) leaves an
    over-stretched edge; such a vertex goes back to the mean of the neighbours it is still close to"""
    bm = bmesh.new(); bm.from_mesh(o.data); total = 0
    for _ in range(rounds):
        moves = []
        for v in bm.verts:
            long_ = [e for e in v.link_edges if e.calc_length() > max_edge]
            if not long_: continue
            near = [e.other_vert(v).co for e in v.link_edges if e not in long_]
            if near: moves.append((v, sum(near, Vector()) / len(near)))
        for v, m in moves: v.co = m
        total += len(moves)
        if not moves: break
    bm.to_mesh(o.data); bm.free(); o.data.update()
    if total: print(o.name + ": pulled back", total, "over-stretched vertices")


def drop_cloth(o, colliders, frames=46, mass=0.2, tension=12, bending=0.2, self_col=False, friction=12, floor_y=None, gap=0.006):
    """a cloth simulation of `o` falling onto the colliders, applied; strays put back and nothing under the floor"""
    for c in colliders:
        c.modifiers.new("col", "COLLISION"); c.collision.thickness_outer = 0.004; c.collision.cloth_friction = friction
    cl = o.modifiers.new("cloth", "CLOTH"); s = cl.settings
    s.quality = 8; s.mass = mass; s.tension_stiffness = tension; s.compression_stiffness = tension; s.shear_stiffness = tension / 3; s.bending_stiffness = bending
    s.air_damping = 1.0; cl.collision_settings.distance_min = gap; cl.collision_settings.use_self_collision = self_col
    if self_col: cl.collision_settings.self_distance_min = 0.004; cl.collision_settings.self_friction = 8
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = frames + 10
    for f in range(1, frames): SC.frame_set(f)
    bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.modifier_apply(modifier="cloth")
    assert not any(m.type == 'CLOTH' for m in o.modifiers), o.name + ": the cloth simulation was not applied"
    for c in colliders:
        for m in list(c.modifiers):
            if m.type == 'COLLISION': c.modifiers.remove(m)
    SC.frame_set(1)
    unspike(o, 0.025, rounds=8)
    if floor_y is not None:
        for v in o.data.vertices:                                                  # nothing through the floor (the solver lets a fast corner slip)
            if v.co.z < floor_y: v.co.z = floor_y
    o.data.update()


def tee_on_chair():
    """the T-shirt thrown over the desk chair's backrest (a cloth simulation against the chair): most of it hangs down
    behind, a hand's width over the front of the top edge, a sleeve sliding off to one side. It is joined into the
    chair's own node ("chair"), so it moves with the chair when he pulls it out; its material is "chair_jersey"."""
    CHAIR, CH_M = G["CHAIR"], G["CH_M"]
    bm = tee_flat()
    for v in bm.verts: v.co.z += 0.02 * nz(gl(v.co), 6.0, 17)
    o = new_obj("tee", bm, "jersey", static=False)
    # chair-local: the backrest's top edge at y ~1.16, its rear face at z ~0.30; the tee across it, its neck to the back
    Mt = Matrix.Translation(B(-0.03, 1.16 + 0.07, 0.40)) @ Matrix.Rotation(0.06, 4, 'Z')
    o.data.transform(CH_M @ Mt); o.data.update()
    drop_cloth(o, [CHAIR], frames=50, mass=0.2, tension=12, bending=0.10, friction=35)
    unstretch(o, 0.045)                                                             # (its grid: 1.8 cm)
    smooth_mesh(o, 0.45, 3)
    paint(o, lambda p: srgb("#7d93a6"))
    sheet(o, 0.004)
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    project_uv(o)
    m = MATS["jersey"].copy(); m.name = "chair_jersey"; o.data.materials[0] = m       # (joining carries it into the chair's own frame)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); CHAIR.select_set(True)
    bpy.context.view_layer.objects.active = CHAIR; bpy.ops.object.join()
    return CHAIR


def blanket(cushion_parts):
    """a fleece throw (100 x 125 cm, 4 mm) left where he sat on the floor cushion: a cloth simulation (with self-
    collision) of the throw dropped in loose pleats, so it lies rumpled half on the cushion and half on the floor,
    in real folds"""
    FY = G["FY"]; random.seed(47)
    W, Lb, nu, nv = 1.00, 1.25, 25, 31
    bm = bmesh.new(); V = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = i / nu, j / nv; x = (u - 0.5) * W; z = (v - 0.5) * Lb
            # dropped bunched: pleated along its length, the pleats squeezing it to ~60 %, one end lifted
            zz = z * 0.42 + 0.04 * math.sin(2 * math.pi * 2.6 * v); y = 0.13 * abs(math.sin(math.pi * 2.6 * v)) + 0.22 * v + 0.05 * nz(Vector((x, 0, z)), 3.0, 48)
            xx = x * (0.55 + 0.25 * v) + 0.06 * math.sin(2 * math.pi * 1.3 * u + 2 * v) + 0.05 * math.sin(2 * math.pi * 2.1 * v + 1.0)
            row.append(bm.verts.new(Bv(Vector((xx, y, zz)))))
        V.append(row)
    for j in range(nv):
        for i in range(nu): bm.faces.new([V[j][i], V[j][i + 1], V[j + 1][i + 1], V[j + 1][i]]).smooth = True
    o = new_obj("blanket", bm, "fleece")
    o.data.transform(Matrix.Translation(B(1.33, FY + 0.12, 0.97)) @ Matrix.Rotation(-0.35, 4, 'Z')); o.data.update()
    drop_cloth(o, [cushion_parts[0], bpy.data.objects["floor"]], frames=70, mass=0.3, tension=10, bending=0.5, self_col=True, friction=14, floor_y=FY + 0.0025)
    smooth_mesh(o, 0.25, 1)
    sheet(o, 0.004, even=False); project_uv(o)
    return o


def clothes(cushion_parts):
    """jeans dropped by the bed's foot, the throw and grey joggers on the floor cushion (each registered with the prop
    sweep), and the T-shirt over the desk chair's back (part of the chair's node)"""
    FY = G["FY"]
    G["check"]("jeans", jeans(), ("y", FY))
    bl = blanket(cushion_parts); G["check"]("blanket", [bl], None)
    G["check"]("joggers", [joggers([cushion_parts[0], bl, bpy.data.objects["floor"]])], None)
    tee_on_chair()


# ================================================================ worn canvas sneakers by the door (#98 soft props, second pass)
def sneaker(nm, right=True, seed=0, loose=True):
    """a worn low-top canvas sneaker (a men's 26 cm foot: 27.5 cm long, 9.2 cm wide at the ball), no brand: a
    vulcanised rubber sole with a foxing stripe and a toe cap, the canvas upper with its heel counter, a padded collar
    round the opening (the lining and the insole show inside), the tongue under five crossed laces through dark
    eyelets, loose untied ends (loose), creases across the toe where it flexes, a heel collar a little trodden down,
    dirt on the sole. Built at the origin, heel at z = 0, toe towards +z; returns its parts."""
    random.seed(70 + seed); n0 = len(STATIC)
    L = 0.275; side = 1 if right else -1
    def wid(t):                                                                     # half-width of the outsole
        keys = [(0.0, 0.0), (0.02, 0.022), (0.08, 0.031), (0.22, 0.034), (0.42, 0.032), (0.62, 0.043), (0.74, 0.046), (0.87, 0.041), (0.95, 0.030), (1.0, 0.0)]
        w = 0.0
        for (a, wa), (b, wb) in zip(keys, keys[1:]):
            if t <= b: u = (t - a) / (b - a); u = u * u * (3 - 2 * u); w = wa + (wb - wa) * u; break
        if t < 0.02: w = 0.022 * math.sqrt(max(0.0, t / 0.02))
        if t > 0.95: w = 0.030 * math.sqrt(max(0.0, (1 - t) / 0.05))
        return w
    def top_h(t):                                                                   # the upper's height at its middle
        keys = [(0.0, 0.070), (0.12, 0.072), (0.22, 0.066), (0.46, 0.071), (0.60, 0.064), (0.74, 0.052), (0.88, 0.043), (0.97, 0.032), (1.0, 0.024)]
        for (a, ha), (b, hb) in zip(keys, keys[1:]):
            if t <= b: u = (t - a) / (b - a); u = u * u * (3 - 2 * u); return ha + (hb - ha) * u
        return 0.024
    def opening(t): return 0.026 * math.sqrt(max(0.0, 1 - ((t - 0.25) / 0.20) ** 2))   # the foot's opening (half-width)
    SOLE = 0.022; INS = 0.028
    ts = [0.0, 0.012, 0.03] + [0.03 + 0.47 * k / 18 for k in range(1, 19)] + [0.5 + 0.47 * k / 9 for k in range(1, 10)] + [0.985, 1.0]   # denser round the opening
    rings = []; cols = []
    for t in ts:
        w = max(wid(t), 1e-4); h = top_h(t); cx = side * 0.005 * math.sin(math.pi * t)       # a banana shape: the medial side straighter
        if t < 0.12: h -= 0.008 * (1 - t / 0.12)                                    # the heel collar, trodden down a little
        op = opening(t); sec = []; col = []
        half = [(0.0, 0.0, "sole"), (0.86, 0.0, "sole"), (0.97, 0.002, "sole"), (1.0, 0.0125, "sole"),
                (1.0, 0.0145, "fox"), (1.0, 0.0165, "fox"), (1.0, 0.0185, "sole"), (0.99, SOLE, "sole"), (0.965, SOLE + 0.002, "up")]
        for f in (0.3, 0.6, 0.85):
            half.append((0.965 - 0.17 * f * f, SOLE + 0.002 + f * (h - 0.006 - SOLE), "up"))
        # the top: seven points across each half. Round the opening they follow its edge (an outer point, the padded
        # rim, the inner lip, then down to the insole), so the edge is one clean line along the rings
        if t < 0.46 and op > 0.003:
            xs = [min(op * 1.12, 0.9 * w - 0.001), op * 1.0, op * 0.9, op * 0.62, op * 0.4, op * 0.18, 0.0]
            ys = [h - 0.006, h + 0.003, h - 0.010, INS + 0.002, INS + 0.001, INS, INS]
            tg = ["top", "rim", "in", "in", "in", "in", "in"]
        else:
            xs = [f * 0.8 * w for f in (0.84, 0.70, 0.56, 0.42, 0.28, 0.14, 0.0)]
            ys = [h - 0.006 + 0.006 * (1 - f * f) for f in (0.84, 0.70, 0.56, 0.42, 0.28, 0.14, 0.0)]; tg = ["top"] * 7
        for x_, y_, t_ in zip(xs, ys, tg): half.append((x_ / w, y_, t_))
        # one loop: the bottom's middle -> up the +x side -> over the top -> down the -x side
        loop = half + [(-xf, y, tg_) for (xf, y, tg_) in reversed(half[1:-1])]
        for (xf, y, tag) in loop:
            x = xf * w; yy = y
            if tag == "top" and 0.44 < t < 0.54: yy += 0.008 * math.sin(math.pi * (t - 0.44) / 0.10) * (1 - (x / (0.8 * w)) ** 2)   # the tongue's top edge
            if tag == "top" and 0.47 <= t <= 0.76: yy += 0.004 * (1 - (x / (0.8 * w)) ** 2)   # the tongue
            if tag in ("top", "up") and 0.62 < t < 0.80:                                # creases across the toe where it flexes
                yy -= 0.0022 * max(0.0, math.sin(2 * math.pi * (t - 0.62) / 0.06)) * (1 - abs(xf))
            if t > 0.86 and tag == "up" and y < 0.036: tag = "cap"                     # the rubber toe cap
            sec.append(Vector((cx + x, yy, t * L))); col.append(tag)
        rings.append(sec); cols.append(col)
    bm = bmesh.new(); V = [[bm.verts.new(Bv(p)) for p in r] for r in rings]; n = len(rings[0])
    for k in range(len(V) - 1):
        for i in range(n):
            j = (i + 1) % n; f = bm.faces.new([V[k][i], V[k][j], V[k + 1][j], V[k + 1][i]]); f.smooth = True
            tg = {cols[k][i], cols[k][j], cols[k + 1][j], cols[k + 1][i]}
            f.material_index = 1 if (tg <= {"sole", "fox"} or "cap" in tg and not ("up" in tg or "top" in tg)) else 0
    bm.faces.new(list(reversed(V[0]))).material_index = 1; bm.faces.new(V[-1]).material_index = 1
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-4); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    vol = sum(f.verts[0].co.dot(f.verts[k].co.cross(f.verts[k + 1].co)) for f in bm.faces for k in range(1, len(f.verts) - 1))
    if vol < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])                     # outward, whichever way the rings wound
    o = new_obj(nm, bm, ["jersey", "painted"])
    up_c, ins_c, sole_c, fox_c = srgb("#6d727c"), srgb("#a3998b"), srgb("#d6d0c2"), srgb("#2b2b2c")
    def colour(p):
        y = p.y; t = p.z / L; c = up_c
        if y < SOLE + 0.0005:
            c = fox_c if 0.0135 < y < 0.0175 else tuple(a * (0.78 + 0.22 * smooth01(0.0, 0.012, y)) for a in sole_c)   # dirt low on the sole
        elif t > 0.86 and y < 0.036: c = tuple(a * 0.93 for a in sole_c)
        elif t < 0.47 and opening(t) > 0.004:                                       # the lining and the insole inside, blended in
            k = (1 - smooth01(opening(t) * 0.86, opening(t) * 0.95, abs(p.x))) * smooth01(0.004, 0.012, top_h(t) - y)
            c = tuple(a + (b_ - a) * k for a, b_ in zip(up_c, ins_c))
        elif t > 0.6: c = tuple(a * (1 + 0.35 * smooth01(0.6, 1.0, t) * max(0.0, nz(p, 30.0, 71))) for a in up_c)   # the canvas worn paler at the toe
        return tuple(a * (1 + 0.05 * nz(p, 25.0, 72)) for a in c)
    paint(o, colour)
    lace_c = srgb("#cfcac0")
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [list(pg.vertices) for pg in o.data.polygons])   # (from the mesh itself: the depsgraph lags behind a new object)
    def on_top(x, t, lift):                                                         # the upper's surface above (x, t), lifted along its normal
        r = bvh.ray_cast(Bv(Vector((x, 0.2, t * L))), Bv(Vector((0, -1, 0))))
        if r[0] is None: return Vector((x, top_h(t), t * L))
        n = gl(r[1]).normalized(); n = n if n.y > 0 else -n                       # (outward: up, whichever way the face winds)
        return gl(r[0]) + n * lift
    eye = [0.51 + 0.052 * k for k in range(5)]
    for k, t in enumerate(eye):
        pts = [on_top(-0.019 + 0.038 * u, t + 0.024 * u, 0.0016 + 0.0012 * math.sin(math.pi * u)) for u in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        thin(tube_along("lace", "painted", pts, 0.0024, 0.0012, n=5, ref=Vector((0, 1, 0)))); paint(STATIC[-1], lambda p: lace_c)
        for x in (-0.019, 0.019):                                                   # the eyelets: dark rings in the canvas
            c = on_top(x, t + (0.024 if x > 0 else 0.0), 0.0008)
            thin(tube_along("eyelet", "painted", [c - Vector((0, 0.0004, 0)), c + Vector((0, 0.0006, 0))], 0.0028, 0.0028, n=5, cap=(False, True))); paint(STATIC[-1], lambda p: srgb("#1c1c1e"))
    if loose:
        for sg in (-1, 1):                                                          # the untied ends: back along the top, over the heel, onto the floor
            t0 = eye[0] - 0.012
            ctrl = [on_top(sg * 0.019, t0, 0.002), on_top(sg * (0.45 + 0.1 * sg) * wid(0.38), 0.38, 0.0025), on_top(sg * 0.7 * wid(0.12), 0.12 + 0.03 * sg, 0.0025),
                    Vector((sg * 0.012, 0.045 + 0.01 * sg, -0.004)), Vector((sg * 0.016, 0.0013, -0.016)), Vector((sg * (0.022 + 0.01 * random.random()), 0.0013, -0.024))]
            thin(tube_along("lace", "painted", tube_pts(ctrl, 5), 0.0022, 0.0012, n=5, ref=Vector((0, 1, 0)), cap=(False, True))); paint(STATIC[-1], lambda p: lace_c)
    return [o for o in STATIC[n0:]]


def sneakers():
    """the pair by the door, standing side by side in the strip between the fridge and the door's hinge-side casing
    (the leaf's swing and his way to the door leave 17 cm there): toes to the wall, the left one pulled out 5 cm and
    turned a touch, as they are when kicked off. Each is placed from its measured bounds; they never touch."""
    FY, IZ, wb = G["FY"], G["IZ"], G["world_box"]
    from mathutils.bvhtree import BVHTree
    def put(parts, x_lo=None, x_hi=None, z_lo=None):
        lo, hi = wb(parts); dx = (x_lo - lo[0]) if x_lo is not None else (x_hi - hi[0]); dz = z_lo - lo[2]
        for o in parts: o.data.transform(Matrix.Translation(B(dx, 0, dz))); o.data.update()
    a = sneaker("sneaker", True, 0)
    for o in a: o.data.transform(Matrix.Scale(0.92, 4)); o.data.update(); transform(o, ry=math.pi + 0.02)
    G["settle"](a, FY); put(a, x_lo=G["FX1"] + 0.004, z_lo=IZ + 0.032)
    b = sneaker("sneaker", False, 1, loose=False)
    for o in b: o.data.transform(Matrix.Scale(0.92, 4)); o.data.update(); transform(o, ry=math.pi - 0.03)
    G["settle"](b, FY); put(b, x_hi=G["LX0"] - 0.003, z_lo=IZ + 0.082)
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    ta, tb = BVHTree.FromObject(a[0], dg), BVHTree.FromObject(b[0], dg)
    assert not ta.overlap(tb), "the sneakers run into each other"
    [project_uv(o) for o in a + b]
    return a, b
