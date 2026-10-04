"""The dressed G2 GLB in a clip's pose, as three.js shows it, for the checks and the corrective shapes (Blender's Python:
numpy + mathutils). Linear blend skinning (four joints a vertex, world x inverse-bind), the clip's keys interpolated
linearly (rotations by slerp), and the garments' corrective shapes (glTF morph targets) weighted by their drivers before
skinning, exactly as the room page must do it (see DRIVERS and README.md).

Drivers (from joint world positions; the same in g2_clip_check.py's JavaScript):
  seated   hip bend: the angle between the thigh (UpLeg -> Leg) and the trunk downwards (neck -> Hips), both legs averaged
  elbow_L  elbow bend: the angle between the upper arm (Arm -> ForeArm) and the forearm (ForeArm -> Hand), left / right
  elbow_R
  lying    the chest's forward direction's height: front = (LeftArm - RightArm) x (neck - Hips), normalised; its y
each mapped by smoothstep(from, to, value) to the shape's weight."""
import json, os
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
import glb_io as G

HERE = os.path.dirname(os.path.abspath(__file__))
SHAPES = ["seated", "elbow_L", "elbow_R", "lying"]
DRIVERS = {"seated": {"type": "hip_bend", "from": 40.0, "to": 80.0},
           "elbow_L": {"type": "elbow_bend", "side": "Left", "from": 45.0, "to": 95.0},
           "elbow_R": {"type": "elbow_bend", "side": "Right", "from": 45.0, "to": 95.0},
           "lying": {"type": "chest_up", "from": 0.6, "to": 0.92}}


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)


class Dressed:
    def __init__(self, path=os.path.join(HERE, "assets", "g2", "boy_g2_dressed.glb"), naked=os.path.join(HERE, "g2", "boy_g2.glb")):
        js, bn = G.read(path); self.js, self.bn = js, bn; self.nodes = nodes = js["nodes"]
        self.parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
        skin = js["skins"][0]; self.joints = skin["joints"]
        self.IBM = G.accessor(js, bn, skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
        self.ix = {n.get("name"): i for i, n in enumerate(nodes)}
        self.meshes = {}
        for n in nodes:
            if "mesh" not in n: continue
            m = js["meshes"][n["mesh"]]; names = m.get("extras", {}).get("targetNames", [])
            prims = []
            for p in m["primitives"]:
                a = p["attributes"]
                prims.append(dict(P=G.accessor(js, bn, a["POSITION"]), J=G.accessor(js, bn, a["JOINTS_0"]).astype(int),
                                  W=G.accessor(js, bn, a["WEIGHTS_0"]), I=G.accessor(js, bn, p["indices"]).reshape(-1, 3),
                                  mat=js["materials"][p["material"]]["name"] if "material" in p else "",
                                  T={nm: G.accessor(js, bn, t["POSITION"]) for nm, t in zip(names, p.get("targets", []))}))
            self.meshes[n["name"]] = prims
        nj, nb = G.read(naked)
        self.full_body_I = G.accessor(nj, nb, nj["meshes"][0]["primitives"][0]["indices"]).reshape(-1, 3)
        self.drivers = js.get("extras", {}).get("correctives", {}).get("drivers", DRIVERS)

    # ---- posing
    def world(self, clip, t):
        """node world matrices (row-major 4x4) for a clip at time t (t < 0: from the end); clip None: the rest pose"""
        T = {i: list(n.get("translation", [0, 0, 0])) for i, n in enumerate(self.nodes)}
        R = {i: list(n.get("rotation", [0, 0, 0, 1])) for i, n in enumerate(self.nodes)}
        if clip:
            cj, cb = G.read(os.path.join(HERE, "g2", clip + ".glb")); an = cj["animations"][0]
            for ch in an["channels"]:
                i = self.ix.get(cj["nodes"][ch["target"]["node"]]["name"])
                if i is None: continue
                sm = an["samplers"][ch["sampler"]]; x = G.accessor(cj, cb, sm["input"]); y = G.accessor(cj, cb, sm["output"])
                tt = float(x.max()) + t if t < 0 else t
                k = int(np.clip(np.searchsorted(x, tt) - 1, 0, len(x) - 2)); f = float(np.clip((tt - x[k]) / max(x[k + 1] - x[k], 1e-9), 0, 1))
                if ch["target"]["path"] == "rotation":
                    q = Quaternion((y[k][3], *y[k][:3])).slerp(Quaternion((y[k + 1][3], *y[k + 1][:3])), f); R[i] = [q.x, q.y, q.z, q.w]
                elif ch["target"]["path"] == "translation": T[i] = list(y[k] * (1 - f) + y[k + 1] * f)
        out = {}
        def W(i):
            if i not in out:
                M = Quaternion((R[i][3], R[i][0], R[i][1], R[i][2])).to_matrix().to_4x4(); M.translation = Vector(T[i])
                out[i] = (W(self.parent[i]) if i in self.parent else np.eye(4)) @ np.array(M)
            return out[i]
        for i in range(len(self.nodes)): W(i)
        return out

    def skin_mats(self, world):
        return np.array([world[j] @ self.IBM[k] for k, j in enumerate(self.joints)])

    def pos(self, world, name): return world[self.ix[name]][:3, 3]

    def weights(self, world):
        p = lambda n: self.pos(world, n); out = {}
        down = p("Hips") - p("neck"); down /= np.linalg.norm(down)
        ang = lambda a, b: float(np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))
        for nm, d in self.drivers.items():
            if d["type"] == "hip_bend":
                v = np.mean([ang(p(s + "Leg") - p(s + "UpLeg"), down) for s in ("Left", "Right")])
            elif d["type"] == "elbow_bend":
                s = d["side"]; v = ang(p(s + "ForeArm") - p(s + "Arm"), p(s + "Hand") - p(s + "ForeArm"))
            elif d["type"] == "chest_up":
                f = np.cross(p("LeftArm") - p("RightArm"), -down); v = float(f[1] / np.linalg.norm(f))
            out[nm] = smoothstep(d["from"], d["to"], v); out[nm + "_value"] = round(v, 3)
        return out

    def skinned(self, prim, M, wts=None, extra=None):
        P = prim["P"].copy()
        if wts:
            for nm, d in prim["T"].items(): P = P + wts.get(nm, 0.0) * d
        if extra is not None: P = P + extra
        v = np.c_[P, np.ones(len(P))]; out = np.zeros((len(v), 3))
        for k in range(4): out += prim["W"][:, k, None] * np.einsum("nij,nj->ni", M[prim["J"][:, k]], v)[:, :3]
        return out

    def body_bvh(self, M):
        body = self.skinned(self.meshes["body"][0], M)
        return body, BVHTree.FromPolygons([Vector(x) for x in body], [tuple(int(i) for i in f) for f in self.full_body_I])


def inside(bvh, p):
    """inside a closed-ish surface: an odd number of crossings along at least two of three rays"""
    odd = 0
    for d in (Vector((0.31, 0.83, 0.46)), Vector((-0.71, -0.2, 0.67)), Vector((0.12, -0.6, -0.79))):
        n, o = 0, Vector(p)
        while True:
            h = bvh.ray_cast(o, d, 3.0)
            if h[0] is None: break
            n += 1; o = h[0] + d * 1e-5
        odd += n % 2
    return odd >= 2
