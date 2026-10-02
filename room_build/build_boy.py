"""SUB-01's character v2 (#76): a fictional young Japanese man, about 20, built from MakeHuman / MPFB2 CC0 assets.

    blender -b -P build_boy.py                     # -> out/boy2_raw.glb + out/boy2_bind.json (then: node boy_post.mjs)
    blender -b -P build_boy.py -- --preview        # also renders out/boy2_front.png / boy2_side.png (Cycles, slow-ish)

Needs Blender 4.2 with the MPFB 2 extension (extensions.blender.org, v2.0.17) and these CC0 asset packs from
https://static.makehumancommunity.org/assets/assetpacks.html unpacked into MPFB's user data folder (see CREDITS.md):
makehuman_system_assets, skins02, hair01, shirts01, pants01, underwear04, faceunits01. Also `node boy_ref.mjs`
first (out/boy_ref.json: the old rig's rest pose, which the new body is posed into).

What it does:
 1. MPFB human (male, ~20, Asian macro), game-engine rig (fingers), CC0 skin, eyes, brows, lashes, hair, clothes.
 2. The blink: ARKit-style faceunits eyeBlinkLeft/Right, measured on every part (lids and lashes move together) and
    kept as offsets; also the eyes' look up/down/left/right as rotations of their own bones (done in boy_post.mjs).
 3. Poses the body into the old rig's rest pose (limb directions, elbow and knee hinges, palms) and applies it.
 4. Deletes the skin hidden under the clothes, merges parts, bakes one 2048 atlas (opaque: skin, eyes, clothes) and
    one 1024 atlas (alpha-tested: hair, brows, lashes) -> two materials.
 5. Exports the skinned mesh in that bind pose (bones are rebuilt by boy_post.mjs) plus the joints' positions.
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in ARGS
os.makedirs(OUT, exist_ok=True)

from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService
from bl_ext.user_default.mpfb.services.locationservice import LocationService
from bl_ext.user_default.mpfb.services.objectservice import ObjectService

DATA = LocationService.get_user_data()
def asset(*p): return os.path.join(DATA, *p)

# ---------------------------------------------------------------- who he is (a generic MakeHuman average, not a likeness)
AGE = 0.1875 + (20 - 11) / (25 - 11) * 0.3125      # MakeHuman's age slider: 0.1875 = 11 years, 0.5 = 25 years
MACRO = {"gender": 1.0, "age": AGE, "muscle": 0.45, "weight": 0.36, "proportions": 0.55, "height": 0.42,
         "cupsize": 0.5, "firmness": 0.5, "race": {"asian": 1.0, "caucasian": 0.0, "african": 0.0}}
HEIGHT = 1.71                                       # metres, top of the head (the old one: 1.72)
# parts: (mhclo, kind, mhmat or None for the asset's own, colour treatment)
#   tint (r, g, b): texture x colour; grey (r, g, b): texture's luminance x colour (re-dyes a coloured garment);
#   hsv (hue shift, saturation, value)
PARTS = [
    ("eyes/low-poly/low-poly.mhclo", "eyes", "eyes/materials/brown.mhmat", ("hsv", (0.035, 0.72, 0.68))),
    ("eyebrows/eyebrow001/eyebrow001.mhclo", "eyebrows", None, ("tint", (0.22, 0.18, 0.16))),
    ("eyelashes/eyelashes01/eyelashes01.mhclo", "eyelashes", None, None),
    ("hair/short02/short02.mhclo", "hair", None, ("tint", (0.17, 0.14, 0.12))),
    # colours are linear: a navy sweater, charcoal trousers, light grey socks
    ("clothes/toigo_fisherman_sweater/toigo_fisherman_sweater.mhclo", "clothes", None, ("grey", (0.053, 0.075, 0.165))),
    ("clothes/toigo_wool_pants/toigo_wool_pants.mhclo", "clothes", None, ("grey", (0.105, 0.105, 0.115))),
    ("clothes/joepal_crude_low_socks/joepal_crude_low_socks.mhclo", "clothes", None, ("grey", (0.50, 0.50, 0.49))),
]
SKIN = ("skins/young_asian_male/young_asian_male.mhmat", ("tint", (0.98, 0.90, 0.82)))
ALPHA_KINDS = {"hair", "eyebrows", "eyelashes"}


def log(*a): print("[build_boy]", *a, flush=True)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # read_factory_settings disables add-ons: MPFB keeps working as a module, but the extension must be re-enabled
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")


def build_human():
    base = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
                                     feet_on_ground=True, scale=0.1, macro_detail_dict=MACRO)
    base.name = "body"
    rig = HumanService.add_builtin_rig(base, "game_engine", import_weights=True)
    parts = []
    for mhclo, kind, mhmat, col in PARTS:
        o = HumanService.add_mhclo_asset(asset(mhclo), base, asset_type=kind, subdiv_levels=0, material_type="MAKESKIN")
        o["kind"] = kind; o["mhmat"] = asset(mhmat) if mhmat else ""; o["color"] = json.dumps(col)
        o["mhclo"] = mhclo
        parts.append(o)
    base["kind"] = "skin"; base["mhmat"] = asset(SKIN[0]); base["color"] = json.dumps(SKIN[1])
    return base, rig, parts


def read_mhmat(path):
    tex = None
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("diffuseTexture"):
            name = line.split(None, 1)[1].strip()
            for cand in (os.path.join(os.path.dirname(path), name), os.path.join(os.path.dirname(path), "textures", os.path.basename(name))):
                if os.path.isfile(cand): tex = cand
    return tex


def mean_luminance(image):
    """Mean linear luminance of an image's opaque pixels (sRGB-encoded values, decoded here)."""
    import numpy as np
    px = np.empty(len(image.pixels), dtype=np.float32); image.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[::7]
    px = px[px[:, 3] > 0.5]
    lin = np.where(px[:, :3] <= 0.04045, px[:, :3] / 12.92, ((px[:, :3] + 0.055) / 1.055) ** 2.4)
    return float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean())


def source_material(o):
    """A plain material for each part: its CC0 diffuse texture (re-dyed per PARTS), read through the part's own UVs."""
    mhmat = o["mhmat"] or ""
    if not mhmat:            # the asset's own material file sits next to its mhclo
        d = os.path.dirname(asset(o["mhclo"]))
        mhmat = next((os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".mhmat")), "")
    tex = read_mhmat(mhmat)
    col = json.loads(o["color"])
    m = bpy.data.materials.new("src_" + o.name); m.use_nodes = True
    nt = m.node_tree; N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.7
    uv = N.new("ShaderNodeUVMap"); uv.uv_map = o.data.uv_layers[0].name
    img = N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(tex, check_existing=True); img.name = "src"
    L.new(uv.outputs["UV"], img.inputs["Vector"])
    c = img.outputs["Color"]
    if col and col[0] == "hsv":                  # hue shift, saturation, value (the eyes: red-brown to dark brown)
        hs = N.new("ShaderNodeHueSaturation"); h, sa, va = col[1]
        hs.inputs["Hue"].default_value = 0.5 + h; hs.inputs["Saturation"].default_value = sa; hs.inputs["Value"].default_value = va
        L.new(c, hs.inputs["Color"]); c = hs.outputs["Color"]; col = None
    if col:
        mode, rgb = col
        if mode == "grey":
            bw = N.new("ShaderNodeRGBToBW"); L.new(c, bw.inputs["Color"]); c = bw.outputs["Val"]
            # the garment's brightest knit/weave is about 1: keep its relief, centred on the new colour
            ga = N.new("ShaderNodeMath"); ga.operation = "MULTIPLY_ADD"; ga.inputs[1].default_value = 0.7; ga.inputs[2].default_value = 0.5
            L.new(c, ga.inputs[0]); c = ga.outputs[0]
            # outside the garment's islands the texture is transparent black: a hem's UVs that reach there get the mean
            fill = N.new("ShaderNodeMix"); fill.data_type = "FLOAT"; fill.inputs["A"].default_value = 0.5 + 0.7 * mean_luminance(img.image)
            L.new(img.outputs["Alpha"], fill.inputs["Factor"]); L.new(c, fill.inputs["B"]); c = fill.outputs["Result"]
        mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0
        L.new(c, mix.inputs["A"]); mix.inputs["B"].default_value = (*rgb, 1.0); c = mix.outputs["Result"]
    rgb_out = N.new("NodeReroute"); rgb_out.name = "basecolor"; L.new(c, rgb_out.inputs[0])
    L.new(rgb_out.outputs[0], bsdf.inputs["Base Color"])
    a_out = N.new("NodeReroute"); a_out.name = "alpha"
    if o["kind"] in ALPHA_KINDS:
        L.new(img.outputs["Alpha"], a_out.inputs[0]); L.new(a_out.outputs[0], bsdf.inputs["Alpha"])
    o.data.materials.clear(); o.data.materials.append(m)
    return m


def render_preview(name, objs, views=(("front", 0), ("side", 90)), focus=None, scale=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.samples = 24; sc.cycles.device = "CPU"; sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = 520, 900; sc.render.film_transparent = False
    if not sc.world: sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True; sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.58, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    top = max((o.matrix_world @ Vector(b)).z for o in objs for b in o.bound_box)
    for nm, kind, loc, en in (("key", "AREA", (1.5, -2.5, 2.5), 400), ("fill", "AREA", (-2, -2, 1.5), 120)):
        if nm not in bpy.data.objects:
            l = bpy.data.lights.new(nm, kind); l.energy = en; l.size = 2; lo = bpy.data.objects.new(nm, l); sc.collection.objects.link(lo)
            lo.location = loc; lo.rotation_euler = (Vector((0, 0, top * 0.6)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"; cam.data.ortho_scale = scale or top * 1.08; sc.camera = cam
    c = Vector(focus) if focus else Vector((0, 0, top / 2))
    for v, ang in views:
        a = math.radians(ang); cam.location = c + Vector((4 * math.sin(a), -4 * math.cos(a), 0))
        cam.rotation_euler = (math.pi / 2, 0, a)
        sc.render.filepath = os.path.join(OUT, f"{name}_{v}.png"); bpy.ops.render.render(write_still=True)


def positions(o):
    """Vertex positions with shape keys but no modifiers (the masks would drop vertices)."""
    vis = [m.show_viewport for m in o.modifiers]
    for m in o.modifiers: m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    me = o.evaluated_get(dg).to_mesh(); out = [v.co.copy() for v in me.vertices]
    o.evaluated_get(dg).to_mesh_clear()
    for m, v in zip(o.modifiers, vis): m.show_viewport = v
    return out


def measure_blink(base, objs):
    """Close both eyes with the CC0 ARKit faceunits (eyeBlinkLeft/Right), refit lashes/brows/hair to the closed lids,
    and keep each vertex's offset in a "blink" attribute (it survives the masks, the joins and the pose change)."""
    before = {o.name: positions(o) for o in objs}
    keys = []
    for t in ("eyeBlinkLeft", "eyeBlinkRight"):
        path = TargetService.target_full_path(t)
        assert path, f"faceunits01 not installed ({t})"
        TargetService.load_target(base, path, weight=1.0, name=t); keys.append(t)
    HumanService.refit(base)
    after = {o.name: positions(o) for o in objs}
    for o in objs:
        a = o.data.attributes.get("blink") or o.data.attributes.new("blink", "FLOAT_VECTOR", "POINT")
        d = [c - b for b, c in zip(before[o.name], after[o.name])]
        for i, v in enumerate(d): a.data[i].vector = v
        log("blink", o.name, "max offset %.4f m" % max((v.length for v in d), default=0))
    for k in base.data.shape_keys.key_blocks:
        if k.name in keys: k.value = 0.0
    for k in keys: base.shape_key_remove(base.data.shape_keys.key_blocks[k])
    HumanService.refit(base)


# ---------------------------------------------------------------- pose into the old rig's rest pose
MAP = {"pelvis": "Hips", "spine_01": "Spine02", "spine_02": "Spine01", "spine_03": "Spine", "neck_01": "neck", "head": "Head"}
for s_, S_ in (("l", "Left"), ("r", "Right")):
    MAP.update({f"clavicle_{s_}": f"{S_}Shoulder", f"upperarm_{s_}": f"{S_}Arm", f"lowerarm_{s_}": f"{S_}ForeArm",
                f"hand_{s_}": f"{S_}Hand", f"thigh_{s_}": f"{S_}UpLeg", f"calf_{s_}": f"{S_}Leg", f"foot_{s_}": f"{S_}Foot",
                f"ball_{s_}": f"{S_}ToeBase"})
    for f, F in (("thumb", "Thumb"), ("index", "Index"), ("middle", "Middle"), ("ring", "Ring"), ("pinky", "Pinky")):
        for k in (1, 2, 3): MAP[f"{f}_0{k}_{s_}"] = f"{S_}Hand{F}{k}"
MAP["Root"] = "Hips"
MAP.update({"eye_l": "LeftEye", "eye_r": "RightEye"})          # the root bone's few weights go to the hips


def g2b(v): return Vector((v[0], -v[2], v[1]))           # glTF (y up, faces +z) -> Blender (z up, faces -y)
def b2g(v): return [v[0], v[2], -v[1]]


def bone_dir(pb): return (pb.tail - pb.head).normalized()


def rotate_pose(pb, R, pivot=None):
    """Rotate a pose bone (and so its children) by R (3x3, armature space) about its head."""
    h = pb.head.copy() if pivot is None else pivot
    pb.matrix = Matrix.Translation(h) @ R.to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()


def twist_to(pb, axis, have, want):
    """Turn pb about `axis` so that the direction `have` (perpendicular part) lines up with `want`."""
    a = axis.normalized(); h = (have - a * have.dot(a)); w = (want - a * want.dot(a))
    if h.length < 1e-6 or w.length < 1e-6: return 0.0
    h.normalize(); w.normalize(); ang = math.atan2(a.dot(h.cross(w)), h.dot(w))
    rotate_pose(pb, Quaternion(a, ang).to_matrix()); return ang


def hinge_of(pb, front):
    """The bone's flex axis (MPFB rigs bend about local X), signed so that a positive turn moves the child towards
    `front` (forwards for an elbow, backwards for a knee)."""
    x = pb.matrix.to_3x3().col[0].normalized(); d = bone_dir(pb)
    return x if x.cross(d).dot(front) > 0 else -x


def palm_of(base, rig, pb_name):
    """Palm normal of a hand (armature space): the way its fingertips curl, measured on the skin."""
    pb = rig.pose.bones[pb_name]; side = pb_name[-1]
    gis = {base.vertex_groups[n].index for n in [pb_name] + [f"{f}_0{k}_{side}" for f in ("index", "middle", "ring", "pinky") for k in (1, 2, 3)]
           if n in base.vertex_groups}
    masks = [m for m in base.modifiers if m.type == "MASK"]
    for m in masks: m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get(); dg.update(); me = base.evaluated_get(dg).to_mesh()
    d = bone_dir(pb); pts = []
    src = base.data
    # evaluated mesh keeps vertex groups only on the original; use the original indices (no masks applied yet)
    co = [v.co.copy() for v in me.vertices] if len(me.vertices) == len(src.vertices) else None
    base.evaluated_get(dg).to_mesh_clear()
    for m in masks: m.show_viewport = True
    assert co, "palm_of needs the unmasked mesh"
    for v in src.vertices:
        for g in v.groups:
            if g.group in gis and g.weight > 0.5: pts.append(co[v.index]); break
    # as palm.mjs: across the fingers (past the thumb) the thinnest direction is the palm's normal; its sign is the side
    # the fingertips curl to
    e1 = d.orthogonal().normalized(); e2 = d.cross(e1)
    t = [(p - pb.head).dot(d) for p in pts]; tmax = max(t)
    band = [p - pb.head for p, k in zip(pts, t) if 0.62 * tmax < k < 0.8 * tmax]
    uv = [(q.dot(e1), q.dot(e2)) for q in band]; cu = sum(u for u, _ in uv) / len(uv); cv = sum(v for _, v in uv) / len(uv)
    xx = sum((u - cu) ** 2 for u, _ in uv); zz = sum((v - cv) ** 2 for _, v in uv); xz = sum((u - cu) * (v - cv) for u, v in uv)
    a = 0.5 * math.atan2(2 * xz, xx - zz); minor = -math.sin(a) * e1 + math.cos(a) * e2
    tips = [p - pb.head for p, k in zip(pts, t) if k > 0.93 * tmax]; ct = sum(tips, Vector()) / len(tips)
    c = cu * e1 + cv * e2
    return (minor if (ct - c).dot(minor) > 0 else -minor).normalized()


def pose_to_reference(base, rig, ref):
    """Turn MPFB's A-pose into the old rig's rest pose, bone by bone (directions, then elbow/knee hinges and palms)."""
    B = ref["bones"]; P = rig.pose.bones
    rig.data.pose_position = "POSE"
    bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode="POSE")
    want = lambda n: g2b(B[MAP[n]]["y"]).normalized()
    front, back = Vector((0, -1, 0)), Vector((0, 1, 0))
    for s in ("l", "r"):
        for n in (f"clavicle_{s}", f"upperarm_{s}", f"lowerarm_{s}", f"thigh_{s}", f"calf_{s}", f"foot_{s}", f"ball_{s}"):
            rotate_pose(P[n], bone_dir(P[n]).rotation_difference(want(n)).to_matrix())
        # elbow: turn the upper arm about itself until MPFB's elbow hinge is the old one, then re-aim the forearm
        for up, lo, fr in ((f"upperarm_{s}", f"lowerarm_{s}", front), (f"thigh_{s}", f"calf_{s}", back)):
            old = g2b(B[MAP[lo]]["hinge"])
            a = twist_to(P[up], bone_dir(P[up]), hinge_of(P[lo], fr), old)
            rotate_pose(P[lo], bone_dir(P[lo]).rotation_difference(want(lo)).to_matrix())
            log(f"{up}: twisted {math.degrees(a):.0f} deg to the old hinge")
        # hand: aim it, then roll the palm onto the old one (half in the forearm, the rest at the wrist)
        h, lo = P[f"hand_{s}"], P[f"lowerarm_{s}"]
        old_palm = g2b(B[MAP[h.name]]["palm"])
        rotate_pose(h, bone_dir(h).rotation_difference(want(h.name)).to_matrix())
        for share in (0.3, 1.0, 1.0):
            pal = palm_of(base, rig, h.name)
            a = h_ang = None
            if share < 1.0:
                ax = bone_dir(lo); hp = pal - ax * pal.dot(ax); wp = old_palm - ax * old_palm.dot(ax)
                ang = math.atan2(ax.dot(hp.normalized().cross(wp.normalized())), hp.normalized().dot(wp.normalized()))
                rotate_pose(lo, Quaternion(ax, ang * share).to_matrix())
                rotate_pose(h, bone_dir(h).rotation_difference(want(h.name)).to_matrix())
            else:
                ang = twist_to(h, bone_dir(h), pal, old_palm)
            log(f"hand_{s}: palm roll {math.degrees(ang):.0f} deg (share {share})")
    bpy.ops.object.mode_set(mode="OBJECT")


def apply_pose(rig, objs):
    """Bake the pose into the meshes and make it the rig's rest pose (the bind pose of the export)."""
    for o in objs:
        bpy.context.view_layer.objects.active = o
        if o.data.shape_keys:
            o.shape_key_add(name="mix", from_mix=True)
            for k in list(o.data.shape_keys.key_blocks)[:-1]: o.shape_key_remove(k)
            o.shape_key_remove(o.data.shape_keys.key_blocks[0])
        for m in list(o.modifiers):
            if m.type == "MASK": bpy.ops.object.modifier_apply(modifier=m.name)
        for m in list(o.modifiers):
            if m.type == "ARMATURE": bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE"); bpy.ops.pose.select_all(action="SELECT"); bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        m = o.modifiers.new("Armature", "ARMATURE"); m.object = rig


def add_eye_bones(rig, eyes):
    """Two bones for the eyeballs (each eye fully on its own bone), so the eyes can look around."""
    pts = {"l": [], "r": []}
    for v in eyes.data.vertices:
        p = eyes.matrix_world @ v.co; pts["l" if p.x > 0 else "r"].append((v.index, p))
    bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones; inv = rig.matrix_world.inverted()
    for s in ("l", "r"):
        c = sum((p for _, p in pts[s]), Vector()) / len(pts[s])
        # the centre of the ball: its front is the iris; the visible verts are a shell, so their mean sits a bit forward
        b = eb.new(f"eye_{s}"); b.head = inv @ c; b.tail = inv @ (c + Vector((0, -0.02, 0))); b.parent = eb["head"]; b.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    for g in list(eyes.vertex_groups): eyes.vertex_groups.remove(g)
    for s in ("l", "r"):
        g = eyes.vertex_groups.new(name=f"eye_{s}"); g.add([i for i, _ in pts[s]], 1.0, "REPLACE")


# ---------------------------------------------------------------- one mesh, two materials
def smooth_crotch(rig, pants, radius=0.11, iterations=24):
    """Flatten the trousers' crotch (the base mesh's bulge shows through the cloth): Laplacian smoothing that fades out
    over `radius` around the point between the hip joints, a little below them."""
    hl, hr = (rig.matrix_world @ rig.data.bones[n].head_local for n in ("thigh_l", "thigh_r"))
    c = (hl + hr) / 2 + Vector((0, -0.03, -0.07))
    bm = bmesh.new(); bm.from_mesh(pants.data); bm.verts.ensure_lookup_table()
    w = {v.index: max(0.0, 1 - ((pants.matrix_world @ v.co) - c).length / radius) for v in bm.verts}
    for _ in range(iterations):
        new = {}
        for v in bm.verts:
            if w[v.index] <= 0 or not v.link_edges: continue
            avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
            new[v] = v.co + (avg - v.co) * 0.5 * w[v.index]
        for v, co in new.items(): v.co = co
    bm.to_mesh(pants.data); bm.free(); pants.data.update()
    log(f"crotch: {sum(1 for k in w.values() if k > 0)} trouser vertices smoothed")


def delete_hidden_skin(base, covers, reach=0.035, inset=0.002):
    """Delete the skin under the clothes: a face goes when every corner sees cloth within `reach` along its normal
    (hair is alpha-tested, so the scalp stays). Also used for the trousers' waist under the sweater: there the ray
    starts `inset` inside, so the bits that poke through the sweater's hem go as well."""
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for c in covers:
        bm = bmesh.new(); bm.from_object(c, dg); bm.transform(c.matrix_world); trees.append(BVHTree.FromBMesh(bm)); bm.free()
    me = base.data; me.calc_normals_split() if hasattr(me, "calc_normals_split") else None
    hidden = []
    for v in me.vertices:
        p = base.matrix_world @ v.co; n = (base.matrix_world.to_3x3() @ v.normal).normalized()
        hit = any(t.ray_cast(p - n * inset, n, reach + inset)[0] is not None for t in trees)
        hidden.append(hit)
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    dead = [f for f in bm.faces if all(hidden[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me); bm.free(); me.update()
    log(f"hidden skin: {len(dead)} faces deleted")


def delete_enclosed(base, others, above=1.3, reach=0.12, share=0.9):
    """Delete head faces nothing can see: the inside of the mouth and the eye sockets behind the eyeballs (at least
    `share` of the rays from them hit the head or an eye within `reach`; a few may slip out between the lips). Only
    above the shoulders (`above`, metres before scaling)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new(); bm.from_object(base, dg)
    for o in others:
        b2 = bmesh.new(); b2.from_object(o, dg); b2.transform(o.matrix_world)
        tmp = bpy.data.meshes.new("tmp"); b2.to_mesh(tmp); b2.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    tree = BVHTree.FromBMesh(bm); bm.free()
    me = base.data; dirs = []
    for i in range(24):                                   # a fixed spread of directions (golden spiral, unit sphere)
        z = 1 - 2 * (i + 0.5) / 24; r = math.sqrt(1 - z * z); a = i * 2.39996
        dirs.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    enclosed = []
    for v in me.vertices:
        p = base.matrix_world @ v.co
        if p.z < above: enclosed.append(False); continue
        n = v.normal; out = [d for d in dirs if d.dot(n) > 0.05]
        hits = sum(1 for d in out if tree.ray_cast(p + d * 0.0015, d, reach)[0] is not None)
        enclosed.append(bool(out) and hits >= share * len(out))
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    dead = [f for f in bm.faces if all(enclosed[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me); bm.free(); me.update()
    log(f"enclosed (mouth, sockets): {len(dead)} faces deleted")


# triangle budget: these parts are decimated (edge collapse keeps their UVs and weights)
DECIMATE = {"short02": 0.62, "toigo_wool_pants": 0.62}


def decimate(objs):
    for o in objs:
        r = next((v for k, v in DECIMATE.items() if o.name.endswith(k)), None)
        if not r: continue
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new("dec", "DECIMATE"); m.decimate_type = "COLLAPSE"; m.ratio = r; m.use_collapse_triangulate = False
        bpy.ops.object.modifier_move_to_index(modifier="dec", index=0)
        bpy.ops.object.modifier_apply(modifier="dec")


def darken_scalp(base, color=(0.11, 0.085, 0.075), amount=0.85):
    """The skin under the hair gets the hair's colour, so the gaps of the alpha-tested hair do not show a pale scalp."""
    g = base.vertex_groups.get("scalp")
    if not g: return
    src = base.data.materials[0]; m = src.copy(); m.name = "src_scalp"; nt = m.node_tree; N, L = nt.nodes, nt.links
    rr = N["basecolor"]; feed = rr.inputs[0].links[0].from_socket
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MIX"; mix.inputs["Factor"].default_value = amount
    L.new(feed, mix.inputs[6]); mix.inputs[7].default_value = (*color, 1.0); L.new(mix.outputs[2], rr.inputs[0])
    base.data.materials.append(m); slot = len(base.data.materials) - 1
    inside = {v.index for v in base.data.vertices for e in v.groups if e.group == g.index and e.weight > 0.5}
    n = 0
    for p in base.data.polygons:
        if all(v in inside for v in p.vertices): p.material_index = slot; n += 1
    log(f"scalp: {n} faces darkened")


def tris(o): return sum(len(p.vertices) - 2 for p in o.data.polygons)


def join_parts(base, parts):
    """All parts into one mesh; every part's own UVs renamed to UVMap (the source materials read that) + an atlas UV."""
    objs = [base] + parts
    for o in objs:
        uvs = o.data.uv_layers
        while len(uvs) > 1: uvs.remove(uvs[-1])
        uvs[0].name = "UVMap"
        # the atlas UV starts as a copy, scaled per part by how much texture it deserves (the face most)
        a = uvs.new(name="atlas"); w = math.sqrt(TEXEL.get(o["kind"] if o["kind"] != "clothes" else o.name.split(".", 1)[1], 0.3))
        for d in a.data: d.uv = d.uv * w
        for i, p in enumerate(o.data.polygons): pass
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    base.name = "boy2"; return base


# relative texel share in the atlases (UV area scale before packing)
TEXEL = {"skin": 2.6, "eyes": 0.04, "toigo_fisherman_sweater": 0.4, "toigo_wool_pants": 0.3, "joepal_crude_low_socks": 0.05,
         "hair": 1.0, "eyebrows": 0.12, "eyelashes": 0.12}


def pack_atlas(o):
    """Pack the atlas UVs: opaque materials together in one 0..1 square, alpha-tested ones in another."""
    me = o.data; me.uv_layers.active = me.uv_layers["atlas"]
    alpha_slots = {i for i, m in enumerate(me.materials) if m.get("alpha")}
    bpy.context.view_layer.objects.active = o
    for group in (False, True):
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for p in me.polygons: p.select = (p.material_index in alpha_slots) == group
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.scene.tool_settings.use_uv_select_sync = True
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="CARDINAL", scale=True,
                                merge_overlap=False, margin_method="FRACTION", margin=0.006, shape_method="CONCAVE")
        bpy.ops.object.mode_set(mode="OBJECT")


def bake_atlas(o, size_main=2048, size_alpha=1024):
    """Bake every part's (re-dyed) texture into the two atlases; returns (main RGB image, hair RGBA image)."""
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"
    sc.render.bake.margin = 6; sc.render.bake.use_clear = True
    main = bpy.data.images.new("atlas_main", size_main, size_main, alpha=False)
    col = bpy.data.images.new("atlas_hair", size_alpha, size_alpha, alpha=False)
    alp = bpy.data.images.new("atlas_hair_a", size_alpha, size_alpha, alpha=False)
    def setup(which):
        for m in o.data.materials:
            nt = m.node_tree; N, L = nt.nodes, nt.links
            em = N.get("bake_emit") or N.new("ShaderNodeEmission"); em.name = "bake_emit"
            out = N["Material Output"]
            src = N["basecolor"] if which == "color" else N["alpha"]
            for l in list(em.inputs["Color"].links): L.remove(l)
            if src.inputs[0].links: L.new(src.outputs[0], em.inputs["Color"])
            else: em.inputs["Color"].default_value = (1, 1, 1, 1)
            L.new(em.outputs[0], out.inputs["Surface"])
            t = N.get("bake_target") or N.new("ShaderNodeTexImage"); t.name = "bake_target"
            t.image = (alp if which == "alpha" else col) if m.get("alpha") else main
            N.active = t; t.select = True
    for which in ("color", "alpha"):
        setup(which)
        if which == "alpha":     # only the hair image needs the alpha pass: keep the main atlas from being re-baked
            for m in o.data.materials:
                if not m.get("alpha"): m.node_tree.nodes["bake_target"].image = bpy.data.images.get("scratch") or bpy.data.images.new("scratch", 64, 64)
        bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.bake(type="EMIT", uv_layer="atlas", margin=6, use_clear=True)
        log("baked", which)
    for im, nm in ((main, "boy2_main.png"), (col, "boy2_hair_rgb.png"), (alp, "boy2_hair_a.png")):
        im.filepath_raw = os.path.join(OUT, nm); im.file_format = "PNG"; im.save()
    return main, col, alp


def final_materials(o):
    """Replace the source materials by two: skin+clothes (opaque), hair+brows+lashes (alpha test, double sided)."""
    me = o.data
    keep = {"opaque": bpy.data.materials.new("boy2_body"), "alpha": bpy.data.materials.new("boy2_hair")}
    keep["alpha"]["alpha"] = True
    slot_of = [1 if m.get("alpha") else 0 for m in me.materials]
    idx = [slot_of[p.material_index] for p in me.polygons]
    me.materials.clear(); me.materials.append(keep["opaque"]); me.materials.append(keep["alpha"])
    for p, i in zip(me.polygons, idx): p.material_index = i
    return keep


def remove_uv(o, name):
    uv = o.data.uv_layers.get(name)
    if uv: o.data.uv_layers.remove(uv)


def scale_all(rig, objs, height):
    top = max((o.matrix_world @ v.co).z for o in objs if o.get("kind") == "skin" for v in o.data.vertices)
    k = height / top
    for o in [rig] + objs: o.select_set(True)
    rig.scale = (k, k, k)
    bpy.ops.object.select_all(action="DESELECT")
    for o in [rig] + objs: o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    log(f"scaled x{k:.3f} to {height} m")


def blink_shape_key(o):
    a = o.data.attributes["blink"]
    o.shape_key_add(name="Basis", from_mix=False); k = o.shape_key_add(name="blink", from_mix=False)
    for i, v in enumerate(o.data.vertices): k.data[i].co = v.co + a.data[i].vector
    o.data.attributes.remove(a)


def export(o, rig):
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); rig.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "boy2_raw.glb"), use_selection=True, export_format="GLB",
                              export_skins=True, export_morph=True, export_morph_normal=False, export_animations=False,
                              export_materials="PLACEHOLDER", export_texcoords=True, export_normals=True, export_yup=True,
                              export_def_bones=False, export_all_influences=False, export_attributes=False)
    # the joints in glTF axes (metres), for boy_post.mjs: heads, tails and frames of MPFB's bones in the bind pose
    bones = {}
    for b in rig.data.bones:
        m = rig.matrix_world @ b.matrix_local
        bones[b.name] = {"head": b2g(m.translation), "tail": b2g(rig.matrix_world @ b.tail_local),
                         "x": b2g(m.to_3x3().col[0]), "y": b2g(m.to_3x3().col[1]), "z": b2g(m.to_3x3().col[2]),
                         "parent": b.parent.name if b.parent else None, "name": MAP.get(b.name)}
    eyes = {}
    me = o.data; mi = [i for i, m in enumerate(me.materials)]
    json.dump({"bones": bones, "map": MAP}, open(os.path.join(OUT, "boy2_bind.json"), "w"), indent=1)


if __name__ == "__main__":
    clear_scene()
    base, rig, parts = build_human()
    for o in [base] + parts:
        n = sum(len(p.vertices) - 2 for p in o.data.polygons)
        log(o.name, o["kind"], "tris", n, "verts", len(o.data.vertices), "mods", [m.type for m in o.modifiers])
    log("bones", [b.name for b in rig.data.bones][:8], "height", max((rig.matrix_world @ v.co).z for v in base.data.vertices))
    for o in [base] + parts: source_material(o)
    measure_blink(base, [base] + parts)
    ref = json.load(open(os.path.join(OUT, "boy_ref.json")))
    pose_to_reference(base, rig, ref)
    if PREVIEW:
        render_preview("boy2_posed", [base] + parts)
        hl = rig.matrix_world @ rig.pose.bones["hand_l"].tail
        render_preview("boy2_hand", [base] + parts, views=(("front", 0), ("out", 90), ("back", 180)), focus=hl, scale=0.35)
    apply_pose(rig, [base] + parts)
    add_eye_bones(rig, next(p for p in parts if p["kind"] == "eyes"))
    sweater = next(p for p in parts if p.name.endswith("sweater")); pants = next(p for p in parts if p.name.endswith("pants"))
    smooth_crotch(rig, pants)
    delete_hidden_skin(base, [p for p in parts if p["kind"] == "clothes"], inset=0.02)
    delete_hidden_skin(pants, [sweater], reach=0.07, inset=0.03)
    delete_enclosed(base, [p for p in parts if p["kind"] == "eyes"])
    decimate(parts)
    darken_scalp(base)
    for o in [base] + parts:
        for m in o.data.materials: m["alpha"] = o["kind"] in ALPHA_KINDS; m["kind"] = o["kind"]
    log("triangles:", {o.name: tris(o) for o in [base] + parts}, "total", sum(tris(o) for o in [base] + parts))
    scale_all(rig, [base] + parts, HEIGHT)
    boy = join_parts(base, parts)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "boy2_joined.blend"))
    pack_atlas(boy)
    bake_atlas(boy)
    final_materials(boy)
    remove_uv(boy, "UVMap"); boy.data.uv_layers["atlas"].name = "UVMap"
    blink_shape_key(boy)
    log("final triangles", tris(boy), "verts", len(boy.data.vertices))
    export(boy, rig)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "boy2_stage1.blend"))
