# blender -b -P g2_silhouette.py
#
# The owner's silhouette check (COORD A): G2's body standing (room_stand_up's end), front, side and back, in three versions
# of the clothes - the one the owner liked before the loose change (3157f95), the loose one (b13af33) and the new slim
# one (this tree) - each version's MakeHuman clothes (.mhclo) fitted to G2's body by MakeHuman's own rule and skinned the
# same way (four weights from the mix of their three body vertices' default weights), its covered skin hidden; beside
# them a real photo of a slim young man in black joggers (front, the face cropped off) and in a black hoodie (back), both
# CC0; and below, the slim version in the three motion poses (desk, walk, lying) with its corrective shapes on.
# Writes docs/design/clothes-mh/silhouette.jpg.
import bpy, sys, os, subprocess, tempfile, math
import numpy as np
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mh_io as M, g2_pose as GP

MH = "/home/user/mh/mh/makehuman/data"
for i, a in enumerate(sys.argv):
    if a == "--mh": MH = sys.argv[i + 1]
SRC = open(os.path.join(HERE, "build_clothes.py")).read()
ns = {"MH": MH, "M": M}; exec(SRC[SRC.index("def g2_targets():"):SRC.index("REST = M.apply_targets(base, g2_targets())")], ns)
base, BODY_F, _, _ = M.read_obj(f"{MH}/3dobjs/base.obj", groups={"body"})
REST = M.apply_targets(base, ns["g2_targets"]())
BODY_IDS = sorted({i for f in BODY_F for i in f}); GL = {v: k for k, v in enumerate(BODY_IDS)}
Y0 = REST[BODY_IDS, 1].min(); S = 1.75 / (REST[BODY_IDS, 1].max() - Y0)
to_m = lambda p: np.stack([p[:, 0] * S, (p[:, 1] - Y0) * S, p[:, 2] * S], -1)
GARMENTS = ["hoodie_black", "track_trousers", "socks_white", "slides_black"]
COLOR = {"hoodie_black": (0.025, 0.025, 0.028), "track_trousers": (0.02, 0.022, 0.03), "socks_white": (0.8, 0.8, 0.78), "slides_black": (0.015, 0.015, 0.016)}
VERSIONS = [("before", "3157f95"), ("loose", "b13af33"), ("slim", None)]

D = GP.Dressed(); BODY = D.meshes["body"][0]
BW = np.zeros((len(BODY["P"]), len(D.joints)))                       # the body's skin weights, dense
for k in range(4): np.add.at(BW, (np.arange(len(BW)), BODY["J"][:, k]), BODY["W"][:, k])


def garment(version, commit, g):
    """a version's garment fitted to G2's body: a skinnable primitive (metres) and its faces, and its hidden skin"""
    if commit:
        d = tempfile.mkdtemp()
        for ext in ("mhclo", "obj"):
            rel = f"room_build/clothes_mh/assets/{g}/{g}.{ext}"
            open(os.path.join(d, f"{g}.{ext}"), "wb").write(subprocess.check_output(["git", "-C", HERE, "show", f"{commit}:{rel}"]))
    else: d = os.path.join(HERE, "assets", g)
    mc = M.read_mhclo(os.path.join(d, f"{g}.mhclo")); _, F, _, _ = M.read_obj(os.path.join(d, f"{g}.obj"))
    P = to_m(M.fit(mc, REST))
    gl = np.vectorize(GL.get)(mc["ref"])
    w = BW[gl[:, 0]] * mc["w"][:, 0, None] + BW[gl[:, 1]] * mc["w"][:, 1, None] + BW[gl[:, 2]] * mc["w"][:, 2, None]
    top = np.argsort(-w, 1)[:, :4]; tw = np.take_along_axis(w, top, 1); tw /= np.maximum(tw.sum(1, keepdims=True), 1e-9)
    tris = [t for f in F for t in ([f[0], f[1], f[2]] + ([f[0], f[2], f[3]] if len(f) == 4 else []),)]
    tris = np.array([x for f in F for x in ([(f[0], f[1], f[2])] + ([(f[0], f[2], f[3])] if len(f) == 4 else []))])
    return {"P": P, "J": top, "W": tw, "T": {}, "I": tris}, set(mc["delete"])


# ---- the scene
bpy.ops.wm.read_factory_settings(use_empty=True); SC = bpy.context.scene
SC.render.engine = 'CYCLES'; SC.cycles.device = 'CPU'; SC.cycles.samples = 48; SC.cycles.use_denoising = True
SC.view_settings.view_transform = 'AgX'
wd = bpy.data.worlds.new("w"); SC.world = wd; wd.use_nodes = True
wd.node_tree.nodes["Background"].inputs[0].default_value = (0.72, 0.73, 0.75, 1); wd.node_tree.nodes["Background"].inputs[1].default_value = 1.0
ld = bpy.data.lights.new("key", 'AREA'); ld.energy = 600; ld.size = 3; key = bpy.data.objects.new("key", ld); SC.collection.objects.link(key)
key.location = (-2.0, -3.0, 3.5); key.rotation_euler = (Vector((0, 0, 1.0)) - key.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
fl = bpy.context.active_object; fm = bpy.data.materials.new("floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.6, 0.6, 0.62, 1); fl.data.materials.append(fm)


def B(a): return np.c_[a[:, 0], -a[:, 2], a[:, 1]]


def mat(name, rgb, rough=0.75):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    P = m.node_tree.nodes["Principled BSDF"]; P.inputs["Base Color"].default_value = (*rgb, 1); P.inputs["Roughness"].default_value = rough; return m


def mesh(name, P, I, m):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(p) for p in B(P)], [], [tuple(int(x) for x in t) for t in I]); me.update()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); SC.collection.objects.link(o); me.materials.append(m)
    sd = o.modifiers.new("s", "SUBSURF"); sd.levels = sd.render_levels = 1; return o


def clear():
    for o in list(SC.objects):
        if o.type == 'MESH' and o.name != fl.name: bpy.data.objects.remove(o)
    for o in list(SC.objects):
        if o.type == 'CAMERA': bpy.data.objects.remove(o)


def shoot(path, eye, tgt, lens, w=420, h=640):
    cd = bpy.data.cameras.new("c"); cd.lens = lens; co = bpy.data.objects.new("c", cd); SC.collection.objects.link(co)
    co.location = Vector(eye); co.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler(); SC.camera = co
    SC.render.resolution_x, SC.render.resolution_y = w, h; SC.render.filepath = path; bpy.ops.render.render(write_still=True)


OUT = os.path.join(HERE, "out", "silhouette"); os.makedirs(OUT, exist_ok=True)
world = D.world("room_stand_up", -0.01); Ms = D.skin_mats(world); hips = D.pos(world, "Hips")
VIEWS = {"front": np.array([0.0, 0.0, 1.0]), "side": np.array([1.0, 0.0, 0.0]), "back": np.array([0.0, 0.0, -1.0])}
# which way he faces at the end of standing up: from the hips towards the knees, level
k = np.cross(D.pos(world, "LeftArm") - D.pos(world, "RightArm"), D.pos(world, "neck") - hips)   # his front, from the shoulders
facing = np.array([k[0], 0, k[2]]); facing /= np.linalg.norm(facing)
side = np.cross([0, 1, 0], facing)
shots = {}
for name, commit in VERSIONS:
    clear(); hide = set()
    for g in GARMENTS:
        prim, dl = garment(name, commit, g); hide |= dl
        mesh(g, D.skinned(prim, Ms), prim["I"], mat(g, COLOR[g], 0.4 if g == "slides_black" else 0.8))
    keep = np.array([not all(BODY_IDS[i] in hide for i in t) for t in D.full_body_I])
    mesh("body", D.skinned(BODY, Ms), D.full_body_I[keep], mat("skin", (0.62, 0.46, 0.38), 0.5))
    for v, d in VIEWS.items():
        dirw = {"front": facing, "side": side, "back": -facing}[v]
        tgt = hips + np.array([0, -0.05, 0]); eye = tgt + dirw * 3.3 + np.array([0, 0.1, 0])
        f = os.path.join(OUT, f"{name}_{v}.png"); shoot(f, B(eye[None])[0], B(tgt[None])[0], 52); shots[(name, v)] = f
# the slim version in motion, its corrective shapes on
clear()
for clip, t, v in (("desk_type_ik", 3.0, "desk"), ("room_walk", 0.3, "walk"), ("room_bed_lie", 12.0, "lying")):
    clear(); wl = D.world(clip, t); Mm = D.skin_mats(wl); wts = D.weights(wl); h = D.pos(wl, "Hips")
    for g in GARMENTS:
        for k_, p in enumerate(D.meshes[g]): mesh(f"{g}{k_}", D.skinned(p, Mm, wts), p["I"], mat(g, COLOR[g], 0.4 if g == "slides_black" else 0.8))
    mesh("body", D.skinned(BODY, Mm), BODY["I"], mat("skin", (0.62, 0.46, 0.38), 0.5))
    if v == "lying":                                                   # along his body, from the side, a little above
        ax = D.pos(wl, "neck") - h; ax[1] = 0; ax /= np.linalg.norm(ax); sd = np.cross(ax, [0, 1, 0])
        tgt = h + ax * 0.15 + np.array([0, 0.05, 0]); eye = tgt + sd * 3.4 + np.array([0, 1.3, 0])
    else:
        tgt = h + np.array([0, -0.1, 0]); eye = tgt + np.array([1.5, 0.3, 2.4])
    f = os.path.join(OUT, f"motion_{v}.png"); shoot(f, B(eye[None])[0], B(tgt[None])[0], 45); shots[("motion", v)] = f
print("SHOTS", len(shots))
