"""CPU-only UV atlas preparation. xatlas + pygltflib; no renderer or GPU required."""

import sys, json, struct
from pathlib import Path
import numpy as np
import xatlas
from pygltflib import GLTF2

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
g = GLTF2().load(str(source))
data = g.binary_blob()
components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
dtypes = {5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "u1"}


def read(i):
    a = g.accessors[i]
    v = g.bufferViews[a.bufferView]
    dt = np.dtype(dtypes[a.componentType])
    n = components[a.type]
    return np.ndarray(
        (a.count, n),
        dt,
        buffer=data,
        offset=(v.byteOffset or 0) + (a.byteOffset or 0),
        strides=(v.byteStride or dt.itemsize * n, dt.itemsize),
    ).copy()


def local(n):
    if n.matrix:
        return np.array(n.matrix).reshape(4, 4, order="F")
    x, y, z, w = n.rotation or [0, 0, 0, 1]
    s = np.array(n.scale or [1, 1, 1])
    m = np.eye(4)
    m[:3, :3] = (
        np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )
        * s
    )
    m[:3, 3] = n.translation or [0, 0, 0]
    return m


world = {}


def visit(i, p):
    world[i] = p @ local(g.nodes[i])
    for c in g.nodes[i].children or []:
        visit(c, world[i])


for i in g.scenes[g.scene or 0].nodes:
    visit(i, np.eye(4))
a = xatlas.Atlas()
original = []
for i, n in enumerate(g.nodes):
    if not n.extras or not n.extras.get("bakeId"):
        continue
    p = g.meshes[n.mesh].primitives[0]
    v = read(p.attributes.POSITION)
    norm = read(p.attributes.NORMAL)
    uv = read(p.attributes.TEXCOORD_0)
    matrix = world[i]
    v = (np.c_[v, np.ones(len(v))] @ matrix.T)[:, :3].astype("float32")
    norm = norm @ np.linalg.inv(matrix[:3, :3])
    norm /= np.linalg.norm(norm, axis=1)[:, None]
    ix = (
        read(p.indices).reshape(-1, 3)
        if p.indices is not None
        else np.arange(len(v), dtype="uint32").reshape(-1, 3)
    )
    a.add_mesh(v, ix.astype("uint32"))
    original.append((n.extras["bakeId"], v, norm.astype("float32"), uv))
opts = xatlas.PackOptions()
opts.resolution = 1024
opts.padding = 3
opts.texels_per_unit = 0
print("Packing", len(original), "meshes", flush=True)
a.generate(pack_options=opts)
print("Atlas", a.width, a.height, a.atlas_count, flush=True)
assert a.atlas_count == 1, "All geometry must use one atlas"
blob = bytearray()
views = []
accessors = []
meshes = []
nodes = []


def attr(arr, typ):
    arr = np.asarray(arr, dtype="<f4" if typ != "SCALAR" else "<u4")
    start = len(blob)
    blob.extend(arr.tobytes())
    views.append({"buffer": 0, "byteOffset": start, "byteLength": arr.nbytes})
    rec = {
        "bufferView": len(views) - 1,
        "componentType": 5126 if typ != "SCALAR" else 5125,
        "count": len(arr),
        "type": typ,
    }
    if typ == "VEC3":
        rec.update(min=arr.min(axis=0).tolist(), max=arr.max(axis=0).tolist())
    accessors.append(rec)
    return len(accessors) - 1


for k, (name, v, n, uv) in enumerate(original):
    remap, ix, lightuv = a[k]
    attrs = {
        "POSITION": attr(v[remap], "VEC3"),
        "NORMAL": attr(n[remap], "VEC3"),
        "TEXCOORD_0": attr(uv[remap], "VEC2"),
        "TEXCOORD_1": attr(lightuv, "VEC2"),
    }
    meshes.append(
        {
            "primitives": [
                {
                    "attributes": attrs,
                    "indices": attr(ix.reshape(-1), "SCALAR"),
                    "mode": 4,
                }
            ]
        }
    )
    nodes.append({"name": name, "mesh": k, "extras": {"bakeId": name}})
j = {
    "asset": {"version": "2.0"},
    "scene": 0,
    "scenes": [{"nodes": list(range(len(nodes)))}],
    "nodes": nodes,
    "meshes": meshes,
    "accessors": accessors,
    "bufferViews": views,
    "buffers": [{"byteLength": len(blob)}],
    "extras": {"width": a.width, "height": a.height},
}
jb = json.dumps(j, separators=(",", ":")).encode()
jb += b" " * ((-len(jb)) % 4)
blob += b"\0" * ((-len(blob)) % 4)
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_bytes(
    struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(jb) + 8 + len(blob))
    + struct.pack("<II", len(jb), 0x4E4F534A)
    + jb
    + struct.pack("<II", len(blob), 0x004E4942)
    + blob
)
