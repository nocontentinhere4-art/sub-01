"""Issue #76: the second character (web/room/boy2*.glb) keeps its budget and plays every clip of the first one.

Reads only the GLB's JSON chunk (and the WebP headers of its textures), so it needs no 3D library: meshopt-compressed
buffers still carry their accessors' counts.
"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOM = ROOT / "web" / "room"
MB = 1024 * 1024


def glb(path):
    """(json, binary chunk) of a .glb file."""
    raw = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", raw, 0)
    assert magic == b"glTF", path
    n, kind = struct.unpack_from("<I4s", raw, 12)
    assert kind == b"JSON"
    js = json.loads(raw[20:20 + n])
    off = 20 + n
    binary = b""
    if off < len(raw):
        m, kind2 = struct.unpack_from("<I4s", raw, off)
        assert kind2 == b"BIN\x00"
        binary = raw[off + 8:off + 8 + m]
    return js, binary


def webp_size(data):
    """Width, height of a WebP image from its header (VP8, VP8L or VP8X)."""
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    chunk = data[12:16]
    if chunk == b"VP8X":
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return w, h
    if chunk == b"VP8L":
        b = int.from_bytes(data[21:25], "little")
        return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    assert chunk == b"VP8 "
    w, h = struct.unpack_from("<HH", data, 26)
    return w & 0x3FFF, h & 0x3FFF


def image_bytes(js, binary, image):
    view = js["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    return binary[start:start + view["byteLength"]]


def anim_names(path):
    js, _ = glb(path)
    return [a.get("name") for a in js.get("animations", [])]


def test_budget():
    path = ROOM / "boy2.glb"
    assert path.stat().st_size <= 3 * MB
    js, binary = glb(path)
    tris = sum(js["accessors"][p["indices"]]["count"] // 3 for m in js["meshes"] for p in m["primitives"])
    assert 15000 < tris <= 25000
    assert len(js["materials"]) <= 2
    for img in js["images"]:
        w, h = webp_size(image_bytes(js, binary, img))
        assert w <= 2048 and h <= 2048
    # one alpha-tested material (hair, brows, lashes), never blended (no sorting, no extra pass)
    assert [m.get("alphaMode", "OPAQUE") for m in js["materials"]].count("BLEND") == 0


def test_rig_has_old_names_fingers_eyes_and_blink():
    js, _ = glb(ROOM / "boy2.glb")
    names = {n.get("name") for n in js["nodes"]}
    old, _ = glb(ROOM / "boy.glb")
    old_bones = {old["nodes"][j]["name"] for j in old["skins"][0]["joints"]}
    assert old_bones <= names                      # room.html finds the same bones (RightHand, Head, headfront, ...)
    for side in ("Left", "Right"):
        for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
            assert {f"{side}Hand{finger}{k}" for k in (1, 2, 3)} <= names
        assert f"{side}Eye" in names
    assert {"socket_phone", "socket_chopsticks", "socket_spoon"} <= names
    mesh = js["meshes"][0]
    assert mesh["extras"]["targetNames"] == ["blink"]
    assert all(len(p.get("targets", [])) == 1 for p in mesh["primitives"])
    assert "blink" in anim_names(ROOM / "boy2.glb")


def test_every_clip_is_retargeted_with_its_name():
    old_files = sorted(p.name for p in ROOM.glob("boy_*.glb"))
    assert old_files
    for f in old_files:
        new = ROOM / f.replace("boy_", "boy2_", 1)
        assert new.exists(), new.name
        assert anim_names(new) == anim_names(ROOM / f)
    assert anim_names(ROOM / "boy2.glb")[0] == anim_names(ROOM / "boy.glb")[0]     # the sit clip, first like before


def test_clips_target_only_bones_of_the_new_rig():
    js, _ = glb(ROOM / "boy2.glb")
    names = {n.get("name") for n in js["nodes"]}
    for path in sorted(ROOM.glob("boy2_*.glb")):
        c, _ = glb(path)
        for a in c.get("animations", []):
            for ch in a["channels"]:
                assert c["nodes"][ch["target"]["node"]]["name"] in names, (path.name, a["name"])
                assert ch["target"]["path"] in ("rotation", "translation"), (path.name, ch["target"])


def test_finger_poses():
    names = anim_names(ROOM / "boy2_hands.glb")
    assert names == ["hand_relaxed", "hand_phone", "hand_chopsticks", "hand_spoon", "hand_type", "hand_mouse"]
