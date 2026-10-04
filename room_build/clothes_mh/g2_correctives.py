# blender -b -P g2_correctives.py
#
# Pose-driven corrective shapes for the clothes on G2's body (COORD A, after the owner's look at the clips): glTF morph
# targets on the hoodie and the trousers in assets/g2/boy_g2_dressed.glb, each weighted at run time by a driver read
# from the skeleton (g2_pose.DRIVERS; the room page computes the same numbers, see README.md). No cloth simulation:
# each shape is made in its pose - the garments skinned as three.js does, put right where they go wrong, and the fix
# carried back to the rest pose through the inverse of each vertex's skinning (so morph-then-skin gives the fixed pose).
#   seated   (desk_type_ik 3 s): the hoodie's front below the chest lies on the body and the lap as a soft shell with
#            2-3 horizontal folds (crests 22 mm, valleys 4 mm off what is under it: the body, or the trousers on the thighs),
#            the hem resting on the thighs, instead of ballooning over the lap; the trousers out of the body at the hip
#   elbow_L/R (desk_type_ik 3 s): the sleeve around a bent elbow out of the arm and its bunching held within 1.5 cm
#   lying    (room_bed_lie 12 s): the hoodie's upper back, shoulders and the lowered hood flattened onto the body and
#            the mattress (not below 5 mm under its top: G2's soft-mattress contact), the hood pressed under the neck
import sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import glb_io as G, g2_pose as GP

PATH = os.path.join(HERE, "assets", "g2", "boy_g2_dressed.glb")
D = GP.Dressed(PATH)
for g in D.meshes.values():                                      # (start from no shapes, if the file already had some)
    for p in g: p["T"] = {}
GARMENTS = ["hoodie_black", "track_trousers"]
MATTRESS_Y = 0.66
DRIVERS = dict(GP.DRIVERS); DRIVERS["elbow_L"] = dict(DRIVERS["elbow_L"], **{"from": 55.0}); DRIVERS["elbow_R"] = dict(DRIVERS["elbow_R"], **{"from": 55.0})
D.drivers = DRIVERS


def crease(x, period, width):
    u = ((x / period) % 1.0 - 0.5) * period; return math.exp(-(u / width) ** 2)


class Welded:
    """a garment's primitives as one mesh: seam duplicates (same rest position) share one vertex and one shape delta"""
    def __init__(self, prims):
        P = np.concatenate([p["P"] for p in prims]); keys = np.round(P / 1e-6).astype(np.int64)
        _, first, inv = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        self.inv = inv.ravel(); self.P = P[first]
        self.J = np.concatenate([p["J"] for p in prims])[first]; self.W = np.concatenate([p["W"] for p in prims])[first]
        off = np.cumsum([0] + [len(p["P"]) for p in prims]); self.slices = [(off[i], off[i + 1]) for i in range(len(prims))]
        nb = [set() for _ in range(len(self.P))]
        for k, p in enumerate(prims):
            for t in p["I"]:
                a, b, c = (self.inv[off[k] + i] for i in t)
                nb[a] |= {b, c}; nb[b] |= {a, c}; nb[c] |= {a, b}
        self.nb = [np.array(sorted(s), int) for s in nb]
        self.delta = {s: np.zeros_like(self.P) for s in GP.SHAPES}

    def prim(self): return {"P": self.P, "J": self.J, "W": self.W, "T": self.delta}

    def to_rest(self, M, dposed):
        """posed offsets -> rest offsets: the inverse of each vertex's blended skinning matrix (3x3)"""
        A = np.zeros((len(self.P), 3, 3))
        for k in range(4): A += self.W[:, k, None, None] * M[self.J[:, k], :3, :3]
        return np.linalg.solve(A, dposed[..., None])[..., 0]

    def smooth(self, d, passes=4, f=0.5):
        for _ in range(passes):
            avg = np.array([d[n].mean(0) if len(n) else d[i] for i, n in enumerate(self.nb)]); d = d * (1 - f) + avg * f
        return d


WG = {g: Welded(D.meshes[g]) for g in GARMENTS}


def surface(points_list, tris_list):
    V = np.concatenate(points_list); off = np.cumsum([0] + [len(p) for p in points_list]); F = []
    for k, T in enumerate(tris_list): F += [tuple(int(i) + off[k] for i in t) for t in T]
    return BVHTree.FromPolygons([Vector(x) for x in V], F)


def posed(clip, t):
    world = D.world(clip, t); M = D.skin_mats(world); wts = D.weights(world)
    body, bbvh = D.body_bvh(M)
    P = {g: D.skinned(WG[g].prim(), M, wts) for g in GARMENTS}
    return world, M, wts, body, bbvh, P


def put(g, M, mask, target):
    """move the garment's posed vertices toward their targets by `mask`, as a rest-pose shape delta (smoothed)"""
    w = WG[g]; dp = (target - Ppose[g]) * mask[:, None]
    return w.smooth(w.to_rest(M, dp)) * np.minimum(1.0, mask * 3)[:, None]


def outside(bvh, q, n, gap):
    """the point `gap` off the surface at q, on its outer side (some faces' normals point in)"""
    c = q + n * gap
    return np.array(c if not GP.inside(bvh, c) else q - n * gap)


def ss(a, b, x): return np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))


report = {}
# ---------------------------------------------------------------- seated (and the trousers at the hip)
world, M, wts, body, bbvh, Ppose = posed("desk_type_ik", 3.0)
H = WG["hoodie_black"]; R0 = H.P
hem_y = R0[:, 1].min(); hz = R0[:, 1] - hem_y
region = (1 - ss(0.20, 0.33, hz)) * ss(-0.03, 0.03, R0[:, 2]) * (1 - ss(0.17, 0.23, np.abs(R0[:, 0])))
trP = Ppose["track_trousers"]; Tw = WG["track_trousers"]
tris_tr = np.concatenate([Tw.inv[a:b][D.meshes["track_trousers"][k]["I"]] for k, (a, b) in enumerate(Tw.slices)])
under = surface([body, trP], [D.full_body_I, tris_tr])
tgt = Ppose["hoodie_black"].copy()
for i in np.nonzero(region > 0)[0]:
    p = Vector(Ppose["hoodie_black"][i]); q, n, _, d = under.find_nearest(p)
    if q is None: continue
    if (p - q).dot(n) < 0: n = -n if not GP.inside(bbvh, p) else n            # (the nearest face may face away)
    # 2-3 soft horizontal folds across the front (6 cm apart, curving up a little at the sides): round crests 2.2 cm off,
    # narrow valleys 4 mm off what is under
    band = hz[i] - 0.04 + 0.014 * (1 - math.cos(min(abs(R0[i, 0]) / 0.17, 1) * math.pi / 2))
    fold = (1 - crease(band, 0.06, 0.011)) * ss(0.02, 0.05, hz[i]) * (1 - ss(0.17, 0.24, hz[i]))
    gap = 0.004 + 0.018 * fold
    tgt[i] = np.array(q + n * gap)
H.delta["seated"] = put("hoodie_black", M, region, tgt)
# the trousers: out of the body at the front of the hip and the crotch (3 mm)
T0 = Tw.P; reg_t = ss(0.62, 0.72, T0[:, 1]) * (1 - ss(0.98, 1.06, T0[:, 1])); tgt = trP.copy(); moved = 0
for i in np.nonzero(reg_t > 0)[0]:
    p = Vector(trP[i])
    if GP.inside(bbvh, p):
        q, n, _, _ = bbvh.find_nearest(p); tgt[i] = outside(bbvh, q, n, 0.003); moved += 1
Tw.delta["seated"] = put("track_trousers", M, reg_t * (np.linalg.norm(tgt - trP, axis=1) > 0), tgt)
report["seated"] = {"pose": "desk_type_ik 3 s", "hoodie_vertices": int((region > 0).sum()), "trousers_out_of_body": moved}
# ---------------------------------------------------------------- the elbows (same pose, the seated shape on)
world, M, wts, body, bbvh, Ppose = posed("desk_type_ik", 3.0)
for side, sg in (("L", 1), ("R", -1)):
    e = GP.np.array(D.pos(D.world(None, 0), ("Left" if sg > 0 else "Right") + "ForeArm"))   # the rest elbow
    dist = np.linalg.norm(R0 - e, axis=1); reg = (1 - ss(0.09, 0.16, dist)) * (R0[:, 0] * sg > 0.1)
    tgt = Ppose["hoodie_black"].copy(); n_in = 0
    for i in np.nonzero(reg > 0)[0]:
        p = Vector(tgt[i]); q, n, _, d = bbvh.find_nearest(p)
        if q is None: continue
        ins = GP.inside(bbvh, p); s = -d if ins else d
        g_ = min(max(s, 0.005), 0.015)
        if ins: n_in += 1
        if abs(g_ - s) > 1e-4: tgt[i] = np.array(q + n * g_ * (1 if (p - q).dot(n) >= 0 or ins else -1))
    H.delta["elbow_" + side] = put("hoodie_black", M, reg, tgt)
    report["elbow_" + side] = {"pose": "desk_type_ik 3 s", "vertices": int((reg > 0).sum()), "were_inside": n_in}
# ---------------------------------------------------------------- lying
world, M, wts, body, bbvh, Ppose = posed("room_bed_lie", 12.0)
back = ss(0.04, -0.02, R0[:, 2]) * (1 - ss(0.2, 0.26, np.abs(R0[:, 0])))           # the whole back: on the mattress
upper = ss(1.12, 1.24, R0[:, 1]) * back                                             # shoulders, upper back: onto the body
caps = ss(1.22, 1.32, R0[:, 1]) * (1 - ss(0.3, 0.38, np.abs(R0[:, 0])))           # the sleeves' tops at the shoulders, all round
upper = np.maximum(upper, caps)
W0 = D.world(None, 0)                                                               # the shoulders' hump (the arms lowered
for sd in ("Left", "Right"):                                                        # from the A-pose push the cloth up there)
    upper = np.maximum(upper, 1 - ss(0.11, 0.17, np.linalg.norm(R0 - D.pos(W0, sd + "Arm"), axis=1)))
hood = (R0[:, 1] > 1.36) & (R0[:, 2] < 0.06) & (np.abs(R0[:, 0]) < 0.2)
upper = np.maximum(upper, hood.astype(float)); reg = np.maximum(back, upper)
tgt = Ppose["hoodie_black"].copy()
for i in np.nonzero(reg > 0)[0]:
    p = Vector(tgt[i]); t_ = np.array(p)
    if upper[i] > 0:
        q, n, _, d = bbvh.find_nearest(p)
        if q is not None and not GP.inside(bbvh, p):
            g_ = 0.004 if hood[i] else 0.006
            t_ = t_ * (1 - upper[i]) + np.array(q + n * min(g_, d)) * upper[i]
    t_[1] = max(t_[1], MATTRESS_Y - 0.005); tgt[i] = t_
H.delta["lying"] = put("hoodie_black", M, reg, tgt)
report["lying"] = {"pose": "room_bed_lie 12 s", "vertices": int((reg > 0).sum())}

# ---------------------------------------------------------------- clean-up: each shape's pose, all shapes on: no garment
# vertex inside the body (where smoothing pulled one in, or the knee and the hip fold the cloth in), 3 mm out, added to
# the shape that pose drives
for clip, t, shape in (("desk_type_ik", 3.0, "seated"), ("room_bed_lie", 12.0, "lying")):
    world, M, wts, body, bbvh, Ppose = posed(clip, t)
    for g in GARMENTS:
        w = WG[g]; tgt = Ppose[g].copy(); mask = np.zeros(len(tgt)); shaped = np.zeros(len(tgt), bool)
        for s_ in GP.SHAPES: shaped |= np.abs(w.delta[s_]).max(1) > 1e-6
        for i in range(len(tgt)):                                   # (every vertex: the knees and the hips bend there too)
            p = Vector(tgt[i])
            if GP.inside(bbvh, p):
                q, n, _, _ = bbvh.find_nearest(p); tgt[i] = outside(bbvh, q, n, 0.003); mask[i] = 1
        if mask.any():
            w.delta[shape] = w.delta[shape] + w.to_rest(M, (tgt - Ppose[g]) * mask[:, None]) / max(wts[shape], 1e-3)
        report.setdefault("cleanup", {})[f"{g}@{clip}"] = int(mask.sum())

# ---------------------------------------------------------------- write: morph targets on the garments' meshes
js, bn = G.read(PATH); Wr = G.Writer(js, bn)
for n in js["nodes"]:
    if n.get("name") not in GARMENTS: continue
    m = js["meshes"][n["mesh"]]; w = WG[n["name"]]
    for k, p in enumerate(m["primitives"]):
        a, b = w.slices[k]; ids = w.inv[a:b]
        p["targets"] = [{"POSITION": Wr.acc(w.delta[s][ids].astype(np.float32), "VEC3", 34962, minmax=True)} for s in GP.SHAPES]
    m["weights"] = [0.0] * len(GP.SHAPES); m.setdefault("extras", {})["targetNames"] = GP.SHAPES
js.setdefault("extras", {})["correctives"] = {
    "shapes": GP.SHAPES, "drivers": DRIVERS,
    "how": "each frame after the animation: weight = smoothstep(from, to, value) of the driver (g2_pose.py, README.md), "
           "set as mesh.morphTargetInfluences on hoodie_black and track_trousers"}
Wr.write(PATH)
for s in GP.SHAPES:
    report.setdefault(s, {})["max_shift_mm"] = round(1000 * max(float(np.abs(WG[g].delta[s]).max()) for g in GARMENTS), 1)
json.dump(report, open(os.path.join(HERE, "out", "correctives.json"), "w"), indent=1)
print("CORRECTIVES", json.dumps(report)); print("wrote", PATH, round(os.path.getsize(PATH) / 1e6, 2), "MB")
