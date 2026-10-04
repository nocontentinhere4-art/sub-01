"""Minimal glTF binary (.glb) reading and writing with numpy: enough to read G2's body and to add the clothes to it.
No dependencies beyond numpy."""
import json, struct
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read(path):
    b = open(path, "rb").read()
    assert b[:4] == b"glTF", path
    n = struct.unpack_from("<I", b, 12)[0]; js = json.loads(b[20:20 + n])
    off = 20 + n; m = struct.unpack_from("<I", b, off)[0]; binc = b[off + 8: off + 8 + m]
    return js, bytearray(binc)


def accessor(js, binc, i):
    a = js["accessors"][i]; bv = js["bufferViews"][a["bufferView"]]
    dt = np.dtype(CT[a["componentType"]]); nc = NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0); stride = bv.get("byteStride", 0)
    if stride and stride != dt.itemsize * nc:
        rows = [np.frombuffer(binc, dt, nc, start + k * stride) for k in range(a["count"])]; return np.array(rows)
    arr = np.frombuffer(binc, dt, a["count"] * nc, start)
    return (arr.reshape(a["count"], nc) if nc > 1 else arr).copy()     # a copy: the buffer may grow later


class Writer:
    """appends buffer views and accessors to an existing glTF (js, bin)"""
    def __init__(self, js, binc):
        self.js, self.bin = js, binc
        for k in ("accessors", "bufferViews", "meshes", "materials", "textures", "images", "samplers", "nodes"):
            js.setdefault(k, [])

    def view(self, data, target=None):
        while len(self.bin) % 4: self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target: v["target"] = target
        self.bin.extend(data); self.js["bufferViews"].append(v); return len(self.js["bufferViews"]) - 1

    def acc(self, arr, kind, target=None, minmax=False):
        arr = np.ascontiguousarray(arr); ct = {np.dtype(np.float32): 5126, np.dtype(np.uint16): 5123,
                                              np.dtype(np.uint32): 5125, np.dtype(np.uint8): 5121}[arr.dtype]
        a = {"bufferView": self.view(arr.tobytes(), target), "componentType": ct, "count": int(arr.shape[0]), "type": kind}
        if minmax: a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        self.js["accessors"].append(a); return len(self.js["accessors"]) - 1

    def image(self, path, mime="image/jpeg"):
        self.js["images"].append({"bufferView": self.view(open(path, "rb").read()), "mimeType": mime})
        if not self.js["samplers"]: self.js["samplers"].append({"wrapS": 10497, "wrapT": 10497, "magFilter": 9729, "minFilter": 9987})
        self.js["textures"].append({"sampler": 0, "source": len(self.js["images"]) - 1}); return len(self.js["textures"]) - 1

    def write(self, path):
        while len(self.bin) % 4: self.bin.append(0)
        self.js["buffers"] = [{"byteLength": len(self.bin)}]
        j = json.dumps(self.js, separators=(",", ":")).encode()
        while len(j) % 4: j += b" "
        out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(self.bin))
        out += struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin)
        open(path, "wb").write(out)
