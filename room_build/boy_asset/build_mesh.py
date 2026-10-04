"""Stage 1 of the boy.glb rebuild (Blender 4.2, headless):  blender -b -P build_mesh.py

Reads work/boy_raw.glb (the shipped boy.glb with meshopt dropped, see README.md) and work/tex_old.png (its 2048 atlas),
and writes work/boy_mesh.glb + work/bake_*.png:
  1. welds the seam-split mesh (35k -> 15.5k vertices), drops the baked custom normals, smooth shading;
  2. pads the old atlas (its thousands of islands sit on black: bilinear filtering pulled black into every seam, the
     "black slivers" by the nose);
  3. labels every face skin / hair / hoodie / pants / socks / slides from the old texture colour, the bone weights
     and the height, with a majority vote over neighbours and small-island cleanup;
  4. subdivides the head skin once (Catmull-Clark, boundary creased so the hood and hair meet it without cracks);
  5. new UVs per region (Smart UV Project + pack) into three atlases: skin 2048, hair 1024, cloth 2048;
  6. bakes the old colour through the old UVs into the new atlases (Cycles, emit, CPU).
The rig is not exported from here: assemble.mjs puts this mesh back into the original file's skin and nodes.
"""
import bpy, bmesh, os, sys, math, time, json
import numpy as np
from mathutils import Vector
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
T0 = time.time()
def log(*a): print("[%5.1fs]" % (time.time() - T0), *a, flush=True)

REGIONS = ["skin", "hair", "hoodie", "pants", "socks", "slides"]     # material slot order: skin first (room.html's handVertices)
ATLAS = {"skin": ("skin", 2048), "hair": ("hair", 1024), "hoodie": ("cloth", 2048), "pants": ("cloth", 2048),
         "socks": ("cloth", 2048), "slides": ("cloth", 2048)}

# ---------------------------------------------------------------- import + weld
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(WORK, "boy_raw.glb"))
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
arm.data.pose_position = "REST"                                   # the imported sit clip must not pose the mesh for the bakes
me = bpy.data.objects["char1"]
for o in list(bpy.data.objects):
    if o not in (arm, me): bpy.data.objects.remove(o)
m = me.data
bm = bmesh.new(); bm.from_mesh(m)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.05)          # units are cm (armature scale 0.01): 0.5 mm
bm.to_mesh(m); bm.free(); m.update()
bpy.context.view_layer.objects.active = me; me.select_set(True)
if m.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode="OBJECT")
for p in m.polygons: p.use_smooth = True
log("welded:", len(m.vertices), "verts", len(m.polygons), "faces")

# ---------------------------------------------------------------- old atlas: coverage + padding
img_old = bpy.data.images.load(os.path.join(WORK, "tex_old.png")); W = H = img_old.size[0]
old = np.array(img_old.pixels[:], dtype=np.float32).reshape(H, W, 4)[:, :, :3]
uv_old = m.uv_layers[0]; uv_old.name = "uv_old"
# coverage: rasterise the old UV triangles (numpy, per-triangle bounding boxes)
cov = np.zeros((H, W), bool)
UV = np.array([l.uv[:] for l in uv_old.data], dtype=np.float64) * [W, H]
for p in m.polygons:
    a, b, c = (UV[i] for i in p.loop_indices)
    x0, x1 = int(max(0, min(a[0], b[0], c[0]) - 1)), int(min(W - 1, max(a[0], b[0], c[0]) + 1))
    y0, y1 = int(max(0, min(a[1], b[1], c[1]) - 1)), int(min(H - 1, max(a[1], b[1], c[1]) + 1))
    if x1 < x0 or y1 < y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if abs(d) < 1e-9: continue
    w0 = ((b[0] - xs) * (c[1] - ys) - (c[0] - xs) * (b[1] - ys)) / d
    w1 = ((c[0] - xs) * (a[1] - ys) - (a[0] - xs) * (c[1] - ys)) / d
    w2 = 1 - w0 - w1
    eps = -0.002
    cov[y0:y1 + 1, x0:x1 + 1] |= (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
log("old atlas coverage %.1f%%" % (100 * cov.mean()))
# padding: fill uncovered texels from covered neighbours, 24 passes (the islands are ~5-40 px wide)
tex = old.copy(); filled = cov.copy()
for it in range(24):
    acc = np.zeros_like(tex); n = np.zeros((H, W), np.float32)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        f = np.roll(np.roll(filled, dy, 0), dx, 1); t = np.roll(np.roll(tex, dy, 0), dx, 1)
        acc += t * f[:, :, None]; n += f
    todo = (~filled) & (n > 0)
    tex[todo] = acc[todo] / n[todo][:, None]; filled |= todo
tex[~filled] = 0.5
img_pad = bpy.data.images.new("tex_pad", W, H, alpha=False); img_pad.colorspace_settings.name = "sRGB"
img_pad.pixels = np.concatenate([tex, np.ones((H, W, 1), np.float32)], 2).ravel()
img_pad.filepath_raw = os.path.join(WORK, "tex_old_padded.png"); img_pad.file_format = "PNG"; img_pad.save()
log("padded atlas saved")

# ---------------------------------------------------------------- per-vertex colour, bone, height
col = np.zeros((len(m.vertices), 3)); cnt = np.zeros(len(m.vertices))
for p in m.polygons:
    for li in p.loop_indices:
        u, v = uv_old.data[li].uv; x = min(W - 1, max(0, int(u * W))); y = min(H - 1, max(0, int(v * H)))
        vi = m.loops[li].vertex_index; col[vi] += tex[y, x]; cnt[vi] += 1          # the padded atlas: a texel on a seam is never black
col /= np.maximum(cnt, 1)[:, None]
co = np.array([v.co[:] for v in m.vertices])
gname = [g.name for g in me.vertex_groups]
wt = {n: np.zeros(len(m.vertices)) for n in gname}
for v in m.vertices:
    for g in v.groups: wt[gname[g.group]][v.index] = g.weight
def W_(*names): return sum(wt[n] for n in names)
r, g, b = col.T; lum = col.mean(1)
skin_c = (r > 0.5) & (r - b > 0.07) & (r >= g)
white_c = (lum > 0.7) & (np.abs(r - b) < 0.1)
dark_c = lum < 0.14
head_w = W_("Head", "head_end", "headfront"); neck_w = wt["neck"]
hand_w = W_("LeftHand", "RightHand"); arm_w = W_("LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftShoulder", "RightShoulder", "Spine", "Spine01", "Spine02")
leg_w = W_("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg"); foot_w = W_("LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"); hips_w = wt["Hips"]
z = co[:, 2]
vlab = np.full(len(m.vertices), "hoodie", dtype=object)
# head: dark = hair, else skin (eyebrows, eyes come back below by island size)
is_head = head_w > 0.5
vlab[is_head] = np.where(dark_c[is_head] | (lum[is_head] < 0.3) & ~skin_c[is_head] & (z[is_head] > 150), "hair", "skin")
# neck: skin unless grey (the hood collar)
is_neck = (neck_w > 0.5)
vlab[is_neck] = np.where(skin_c[is_neck], "skin", "hoodie")
vlab[is_neck & dark_c & (z > 152)] = "hair"
# hands: skin unless grey (cuff)
is_hand = hand_w > 0.5
vlab[is_hand] = np.where(lum[is_hand] < 0.45, "hoodie", "skin")      # the cuff is dark grey (0.2-0.4); everything lighter on the hand is skin (the old atlas's padding is pale)
vlab[(arm_w > 0.5) & skin_c] = "skin"                                # wrist skin weighted to the forearm
# hips: hoodie if grey, pants if dark
is_hips = hips_w > 0.5
vlab[is_hips] = np.where(dark_c[is_hips] | (lum[is_hips] < 0.2), "pants", "hoodie")
vlab[leg_w > 0.5] = "pants"
is_foot = foot_w > 0.5
vlab[is_foot] = np.where(lum[is_foot] > 0.85, "socks", "slides")             # the old atlas is bimodal at the feet (0.1-0.3 slides and cuff, 0.9+ socks); the grey smear on the strap (0.5-0.8) is the slide
vlab[is_foot & (z < 1.2)] = "slides"                                 # the sole
vlab[is_foot & ~white_c & (lum < 0.45) & (z > 9)] = "pants"          # the pants cuff is weighted to the foot
log("vertex labels:", Counter(vlab))

# face labels = majority of the 3 vertices, then neighbour votes, then small islands absorbed
flab = np.array([Counter(vlab[v] for v in p.vertices).most_common(1)[0][0] for p in m.polygons], dtype=object)
# face adjacency through edges
ek = {}
for p in m.polygons:
    for e in p.edge_keys: ek.setdefault(e, []).append(p.index)
adj = [[] for _ in m.polygons]
for fs in ek.values():
    for a in fs:
        for b_ in fs:
            if a != b_: adj[a].append(b_)
for it in range(3):
    new = flab.copy()
    for i in range(len(flab)):
        c = Counter(flab[j] for j in adj[i]); c[flab[i]] += 1
        new[i] = c.most_common(1)[0][0]
    flab = new
def islands(flab):
    seen = np.zeros(len(flab), bool); out = []
    for i in range(len(flab)):
        if seen[i]: continue
        q = deque([i]); seen[i] = True; comp = []
        while q:
            x = q.popleft(); comp.append(x)
            for j in adj[x]:
                if not seen[j] and flab[j] == flab[x]: seen[j] = True; q.append(j)
        out.append(comp)
    return out
for pass_ in range(3):
    changed = 0
    for comp in islands(flab):
        lab = flab[comp[0]]
        limit = {"skin": 60, "hair": 400, "hoodie": 120, "pants": 120, "socks": 60, "slides": 60}[lab]
        if len(comp) >= limit: continue
        c = Counter(flab[j] for i in comp for j in adj[i] if flab[j] != lab)
        if c:
            for i in comp: flab[i] = c.most_common(1)[0][0]
            changed += 1
    if not changed: break
# skin islands that are not the face (the biggest) and sit on the head are hair strands the old atlas painted scalp-pink
skin_isl = sorted([c for c in islands(flab) if flab[c[0]] == "skin"], key=len, reverse=True)
for comp in skin_isl[1:]:
    if np.mean([head_w[v] for i in comp for v in m.polygons[i].vertices]) > 0.5:
        for i in comp: flab[i] = "hair"
# hair strands the votes absorbed into the face (the bangs' roots touch the forehead; the atlas painted them pale): a strand
# is a THIN spike, the face is not. A ray cast inward from a face centroid leaves a spike through its back within 1 cm;
# from the forehead, the nose or the lips it travels into the head. Only dark-ish faces (lum < 0.65: the ears and the
# nose wings stay skin) above the eye line or behind the head (the nape).
from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromPolygons([v.co[:] for v in m.vertices], [tuple(p.vertices) for p in m.polygons])
HB = arm.data.bones["Head"].head_local; HF = arm.data.bones["headfront"].head_local
fwd_h = Vector((HF.x - HB.x, HF.y - HB.y, HF.z - HB.z)); fwd_h.z = 0; fwd_h.normalize(); right_h = fwd_h.cross(Vector((0, 0, 1)))
zmax = float(co[:, 2].max()); flum = np.array([lum[list(p.vertices)].mean() for p in m.polygons])
log("head bone z %.1f, mesh top z %.1f (same space if the top is ~20 cm above)" % (HB.z, zmax))
# zones: the top of the head (above the eye line, zmax - 10) and the nape take every thin face; the band of the eyes
# and the ears (down to zmax - 14) only lateral ones in front of the ears (the sideburns), never the nose (central) nor
# the ears themselves (beside the head centre); pale ones too (the old atlas painted many strands scalp-pink)
thin = 0; thin_pale = 0
for p in m.polygons:
    if flab[p.index] != "skin": continue
    if not (head_w[list(p.vertices)].mean() > 0.3 or neck_w[list(p.vertices)].mean() > 0.3): continue
    c = p.center; d = c - Vector((HB.x, HB.y, c.z)); f = d.dot(fwd_h); lat = abs(d.dot(right_h))
    top = c.z > zmax - 10; mid = zmax - 14 < c.z <= zmax - 10; behind = f < -2.0; side = -2.0 <= f <= 3.0
    if not (top or behind or (mid and lat > 4.0)): continue
    if 2.5 < f < 7.2 and lat > 6.0 and zmax - 19 < c.z < zmax - 11: continue        # the ears themselves (thin rims) stay skin
    n = p.normal
    hit = bvh.ray_cast(c - n * 0.02, -n, 1.0)
    if hit[0] is not None and hit[1].dot(-n) > 0:
        flab[p.index] = "hair"; thin += 1; thin_pale += flum[p.index] >= 0.65
log("thin skin faces on the head relabelled hair:", thin, "of them pale:", int(thin_pale))
for comp in islands(flab):                                                      # specks the ray test left behind
    if flab[comp[0]] == "hair" and len(comp) < 4:
        c = Counter(flab[j] for i in comp for j in adj[i] if flab[j] != "hair")
        if c:
            for i in comp: flab[i] = c.most_common(1)[0][0]
# the feet: one shell (the slide's strap and the pants' cuff are bulges of the sock in Meshy's remesh), so the labels can
# only come from the old paint. The vertex colours above were sampled from the PADDED atlas, which paints the sliver
# islands of the strap and the cuff's hem white from the sock next door. Here every foot face is re-read from the
# covered texels inside its own old UV triangle (no padding): mostly white -> sock, else the cuff above 9 cm, the slide below
foot_f = 0; foot_changed = 0
FOOT_XMID = {side: float(co[(foot_w > 0.5) & (co[:, 0] * sgn > 0), 0].mean()) for side, sgn in (("left", 1), ("right", -1))}
# the pants' cuff is a bulge round the ankle: at each angle round the leg its surface stands > 4.5 mm outside the sock's
# radius below it. Per foot: the ankle's centre from the vertices at 5-8 cm, the sock's radius per angle (16 bins) as a
# running minimum going up, and a face at 7.5-12.5 cm is the cuff when it stands out of that radius.
ANKLE = {}
for side, sgn in (("left", 1), ("right", -1)):
    fv = np.nonzero((foot_w > 0.5) & (co[:, 0] * sgn > 0))[0]
    low = fv[(co[fv, 2] > 5) & (co[fv, 2] < 8)]
    if len(low) < 10: continue
    cx_, cy_ = co[low, 0].mean(), co[low, 1].mean()
    ang = np.arctan2(co[fv, 1] - cy_, co[fv, 0] - cx_); rad = np.hypot(co[fv, 0] - cx_, co[fv, 1] - cy_); zz = co[fv, 2]
    bins = ((ang + np.pi) / (2 * np.pi) * 16).astype(int) % 16
    r_sock = np.full(16, np.inf)
    for b_ in range(16):
        sel = (bins == b_) & (zz > 5) & (zz < 8.5)
        if sel.any(): r_sock[b_] = np.percentile(rad[sel], 30)
    r_sock = np.where(np.isfinite(r_sock), r_sock, np.nanmedian(np.where(np.isfinite(r_sock), r_sock, np.nan)))
    ANKLE[side] = {"cx": float(cx_), "cy": float(cy_), "r_sock": [float(x) for x in r_sock]}
USE_ANKLE_RULE = False
def is_cuff(c_):
    side = "left" if c_[0] > 0 else "right"
    if side not in ANKLE or not (7.5 < c_[2] < 12.5): return False
    A_ = ANKLE[side]; b_ = int(((np.arctan2(c_[1] - A_["cy"], c_[0] - A_["cx"]) + np.pi) / (2 * np.pi) * 16)) % 16
    return np.hypot(c_[0] - A_["cx"], c_[1] - A_["cy"]) > A_["r_sock"][b_] + 0.45
for p in m.polygons:
    vs = list(p.vertices)
    if foot_w[vs].mean() < 0.5 and co[vs, 2].max() > 14: continue
    if co[vs, 2].mean() > 14: continue
    if USE_ANKLE_RULE and is_cuff(co[vs].mean(0)):                                 # (off: the ankle is not round; the sock's own bulges stood out of the 5-8 cm radius)
        if flab[p.index] != "pants": flab[p.index] = "pants"; foot_changed += 1
        continue
    uvs = [uv_old.data[li].uv for li in p.loop_indices]
    if len(uvs) != 3: continue
    whites = 0; covered = 0
    for (a_, b_, c_) in ((0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6), (1 / 3, 1 / 3, 1 / 3), (0.45, 0.45, 0.1), (0.45, 0.1, 0.45), (0.1, 0.45, 0.45), (0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.1, 0.1, 0.8)):
        u = a_ * uvs[0][0] + b_ * uvs[1][0] + c_ * uvs[2][0]; v = a_ * uvs[0][1] + b_ * uvs[1][1] + c_ * uvs[2][1]
        x = min(W - 1, max(0, int(u * W))); y = min(H - 1, max(0, int(v * H)))
        if cov[y, x]: covered += 1; whites += old[y, x].mean() > 0.85
    if covered < 3: continue
    foot_f += 1
    new_lab = "socks" if whites / covered > 0.5 else ("pants" if co[vs, 2].mean() > 11.0 else "slides")
    if new_lab == "socks" and co[vs, 2].mean() > 10.0: new_lab = "pants"       # the hem: a clean line at 10 cm (the one shell has no real edge there)
    cxm = co[vs].mean(0)
    if new_lab == "socks" and cxm[2] < 4.5 and abs(cxm[0] - FOOT_XMID["left" if cxm[0] > 0 else "right"]) > 4.3: new_lab = "slides"   # the strap's ends and the sole's sides, whatever the old paint
    if new_lab != flab[p.index]: flab[p.index] = new_lab; foot_changed += 1
for it in range(2):                                                               # a vote among the foot faces against specks
    new = flab.copy()
    for i, p in enumerate(m.polygons):
        if flab[i] not in ("socks", "slides") : continue
        c = Counter(flab[j] for j in adj[i] if flab[j] in ("socks", "slides", "pants")); c[flab[i]] += 1
        new[i] = c.most_common(1)[0][0]
    flab = new
for comp in islands(flab):                                                      # a few white triangles of old padding at the strap's end: not a sock
    if flab[comp[0]] == "socks" and len(comp) < 40:
        c = Counter(flab[j] for i in comp for j in adj[i] if flab[j] != "socks")
        if c and c.most_common(1)[0][0] == "slides":
            for i in comp: flab[i] = "slides"
            foot_changed += len(comp)
# the strap: the slide faces over the instep (above 2.2 cm, within 4.5 cm of the foot's midline) span a band along the
# foot; a sock face inside that band at strap height IS the strap's surface (the sock under it is not modelled), whatever
# the old paint says: the white bits at the strap's end were these
USE_STRAP_BAND = False                                                          # (off: the slide label runs up the foot's sides to the sock, so the "strap" band spanned the whole foot and took the sock's sides with it)
for side, sgn in (("left", 1), ("right", -1)) if USE_STRAP_BAND else ():
    cs = np.array([co[list(p.vertices)].mean(0) for p in m.polygons])
    strap = [i for i, p in enumerate(m.polygons) if flab[i] == "slides" and cs[i, 0] * sgn > 0 and cs[i, 2] > 3.2 and abs(cs[i, 0] - FOOT_XMID[side]) < 4.5 and foot_w[list(p.vertices)].mean() > 0.3]   # above the sole's sides (~3 cm): the strap alone
    if len(strap) < 10: continue
    y0, y1 = np.percentile(cs[strap, 1], 5), np.percentile(cs[strap, 1], 95)
    n_s = 0
    for i, p in enumerate(m.polygons):
        if flab[i] == "socks" and cs[i, 0] * sgn > 0 and 1.5 < cs[i, 2] < 5.5 and y0 <= cs[i, 1] <= y1 and abs(cs[i, 0] - FOOT_XMID[side]) < 5.0: flab[i] = "slides"; n_s += 1
    log("%s strap band y %.1f..%.1f: %d sock faces inside it relabelled slides" % (side, y0, y1, n_s)); foot_changed += n_s
log("foot faces re-read from their own old texels: %d, relabelled %d" % (foot_f, foot_changed))
log("face labels:", Counter(flab), "islands:", Counter(flab[c[0]] for c in islands(flab)))

# ---------------------------------------------------------------- material slots
m.materials.clear()
for name in REGIONS:
    mat = bpy.data.materials.new("boy_" + name); mat.use_nodes = True; m.materials.append(mat)
for p in m.polygons: p.material_index = REGIONS.index(flab[p.index])


def components(pred):
    """connected components (shared vertices) among the faces that pass pred"""
    faces = [p for p in m.polygons if pred(p)]; vf = {}
    for p in faces:
        for v in p.vertices: vf.setdefault(v, []).append(p.index)
    fset = {p.index: p for p in faces}; seen = set(); comps = []
    for p in faces:
        if p.index in seen: continue
        q = deque([p.index]); seen.add(p.index); c = 0
        while q:
            f = q.popleft(); c += 1
            for v in fset[f].vertices:
                for f2 in vf[v]:
                    if f2 not in seen: seen.add(f2); q.append(f2)
        comps.append(c)
    comps.sort(reverse=True); return comps

def select_faces(pred):
    """select faces in edit mode through bmesh (setting MeshPolygon.select in object mode loses faces at region borders)"""
    sel = [pred(p) for p in m.polygons]
    bpy.ops.object.mode_set(mode="EDIT"); bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bme = bmesh.from_edit_mesh(m); bme.faces.ensure_lookup_table()
    for f in bme.faces: f.select = False
    for v in bme.verts: v.select = False
    for e in bme.edges: e.select = False
    for f in bme.faces:
        if sel[f.index]: f.select = True
    bme.select_flush_mode(); bmesh.update_edit_mesh(m)
    n = sum(1 for f in bme.faces if f.select); assert n == sum(sel), (n, sum(sel))

# ---------------------------------------------------------------- the socks' own sole (#126: the page hides the slides on the bed)
# The mesh is one shell at the feet: the sock has no sole or instep of its own, the slide IS them. room.html therefore
# had to keep the slides' shape in sock-white when he lies on the duvet (two big white ovals). Every slide face is
# copied, labelled sock, and the copy is pushed INTO the foot along its normal (6 mm, tapering to 0 within 1.5 cm of the
# sock border so the two surfaces meet without a step). With the slides on, the copy is inside them, unseen; with the
# slides hidden, the foot is a closed white sock: sole, rim and instep.
SOLE_D, SOLE_TAPER = 0.6, 1.5
bm = bmesh.new(); bm.from_mesh(m)
copy_layer = bm.faces.layers.int.new("sole_copy")                              # (made before any face reference: a new layer invalidates them) survives the separation / subdivision / join below
bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.normal_update()
slide_faces = [bm.faces[i] for i in range(len(m.polygons)) if flab[i] == "slides"]
is_sock_v = np.zeros(len(bm.verts), bool); is_slide_v = np.zeros(len(bm.verts), bool)
for i, p in enumerate(m.polygons):
    if flab[i] == "socks": is_sock_v[list(p.vertices)] = True
    if flab[i] == "slides": is_slide_v[list(p.vertices)] = True
border0 = np.nonzero(is_sock_v & is_slide_v)[0]
dist = np.full(len(bm.verts), np.inf); dist[border0] = 0.0; q = deque(border0.tolist())
while q:                                                                        # edge-length Dijkstra-lite over the slide vertices
    i = q.popleft()
    for e in bm.verts[i].link_edges:
        j = e.other_vert(bm.verts[i]).index
        if not is_slide_v[j]: continue
        d_ = dist[i] + e.calc_length()
        if d_ < dist[j] - 1e-6: dist[j] = d_; q.append(j)
dup = bmesh.ops.duplicate(bm, geom=slide_faces)
n_old_v = len(dist)
for k_, v_ in dup["vert_map"].items():                                         # BMVert pairs; which one is the copy is told by its index (new ones come after the old)
    src, dst = (k_, v_) if k_.index < n_old_v else (v_, k_)
    t = min(1.0, dist[src.index] / SOLE_TAPER) if np.isfinite(dist[src.index]) else 1.0
    dst.co = src.co - src.normal * (SOLE_D * t)
new_faces = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)]
for f_ in new_faces: f_[copy_layer] = 1
n_before = len(m.polygons)
bm.to_mesh(m); bm.free(); m.update()
flab = np.concatenate([flab, np.array(["socks"] * (len(m.polygons) - n_before), dtype=object)])
for p in m.polygons: p.material_index = REGIONS.index(flab[p.index])
# the copies keep the slides' old UVs (black): make_textures.py paints every sock-region texel white, so that is harmless
log("sock sole: %d slide faces copied inward (border vertices %d)" % (len(m.polygons) - n_before, len(border0)))
co = np.array([v.co[:] for v in m.vertices])
wt = {n: np.zeros(len(m.vertices)) for n in gname}
for v in m.vertices:
    for g in v.groups: wt[gname[g.group]][v.index] = g.weight

# ---------------------------------------------------------------- a low-poly copy of the whole welded body: the invisible proxy
# room.html's bed code (bedInit, slidesInit, the debug helpers) takes the LAST skinned mesh as his whole body; with the
# body split into one primitive per material that would be the slides alone, so assemble.mjs appends this proxy (alpha-
# masked, never drawn) to the slides primitive. Decimated: ~3k triangles are enough for "how thick he is around a bone".
bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.duplicate(); proxy = bpy.context.active_object; proxy.name = "proxy"
dec = proxy.modifiers.new("dec", "DECIMATE"); dec.ratio = 0.1; dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier="dec")
proxy.hide_render = True; proxy.hide_viewport = True                 # never part of the bakes (it would shadow the body's AO)
log("proxy:", len(proxy.data.polygons), "faces")
bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me

# ---------------------------------------------------------------- subdivide the smooth regions once: head skin, hands, socks, slides
def face_bone_w(p, w): return all(w[v] > 0.3 for v in p.vertices)
hand_w_v = W_("LeftHand", "RightHand", "LeftForeArm", "RightForeArm")
sole_copy_f = np.array([m.attributes["sole_copy"].data[i].value for i in range(len(m.polygons))]) if "sole_copy" in m.attributes else np.zeros(len(m.polygons), int)
masks = {
    "skin": np.array([flab[p.index] == "skin" for p in m.polygons]),            # head, neck, throat and collarbones, hands
    "socks": np.array([flab[p.index] == "socks" and not sole_copy_f[p.index] for p in m.polygons]),   # the sole copies stay coarse (budget)
    "slides": np.array([flab[p.index] == "slides" for p in m.polygons]),
}
region = np.zeros(len(m.polygons), bool)
for k, v in masks.items(): log(k, "faces", int(v.sum())); region |= v
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
selset = set(int(i) for i in np.nonzero(region)[0])
# boundary edges of the selection are creased, and remembered: after the subdivision the part's border vertices are
# snapped back onto these original edges (Catmull-Clark moves them even when creased, which left hairline cracks
# against the unsubdivided neighbours: the dark line at the collar). The new edge midpoints then lie exactly on the
# neighbours' straight edges, so there is no gap.
border_segs = []
for e in bm.edges:
    fs = [f.index in selset for f in e.link_faces]
    if any(fs) and (not all(fs) or len(e.link_faces) == 1):
        e[crease] = 1.0; border_segs.append((e.verts[0].co.copy(), e.verts[1].co.copy()))
bm.to_mesh(m); bm.free()
A = np.array([[*a_] for a_, b_ in border_segs]); B_ = np.array([[*b_] for a_, b_ in border_segs]); AB = B_ - A; L2 = np.maximum((AB * AB).sum(1), 1e-12)
log("border segments:", len(border_segs))
# split the regions into their own object, subdivide (vertex groups and UVs interpolate), snap the border, join back
select_faces(lambda p: bool(region[p.index])); bpy.ops.mesh.separate(type="SELECTED"); bpy.ops.object.mode_set(mode="OBJECT")
part = [o for o in bpy.data.objects if o.type == "MESH" and o is not me and o.name != "proxy"][0]; part.name = "smooth_regions"
bpy.ops.object.select_all(action="DESELECT"); part.select_set(True); bpy.context.view_layer.objects.active = part
mod = part.modifiers.new("subd", "SUBSURF"); mod.levels = 1; mod.use_creases = True; mod.boundary_smooth = "PRESERVE_CORNERS"; mod.uv_smooth = "PRESERVE_BOUNDARIES"
bpy.ops.object.modifier_apply(modifier="subd")
pm = part.data; bmp = bmesh.new(); bmp.from_mesh(pm); bmp.verts.ensure_lookup_table()
border_v = [v.index for v in bmp.verts if any(len(e.link_faces) == 1 for e in v.link_edges)]
bmp.free()
P = np.array([pm.vertices[i].co[:] for i in border_v]); snapped = 0
for k, i in enumerate(border_v):
    p_ = P[k]; t = np.clip(((p_ - A) * AB).sum(1) / L2, 0, 1); Q = A + AB * t[:, None]; d2 = ((Q - p_) ** 2).sum(1); j = int(np.argmin(d2))
    if d2[j] < 1.0: pm.vertices[i].co = Q[j]; snapped += 1                      # within 1 cm: it is this border
log("regions subdivided:", len(pm.polygons), "faces; border vertices snapped", snapped, "of", len(border_v))
bpy.ops.object.select_all(action="DESELECT"); part.select_set(True); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.join()
bm = bmesh.new(); bm.from_mesh(m); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01); bm.to_mesh(m); bm.free()
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT"); bpy.ops.mesh.remove_doubles(threshold=0.01); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode="OBJECT")
for p in m.polygons: p.use_smooth = True
m.update()
log("after join:", len(m.vertices), "verts", len(m.polygons), "faces", "tris ~", sum(len(p.vertices) - 2 for p in m.polygons))
# the slides' straps and sides grow 1.5 mm outward (the smoothed socks poked through them); the soles stay
slides_slot = REGIONS.index("slides"); sv = set(v for p in m.polygons if p.material_index == slides_slot for v in p.vertices)
for vi in sv:
    v = m.vertices[vi]
    if v.co.z > 1.5: v.co = v.co + v.normal * 0.15
m.update(); log("slides grown outward:", len(sv), "vertices")
# the socks tuck 1.5 mm under the cuff's hem (7-11 cm): the subdivided sock poked through it as white teeth
socks_slot = REGIONS.index("socks"); sock_vv = set(v for p in m.polygons if p.material_index == socks_slot for v in p.vertices); tucked = 0
for vi in sock_vv:
    v = m.vertices[vi]
    if 9.6 < v.co.z < 11.5: v.co = v.co - v.normal * (0.3 * min(1.0, (v.co.z - 9.6) / 0.8)); tucked += 1      # only under the hem (10 cm): lower, the dents showed as creases on the visible sock
m.update(); log("sock vertices tucked under the hem:", tucked)

# ---------------------------------------------------------------- the ears: a sculpted relief on the subdivided ear
# Meshy's ear is a smooth blob. In the ear's own frame (u forward, v up, both -1..1 over the ear's half-size) a height
# field along the outward normal draws the anatomy: the helix rim, the scapha groove inside it, the antihelix ridge,
# the concha bowl, the tragus in front of it, a soft lobe; it fades where the ear joins the head (the front) and past
# the rim. The detail material repeats the same field in the normal map for the fine edges.
skin_slot = REGIONS.index("skin"); co2 = np.array([v.co[:] for v in m.vertices]); zmax2 = float(co2[:, 2].max())
EAR = {"f_c": 4.8, "z_c": zmax2 - 15.3, "hw": 2.0, "hh": 2.7, "lat_min": 6.4, "f_lo": 2.5, "f_hi": 7.2}
rel = co2 - np.array([HB.x, HB.y, 0.0]); f_all = rel @ np.array(fwd_h[:]); lat_all = rel @ np.array(right_h[:])
def ear_height(u, v):
    r = np.hypot(u, v); sm = lambda x, a, b: np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))
    helix = 0.22 * np.exp(-((r - 0.86) / 0.09) ** 2) * (1 - sm(u, 0.3, 0.7)) * (1 - sm(-v, 0.6, 0.9))
    scapha = -0.12 * np.exp(-((r - 0.68) / 0.08) ** 2) * (1 - sm(u, 0.3, 0.7))
    antihelix = 0.16 * np.exp(-((r - 0.50) / 0.08) ** 2) * (1 - sm(u, 0.1, 0.5))
    rc = np.hypot(u - 0.15, v + 0.1) / 0.40; concha = -0.35 * np.maximum(0.0, 1 - rc * rc)
    tragus = 0.18 * np.exp(-(((u - 0.55) / 0.18) ** 2 + ((v + 0.1) / 0.22) ** 2))
    lobe = 0.08 * sm(-v, 0.55, 0.9) * (1 - sm(r, 0.9, 1.05))
    w = (1 - sm(r, 0.95, 1.1)) * (1 - sm(u, 0.6, 0.85))
    return (helix + scapha + antihelix + concha + tragus + lobe) * w * 1.4
sv_skin = set(v for p in m.polygons if p.material_index == skin_slot for v in p.vertices)
def ear_vertices():
    co_ = np.array([v.co[:] for v in m.vertices]); rel_ = co_ - np.array([HB.x, HB.y, 0.0]); f_ = rel_ @ np.array(fwd_h[:]); l_ = rel_ @ np.array(right_h[:])
    sk = set(v for p in m.polygons if p.material_index == skin_slot for v in p.vertices)
    return co_, f_, l_, [i for i in sk if abs(l_[i]) > EAR["lat_min"] and EAR["f_lo"] < f_[i] < EAR["f_hi"] and EAR["z_c"] - 1.3 * EAR["hh"] < co_[i, 2] < EAR["z_c"] + 1.3 * EAR["hh"]]
co2, f_all, lat_all, ear_idx = ear_vertices()
# the ear's triangles are ~3 mm after the one subdivision, the relief's features 2-4 mm: one more cut on the ear alone
ear_set = set(ear_idx)
bm = bmesh.new(); bm.from_mesh(m); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
ear_faces = [f_ for f_ in bm.faces if all(v.index in ear_set for v in f_.verts)]
ear_edges = list({e_ for f_ in ear_faces for e_ in f_.edges})
bmesh.ops.subdivide_edges(bm, edges=ear_edges, cuts=1, use_grid_fill=True)
bm.to_mesh(m); bm.free(); m.update()
log("ear subdivided once more: %d faces, %d edges cut" % (len(ear_faces), len(ear_edges)))
co2, f_all, lat_all, ear_idx = ear_vertices()
moved = 0
for i in ear_idx:
    u = (f_all[i] - EAR["f_c"]) / EAR["hw"]; v = (co2[i, 2] - EAR["z_c"]) / EAR["hh"]
    h = float(ear_height(np.array(u), np.array(v)))
    if abs(h) > 1e-4: m.vertices[i].co = m.vertices[i].co + right_h * (np.sign(lat_all[i]) * h); moved += 1
m.update(); log("ear relief: %d ear vertices, %d moved" % (len(ear_idx), moved))
# hair shards that overlap the ear (their jagged edges cut across its top): clamped to the ear's base plane, behind it
hair_slot = REGIONS.index("hair"); co2 = np.array([v.co[:] for v in m.vertices])
rel_h = co2 - np.array([HB.x, HB.y, 0.0]); f_h = rel_h @ np.array(fwd_h[:]); l_h = rel_h @ np.array(right_h[:])
hv_set = set(v for p in m.polygons if p.material_index == hair_slot for v in p.vertices); tucked_h = 0
for i in hv_set:
    if EAR["f_lo"] - 0.3 < f_h[i] < EAR["f_hi"] and EAR["z_c"] - 1.3 * EAR["hh"] < co2[i, 2] < EAR["z_c"] + 1.6 * EAR["hh"] and abs(l_h[i]) > EAR["lat_min"] - 0.6:
        excess = abs(l_h[i]) - (EAR["lat_min"] - 0.6); m.vertices[i].co = m.vertices[i].co - right_h * (np.sign(l_h[i]) * excess); tucked_h += 1
m.update(); log("hair vertices tucked behind the ears:", tucked_h)
EAR.update({"fwd": list(fwd_h[:]), "right": list(right_h[:]), "head": [HB.x, HB.y, 0.0]})
json.dump(EAR, open(os.path.join(WORK, "ears.json"), "w"))
# buffers for make_textures.py: the hair's vertices (the hairline's baby hairs), the socks' own vertices (not the sole
# copies: the strap edge), the feet's extents (toe and heel seams)
hair_slot = REGIONS.index("hair"); co2 = np.array([v.co[:] for v in m.vertices])
np.save(os.path.join(WORK, "hair_verts.npy"), co2[sorted(set(v for p in m.polygons if p.material_index == hair_slot for v in p.vertices))].astype(np.float32))
sole_copy_f2 = np.array([m.attributes["sole_copy"].data[i].value for i in range(len(m.polygons))]) if "sole_copy" in m.attributes else np.zeros(len(m.polygons), int)
socks_slot = REGIONS.index("socks")
sock_v = sorted(set(v for p in m.polygons if p.material_index == socks_slot and not sole_copy_f2[p.index] for v in p.vertices))
np.save(os.path.join(WORK, "socks_verts.npy"), co2[sock_v].astype(np.float32))
FEET = {}
for side, sgn in (("left", 1), ("right", -1)):
    fv = [i for i in sock_v if co2[i, 0] * sgn > 0] + [v for p in m.polygons if p.material_index == REGIONS.index("slides") for v in p.vertices if co2[v, 0] * sgn > 0]
    P_ = co2[fv]; FEET[side] = {"y_toe": float(P_[:, 1].min()), "y_heel": float(P_[:, 1].max()), "x_mid": float(P_[:, 0].mean()), "x_lo": float(P_[:, 0].min()), "x_hi": float(P_[:, 0].max())}
FEET["ankle"] = ANKLE
json.dump(FEET, open(os.path.join(WORK, "feet.json"), "w")); log("feet:", FEET)

# ---------------------------------------------------------------- hand frames for the finger grooves (a second UV map carries them)
# per hand: PCA of its vertices gives the axis along the fingers (longest), across the palm, and the thickness; the
# "hand_uv" map stores (across, along) in cm for hand vertices, (-50, -50) elsewhere, and the skin material draws four
# finger grooves from it (the hands are closed mitten shapes: the grooves make them read as fingers)
gi = {g.name: g.index for g in me.vertex_groups}
hw = {side: np.zeros(len(m.vertices)) for side in ("Left", "Right")}
fw = {side: np.zeros(len(m.vertices)) for side in ("Left", "Right")}
for v in m.vertices:
    for g in v.groups:
        for side in ("Left", "Right"):
            if g.group == gi[side + "Hand"]: hw[side][v.index] += g.weight
            if g.group == gi[side + "ForeArm"]: fw[side][v.index] += g.weight
co2 = np.array([v.co[:] for v in m.vertices])
hand_uv = m.uv_layers.new(name="hand_uv", do_init=False)
huv = np.full((len(m.vertices), 2), -50.0)
for side in ("Left", "Right"):
    idx = np.nonzero((hw[side] > 0.5) & (co2[:, 2] < 110))[0]
    if len(idx) < 20: continue
    P = co2[idx]; c = P.mean(0); U, S_, Vt = np.linalg.svd(P - c, full_matrices=False)
    along, across = Vt[0], Vt[1]
    wrist = co2[np.nonzero(fw[side] > 0.6)[0]].mean(0)                     # the forearm end: the fingers point away from it
    if np.dot(c - wrist, along) < 0: along = -along
    t = (P - c) @ along; tip = t.max()
    log(side, "hand: %d verts, length %.1f cm, width %.1f cm" % (len(idx), t.max() - t.min(), ((P - c) @ across).max() - ((P - c) @ across).min()))
    huv[idx, 0] = (P - c) @ across; huv[idx, 1] = t - tip                 # along: 0 at the fingertips, negative towards the wrist
for p in m.polygons:
    for li in p.loop_indices: hand_uv.data[li].uv = huv[m.loops[li].vertex_index]

# ---------------------------------------------------------------- new UVs per atlas
uv_new = m.uv_layers.new(name="uv_new", do_init=False); m.uv_layers.active = uv_new
uv_new.active_render = True
head_w = np.zeros(len(m.vertices)); neck_w = np.zeros(len(m.vertices))      # (recomputed: the join renumbered the vertices)
gi = {g.name: g.index for g in me.vertex_groups}
for v in m.vertices:
    for g in v.groups:
        if g.group in (gi["Head"], gi["head_end"], gi["headfront"]): head_w[v.index] += g.weight
        if g.group == gi["neck"]: neck_w[v.index] += g.weight
def uv_islands(pred):
    """count UV islands among the faces that pass pred (UV-connected = same vertex and same uv)"""
    par = {}
    def find(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    for p in m.polygons:
        if not pred(p): continue
        keys = [(m.loops[li].vertex_index, round(uv_new.data[li].uv[0], 5), round(uv_new.data[li].uv[1], 5)) for li in p.loop_indices]
        for k in keys[1:]: par[find(keys[0])] = find(k)
    return len(set(find(k) for k in list(par)))
is_head_face = lambda p: all(head_w[v] > 0.3 or neck_w[v] > 0.3 for v in p.vertices)
log("head skin components after join:", components(lambda p: p.material_index == 0 and is_head_face(p))[:8], "seams", sum(e.use_seam for e in m.edges))
for atlas in ("skin", "hair", "cloth"):
    slots = [i for i, n in enumerate(REGIONS) if ATLAS[n][0] == atlas]
    in_atlas = lambda p, slots=slots: p.material_index in slots
    if atlas == "skin":
        # the head skin (face, ears, neck: an open surface bounded by the hair and the collar) unwraps as one island
        select_faces(lambda p: in_atlas(p) and is_head_face(p))
        bpy.ops.uv.select_all(action="SELECT"); bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.002)
        select_faces(lambda p: in_atlas(p) and not is_head_face(p))
        bpy.ops.uv.smart_project(angle_limit=math.radians(70), island_margin=0.004, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        print("  head island(s):", uv_islands(lambda p: in_atlas(p) and is_head_face(p)))
        uvl = m.uv_layers["uv_new"]                                        # (a fresh reference: the mode toggles above make the old one stale, and writes to it are lost)
        for p in m.polygons:                                                 # the face gets most of the skin atlas
            if is_head_face(p) and in_atlas(p):
                for li in p.loop_indices: uvl.data[li].uv = uvl.data[li].uv * 2.0
        m.update()
    else:
        select_faces(in_atlas)
        bpy.ops.uv.smart_project(angle_limit=math.radians(70), island_margin=0.004, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    select_faces(in_atlas)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004, margin_method="FRACTION", shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    if atlas == "cloth":                                                 # a margin all round (the pack puts islands right at the edge; filtering wraps)
        uvl = m.uv_layers["uv_new"]
        for p in m.polygons:
            if in_atlas(p):
                for li in p.loop_indices: uvl.data[li].uv = uvl.data[li].uv * 0.98 + Vector((0.01, 0.01))
        m.update()
    log("uv:", atlas, "faces", sum(1 for p in m.polygons if in_atlas(p)), "islands", uv_islands(in_atlas))

# ---------------------------------------------------------------- bake the old colour into the new atlases
scene = bpy.context.scene; scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 1
scene.render.bake.use_selected_to_active = False; scene.render.bake.margin = 12; scene.render.bake.margin_type = "EXTEND"
bake_imgs = {}
for atlas, size in {"skin": 2048, "hair": 1024, "cloth": 2048}.items():
    im = bpy.data.images.new("bake_" + atlas, size, size, alpha=False); im.colorspace_settings.name = "sRGB"; bake_imgs[atlas] = im
for i, name in enumerate(REGIONS):
    mat = m.materials[i]; nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tex_n = nt.nodes.new("ShaderNodeTexImage"); tex_n.image = img_pad; tex_n.interpolation = "Linear"
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "uv_old"
    nt.links.new(uvn.outputs[0], tex_n.inputs[0]); nt.links.new(tex_n.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    target = nt.nodes.new("ShaderNodeTexImage"); target.image = bake_imgs[ATLAS[name][0]]; nt.nodes.active = target
bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.bake(type="EMIT", use_clear=True, margin=12)
for atlas, im in bake_imgs.items():
    im.filepath_raw = os.path.join(WORK, "bake_%s.png" % atlas); im.file_format = "PNG"; im.save()
log("baked")

# ---------------------------------------------------------------- position / normal buffers of the skin atlas (for the eyes)
# object-space position and normal per texel of the skin atlas: make_textures.py finds the eyes in texture space
def bake_to(atlas_imgs, bake_type, **kw):
    for i, name in enumerate(REGIONS):
        nt = m.materials[i].node_tree
        target = nt.nodes.get("target") or nt.nodes.new("ShaderNodeTexImage"); target.name = "target"
        target.image = atlas_imgs[ATLAS[name][0]]; nt.nodes.active = target
    bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
    bpy.ops.object.bake(type=bake_type, use_clear=True, **kw)
def new_imgs(prefix, sizes, float_=False, colorspace="Non-Color"):
    out = {}
    for atlas, size in sizes.items():
        im = bpy.data.images.new(prefix + atlas, size, size, alpha=False, float_buffer=float_); im.colorspace_settings.name = colorspace; out[atlas] = im
    return out
def save_imgs(imgs, prefix):
    for atlas, im in imgs.items():
        im.filepath_raw = os.path.join(WORK, "%s%s.png" % (prefix, atlas)); im.file_format = "PNG"; im.save()
SIZES = {"skin": 2048, "hair": 1024, "cloth": 2048}
pos_imgs = new_imgs("pos_", {"skin": 2048, "hair": 8, "cloth": 1024}, float_=True)   # the skin atlas (full) and the cloth atlas's height (feet) are read
def emit_geometry(which):
    """every material emits its object-space position (cm, scaled into 0..1) or normal, baked with EMIT"""
    for i, name in enumerate(REGIONS):
        nt = m.materials[i].node_tree; nt.nodes.clear()
        tc = nt.nodes.new("ShaderNodeTexCoord"); em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
        vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
        if which == "pos": nt.links.new(tc.outputs["Object"], vm.inputs[0]); vm.inputs[1].default_value = (1 / 400, 1 / 400, 1 / 400); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        else: nt.links.new(tc.outputs["Normal"], vm.inputs[0]); vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(vm.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
        nt.nodes.new("ShaderNodeTexImage").name = "target"
def emit_region():
    """every material emits its region index / 8 (R), for make_textures.py's per-region grading of the cloth atlas"""
    for i, name in enumerate(REGIONS):
        nt = m.materials[i].node_tree; nt.nodes.clear()
        em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial"); em.inputs[0].default_value = ((i + 1) / 8, (i + 1) / 8, (i + 1) / 8, 1)
        nt.links.new(em.outputs[0], out.inputs[0]); nt.nodes.new("ShaderNodeTexImage").name = "target"
reg_imgs = new_imgs("region_", {"skin": 8, "hair": 8, "cloth": 1024}, float_=True)
emit_region(); bake_to(reg_imgs, "EMIT", margin=0)
np.save(os.path.join(WORK, "region_cloth.npy"), np.round(np.array(reg_imgs["cloth"].pixels[:], dtype=np.float32).reshape(1024, 1024, 4)[:, :, 0] * 8).astype(np.uint8))
emit_geometry("pos"); bake_to(pos_imgs, "EMIT", margin=4)
np.save(os.path.join(WORK, "pos_skin.npy"), (np.array(pos_imgs["skin"].pixels[:], dtype=np.float32).reshape(2048, 2048, 4)[:, :, :3] - 0.5) * 400)
np.save(os.path.join(WORK, "pos_cloth.npy"), (np.array(pos_imgs["cloth"].pixels[:], dtype=np.float32).reshape(1024, 1024, 4)[:, :, :3] - 0.5) * 400)   # position per cloth texel (cm): make_textures.py draws the socks' edge, seams and the slides' tread from it
emit_geometry("nrm"); bake_to(pos_imgs, "EMIT", margin=4)
np.save(os.path.join(WORK, "nrm_skin.npy"), np.array(pos_imgs["skin"].pixels[:], dtype=np.float32).reshape(2048, 2048, 4)[:, :, :3] * 2 - 1)
log("position / normal buffers saved")

# ---------------------------------------------------------------- detail: procedural bump -> tangent normal maps, roughness, AO
# object-space procedural textures (units: cm) so that the fabric detail runs seamlessly across the UV islands
CROWN = (0.0, -2.0, 172.0)   # top of the head (Blender z up)
def links(nt): return nt.links
def node(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        if k == "inputs":
            for ik, iv in v.items(): n.inputs[ik].default_value = iv
        else: setattr(n, k, v)
    return n
def tex_coords(nt):
    tc = node(nt, "ShaderNodeTexCoord"); return tc.outputs["Object"]
def noise(nt, vec, scale, detail=2.0, roughness=0.5, distortion=0.0):
    n = node(nt, "ShaderNodeTexNoise", inputs={"Scale": scale, "Detail": detail, "Roughness": roughness, "Distortion": distortion}); links(nt).new(vec, n.inputs["Vector"]); return n.outputs["Fac"]
def voronoi(nt, vec, scale, feature="F1", randomness=1.0):
    n = node(nt, "ShaderNodeTexVoronoi", feature=feature, inputs={"Scale": scale, "Randomness": randomness}); links(nt).new(vec, n.inputs["Vector"]); return n.outputs["Distance"]
def wave(nt, vec, scale, direction="X", distortion=0.0, detail=0.0, profile="SIN"):
    n = node(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction=direction, wave_profile=profile, inputs={"Scale": scale, "Distortion": distortion, "Detail": detail}); links(nt).new(vec, n.inputs["Vector"]); return n.outputs["Fac"]
def math(nt, op, a, b=None, c=None):
    n = node(nt, "ShaderNodeMath", operation=op)
    for i, x in enumerate((a, b, c)):
        if x is None: continue
        if hasattr(x, "is_linked"): links(nt).new(x, n.inputs[i])
        else: n.inputs[i].default_value = x
    return n.outputs[0]
def mix(nt, a, b, fac):
    n = node(nt, "ShaderNodeMixRGB", blend_type="MIX")
    for i, x in ((1, a), (2, b), (0, fac)):
        if hasattr(x, "is_linked"): links(nt).new(x, n.inputs[i])
        else: n.inputs[i].default_value = x if i == 0 else (x, x, x, 1)
    return n.outputs[0]
def vmath(nt, op, a, b=None, scale=None):
    n = node(nt, "ShaderNodeVectorMath", operation=op)
    for i, x in enumerate((a, b)):
        if x is None: continue
        if hasattr(x, "is_linked"): links(nt).new(x, n.inputs[i])
        else: n.inputs[i].default_value = x
    if scale is not None: n.inputs["Scale"].default_value = scale
    return n.outputs[0]
def separate(nt, vec):
    n = node(nt, "ShaderNodeSeparateXYZ"); links(nt).new(vec, n.inputs[0]); return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]
# the room page multiplies every material's roughness by 0.78: maps are written as wanted / 0.78
R = lambda v: min(1.0, v / 0.78)

def detail_material(name, nt):
    """height (0..1) and roughness sockets + bump strength/distance for a region"""
    nt.nodes.clear(); P = tex_coords(nt)
    if name == "skin":
        pores = voronoi(nt, P, 6.0, "F1")                                   # ~1.7 mm cells (they must survive the 1024 map)
        fine = noise(nt, P, 30.0, 3.0, 0.6)                                   # ~0.3 mm grain
        broad = noise(nt, P, 0.5, 2.0, 0.5)                                   # ~2 cm unevenness
        h = math(nt, "ADD", math(nt, "MULTIPLY", pores, 0.5), math(nt, "ADD", math(nt, "MULTIPLY", fine, 0.2), math(nt, "MULTIPLY", broad, 0.5)))
        # finger grooves on the hands: four fingers over ~7.4 cm, grooves 1.85 cm apart, from the knuckles (6.5 cm behind the tips)
        uvn = node(nt, "ShaderNodeUVMap", uv_map="hand_uv"); hx, hy, _ = separate(nt, uvn.outputs[0])
        fr = math(nt, "FRACT", math(nt, "DIVIDE", math(nt, "ADD", hx, 50.925), 1.85))          # 0..1 across each finger
        d = math(nt, "DIVIDE", math(nt, "SUBTRACT", fr, 0.5), 0.14)
        groove = math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "MULTIPLY", d, d), -1.0))
        onhand = math(nt, "GREATER_THAN", hy, -40.0)
        fingers = math(nt, "MULTIPLY", onhand, math(nt, "MINIMUM", 1.0, math(nt, "MAXIMUM", 0.0, math(nt, "DIVIDE", math(nt, "ADD", hy, 6.5), 1.5))))
        nearmid = math(nt, "LESS_THAN", math(nt, "ABSOLUTE", hx), 3.9)                               # only the four fingers, not the thumb side
        h = math(nt, "SUBTRACT", h, math(nt, "MULTIPLY", math(nt, "MULTIPLY", groove, fingers), math(nt, "MULTIPLY", nearmid, 6.0)))
        # the ears' relief again, for the fine edges (same field as the geometry above, in height units: 0.006 cm each)
        relp = vmath(nt, "SUBTRACT", P, tuple(EAR["head"])); fe = vmath(nt, "DOT_PRODUCT", relp, tuple(EAR["fwd"])); le = vmath(nt, "DOT_PRODUCT", relp, tuple(EAR["right"]))
        _, _, ze = separate(nt, P)
        ue = math(nt, "DIVIDE", math(nt, "SUBTRACT", fe, EAR["f_c"]), EAR["hw"]); ve = math(nt, "DIVIDE", math(nt, "SUBTRACT", ze, EAR["z_c"]), EAR["hh"])
        re_ = math(nt, "SQRT", math(nt, "ADD", math(nt, "MULTIPLY", ue, ue), math(nt, "MULTIPLY", ve, ve)))
        def gauss(x, c, w): d_ = math(nt, "DIVIDE", math(nt, "SUBTRACT", x, c), w); return math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "MULTIPLY", d_, d_), -1.0))
        def smst(x, a_, b_): t_ = math(nt, "MINIMUM", 1.0, math(nt, "MAXIMUM", 0.0, math(nt, "DIVIDE", math(nt, "SUBTRACT", x, a_), b_ - a_))); return math(nt, "MULTIPLY", math(nt, "MULTIPLY", t_, t_), math(nt, "SUBTRACT", 3.0, math(nt, "MULTIPLY", t_, 2.0)))
        back = math(nt, "SUBTRACT", 1.0, smst(ue, 0.3, 0.7))
        helix = math(nt, "MULTIPLY", math(nt, "MULTIPLY", gauss(re_, 0.86, 0.09), 0.22), back)
        scapha = math(nt, "MULTIPLY", math(nt, "MULTIPLY", gauss(re_, 0.68, 0.08), -0.12), back)
        antihelix = math(nt, "MULTIPLY", math(nt, "MULTIPLY", gauss(re_, 0.50, 0.08), 0.16), math(nt, "SUBTRACT", 1.0, smst(ue, 0.1, 0.5)))
        ucx = math(nt, "DIVIDE", math(nt, "SUBTRACT", ue, 0.15), 0.40); vcx = math(nt, "DIVIDE", math(nt, "ADD", ve, 0.1), 0.40)
        concha = math(nt, "MULTIPLY", math(nt, "MAXIMUM", 0.0, math(nt, "SUBTRACT", 1.0, math(nt, "ADD", math(nt, "MULTIPLY", ucx, ucx), math(nt, "MULTIPLY", vcx, vcx)))), -0.35)
        tux = math(nt, "DIVIDE", math(nt, "SUBTRACT", ue, 0.55), 0.18); tvx = math(nt, "DIVIDE", math(nt, "ADD", ve, 0.1), 0.22)
        tragus = math(nt, "MULTIPLY", math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "ADD", math(nt, "MULTIPLY", tux, tux), math(nt, "MULTIPLY", tvx, tvx)), -1.0)), 0.18)
        win = math(nt, "MULTIPLY", math(nt, "SUBTRACT", 1.0, smst(re_, 0.95, 1.1)), math(nt, "SUBTRACT", 1.0, smst(ue, 0.6, 0.85)))
        on_ear = math(nt, "GREATER_THAN", math(nt, "ABSOLUTE", le), EAR["lat_min"] - 0.3)
        ear_h = math(nt, "MULTIPLY", math(nt, "ADD", math(nt, "ADD", helix, scapha), math(nt, "ADD", math(nt, "ADD", antihelix, concha), tragus)), math(nt, "MULTIPLY", win, on_ear))
        EXTRA_BUMP["skin"] = ear_h                                            # its own bump node below: the pores' bump is weak by design
        rough = math(nt, "ADD", R(0.46), math(nt, "MULTIPLY", math(nt, "SUBTRACT", noise(nt, P, 1.5, 2.0), 0.5), 0.16))
        return h, rough, 0.05, 0.006
    if name == "hair":
        rel = vmath(nt, "SUBTRACT", P, CROWN); x, y, z = separate(nt, rel)
        az = math(nt, "ARCTAN2", y, x)                                        # strands run down the meridians from the crown
        el = math(nt, "ARCTAN2", z, vmath(nt, "LENGTH", vmath(nt, "MULTIPLY", rel, (1, 1, 0))))
        wobble = math(nt, "MULTIPLY", math(nt, "SUBTRACT", noise(nt, P, 0.35, 2.0), 0.5), 1.6)
        strands = math(nt, "SINE", math(nt, "ADD", math(nt, "MULTIPLY", math(nt, "ADD", az, wobble), 36.0), math(nt, "MULTIPLY", el, 2.0)))
        clumps = noise(nt, P, 0.9, 2.0, 0.6)
        h = math(nt, "ADD", math(nt, "MULTIPLY", math(nt, "ADD", strands, 1.0), 0.3), math(nt, "MULTIPLY", clumps, 0.4))
        rough = math(nt, "ADD", R(0.40), math(nt, "MULTIPLY", math(nt, "SUBTRACT", clumps, 0.5), 0.3))
        return h, rough, 0.3, 0.05
    if name == "hoodie":                                                      # fleece jersey: fine knit + fuzz
        knit = math(nt, "MULTIPLY", wave(nt, P, 1.1, "X", 1.5, 1.0), wave(nt, P, 1.1, "Z", 1.5, 1.0))     # ~0.9 cm knit
        fuzz = noise(nt, P, 4.0, 3.0, 0.6)
        fold = noise(nt, P, 0.2, 2.0, 0.5)
        h = math(nt, "ADD", math(nt, "MULTIPLY", knit, 0.3), math(nt, "ADD", math(nt, "MULTIPLY", fuzz, 0.35), math(nt, "MULTIPLY", fold, 0.5)))
        rough = math(nt, "ADD", R(0.92), math(nt, "MULTIPLY", math(nt, "SUBTRACT", fuzz, 0.5), 0.1))
        return h, rough, 0.1, 0.03
    if name == "pants":                                                       # nylon track pants: a fine woven grid, a bit of sheen
        weave = math(nt, "ADD", wave(nt, P, 1.6, "X", 0.0, 0.0, "SIN"), wave(nt, P, 1.6, "Z", 0.0, 0.0, "SIN"))   # ~0.6 cm
        sheenv = noise(nt, P, 0.6, 2.0, 0.5)
        h = math(nt, "ADD", math(nt, "MULTIPLY", weave, 0.25), math(nt, "MULTIPLY", sheenv, 0.6))
        rough = math(nt, "ADD", R(0.72), math(nt, "MULTIPLY", math(nt, "SUBTRACT", sheenv, 0.5), 0.12))   # soft cotton-poly track pants, not PVC
        return h, rough, 0.08, 0.03
    if name == "socks":                                                       # cotton: a rib knit at the cuff, a fine jersey knit below, toe and heel seams
        rel = vmath(nt, "SUBTRACT", P, (0, 0, 0)); x, y, z = separate(nt, rel)
        ribs = math(nt, "SINE", math(nt, "MULTIPLY", math(nt, "ARCTAN2", y, math(nt, "SUBTRACT", math(nt, "ABSOLUTE", x), 14.0)), 90.0))
        cuff = math(nt, "MINIMUM", 1.0, math(nt, "MAXIMUM", 0.0, math(nt, "DIVIDE", math(nt, "SUBTRACT", z, 6.0), 1.2)))
        knit = math(nt, "MULTIPLY", wave(nt, P, 5.0, "X", 0.6, 0.0), wave(nt, P, 5.0, "Z", 0.6, 0.0))        # ~2 mm jersey loops
        fuzz = noise(nt, P, 12.0, 2.0, 0.6)
        h = math(nt, "ADD", math(nt, "MULTIPLY", math(nt, "MULTIPLY", math(nt, "ADD", ribs, 1.0), 0.35), cuff), math(nt, "ADD", math(nt, "MULTIPLY", knit, math(nt, "MULTIPLY", 0.08, math(nt, "SUBTRACT", 1.0, cuff))), math(nt, "MULTIPLY", fuzz, 0.03)))   # a subtle knit: the socks read as clean cotton, not fur
        lowfoot = math(nt, "LESS_THAN", z, 4.5); onleft = math(nt, "GREATER_THAN", x, 0.0)
        y_toe = mix(nt, FEET["right"]["y_toe"], FEET["left"]["y_toe"], onleft); x_mid = mix(nt, FEET["right"]["x_mid"], FEET["left"]["x_mid"], onleft); y_heel = mix(nt, FEET["right"]["y_heel"], FEET["left"]["y_heel"], onleft)
        dt_ = math(nt, "DIVIDE", math(nt, "SUBTRACT", y, math(nt, "ADD", y_toe, 1.0)), 0.12); toe = math(nt, "MULTIPLY", math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "MULTIPLY", dt_, dt_), -1.0)), lowfoot)
        dh_ = math(nt, "DIVIDE", math(nt, "SUBTRACT", x, x_mid), 0.12); heel = math(nt, "MULTIPLY", math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "MULTIPLY", dh_, dh_), -1.0)), math(nt, "MULTIPLY", math(nt, "GREATER_THAN", y, math(nt, "SUBTRACT", y_heel, 2.5)), math(nt, "LESS_THAN", z, 9.0)))
        h = math(nt, "SUBTRACT", h, math(nt, "MULTIPLY", math(nt, "ADD", toe, heel), 0.8))
        rough = math(nt, "ADD", R(0.95), 0.0)
        return h, rough, 0.2, 0.05
    if name == "slides":                                                      # EVA foam: smooth with faint cells, a tread groove around the sole's edge
        cells = voronoi(nt, P, 3.0, "SMOOTH_F1")
        _, _, zs = separate(nt, P); dz_ = math(nt, "DIVIDE", math(nt, "SUBTRACT", zs, 0.9), 0.15)
        tread = math(nt, "EXPONENT", math(nt, "MULTIPLY", math(nt, "MULTIPLY", dz_, dz_), -1.0))
        h = math(nt, "SUBTRACT", math(nt, "ADD", math(nt, "MULTIPLY", cells, 0.4), math(nt, "MULTIPLY", noise(nt, P, 8.0, 2.0), 0.2)), math(nt, "MULTIPLY", tread, 2.5))
        rough = math(nt, "ADD", R(0.62), math(nt, "MULTIPLY", math(nt, "SUBTRACT", cells, 0.5), 0.1))
        return h, rough, 0.12, 0.02
EXTRA_BUMP = {}
for i, name in enumerate(REGIONS):
    nt = m.materials[i].node_tree
    h, rough, strength, dist = detail_material(name, nt)
    bump = node(nt, "ShaderNodeBump", inputs={"Strength": strength, "Distance": dist}); links(nt).new(h, bump.inputs["Height"])
    last = bump.outputs[0]
    if name in EXTRA_BUMP:                                                       # the ears' relief (cm) on top, at full strength
        bump2 = node(nt, "ShaderNodeBump", inputs={"Strength": 0.8, "Distance": 0.3}); links(nt).new(EXTRA_BUMP[name], bump2.inputs["Height"]); links(nt).new(last, bump2.inputs["Normal"]); last = bump2.outputs[0]
    bsdf = node(nt, "ShaderNodeBsdfPrincipled"); links(nt).new(last, bsdf.inputs["Normal"]); links(nt).new(rough, bsdf.inputs["Roughness"])
    out = node(nt, "ShaderNodeOutputMaterial"); links(nt).new(bsdf.outputs[0], out.inputs[0])
    node(nt, "ShaderNodeTexImage", name="target")
scene.render.bake.normal_space = "TANGENT"
nrm_imgs = new_imgs("nrm_", SIZES); bake_to(nrm_imgs, "NORMAL", margin=12); save_imgs(nrm_imgs, "nrm_"); log("normal maps baked")
rough_imgs = new_imgs("rough_", SIZES); bake_to(rough_imgs, "ROUGHNESS", margin=12); save_imgs(rough_imgs, "rough_"); log("roughness baked")
if os.environ.get("BOY_AO", "1") != "0":
    scene.cycles.samples = int(os.environ.get("BOY_AO_SAMPLES", "24")); scene.world = bpy.data.worlds.new("w"); scene.world.light_settings.distance = 12.0
    ao_imgs = new_imgs("ao_", {"skin": 1024, "hair": 512, "cloth": 1024}); bake_to(ao_imgs, "AO", margin=8); save_imgs(ao_imgs, "ao_"); log("ao baked")
    scene.cycles.samples = 1

# the hair keeps crisp shard edges (smooth normals over the jagged shards read as blobs): edges between hair faces
# that meet at more than 40 degrees are marked sharp; the skin and the clothes stay fully smooth
hair_slot = REGIONS.index("hair"); hair_faces = set(p.index for p in m.polygons if p.material_index == hair_slot)
bm = bmesh.new(); bm.from_mesh(m); bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table(); n_sharp = 0
for e in bm.edges:
    if len(e.link_faces) == 2 and all(f.index in hair_faces for f in e.link_faces) and e.calc_face_angle(0) > np.radians(40):
        e.smooth = False; n_sharp += 1
bm.to_mesh(m); bm.free(); m.update()
log("hair sharp edges:", n_sharp)

# ---------------------------------------------------------------- export the mesh (with the armature, for the joints)
m.uv_layers.remove(m.uv_layers["uv_old"]); m.uv_layers.remove(m.uv_layers["hand_uv"])
for i, name in enumerate(REGIONS):
    nt = m.materials[i].node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bake_imgs[ATLAS[name][0]]
    nt.links.new(t.outputs[0], bsdf.inputs["Base Color"]); nt.links.new(bsdf.outputs[0], out.inputs[0])
proxy.hide_render = False; proxy.hide_viewport = False
m.validate(verbose=False); m.update()                                    # (the sharp-edge pass leaves the mesh flagged; validate before the exporter)
bpy.ops.object.select_all(action="DESELECT"); arm.select_set(True); me.select_set(True); proxy.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(WORK, "boy_mesh.glb"), use_selection=True, export_format="GLB", export_animations=False,
                          export_skins=True, export_yup=True, export_image_format="NONE", export_materials="EXPORT", export_normals=True)
# labels per face for the eye search in the next stage
np.save(os.path.join(WORK, "face_labels.npy"), np.array([REGIONS.index(flab[p.index]) if p.index < len(flab) else 0 for p in m.polygons]))
log("exported work/boy_mesh.glb")
