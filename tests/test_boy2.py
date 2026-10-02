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


def test_motion_set():
    """#63's clip list, in one file; every clip keys every body bone (the fingers are left to the finger poses) and
    moves the hips."""
    names = anim_names(ROOM / "boy2_motion.glb")
    for n in ["lie_back_idle", "lie_side_left", "lie_side_right", "roll_back_to_side_L", "roll_back_to_side_R",
              "sit_idle_upright", "type", "mouse", "stand_idle", "walk", "walk_start", "walk_stop", "sit_down_chair",
              "stand_up_chair", "sit_down_bed_edge", "stand_up_bed_edge", "sit_edge_idle", "lie_down_from_edge",
              "get_up_to_edge", "lie_phone", "sleep_breathing", "door_open_pull", "take_item", "put_down", "crouch_drop",
              "lean_on_sill", "stretch_arms_up", "scratch_head", "look_around", "sit_lean_back", "sit_eat_chopsticks",
              "sit_drink", "turn_in_place_L90", "turn_in_place_R90"]:
        assert n in names, n
    js, _ = glb(ROOM / "boy2_motion.glb")
    fingers = {f"{s}Hand{f}{k}" for s in ("Left", "Right") for f in ("Thumb", "Index", "Middle", "Ring", "Pinky") for k in (1, 2, 3)}
    bones = {n["name"] for n in js["nodes"]} - {"Armature", "socket_phone", "socket_chopsticks", "socket_spoon"} - fingers
    for a in js["animations"]:
        rot = {js["nodes"][c["target"]["node"]]["name"] for c in a["channels"] if c["target"]["path"] == "rotation"}
        assert rot == bones, a["name"]
        assert any(c["target"]["path"] == "translation" for c in a["channels"]), a["name"]


DEFORM = ROOT / "docs" / "character" / "deform_check.json"
# cm; the report is written by room_build/boy_post.mjs (deformCheck) from the same skinning the browser does
LIMITS = {"bulge_legs_cm": 4.5, "bulge_arms_cm": 7.0, "bulge_trunk_cm": 4.5, "torso_cm": 1.0}


def test_deform_check_covers_every_motion_clip():
    report = json.loads(DEFORM.read_text())
    checked = {c["clip"] for c in report["clips"] if c["file"] == "boy2_motion.glb"}
    assert checked == set(anim_names(ROOM / "boy2_motion.glb"))


def test_motion_keeps_cloth_on_the_body_and_hands_out_of_the_torso():
    """No vertex of skin or cloth swells more than the limit off its bones (the joggers at a bent hip and knee, the
    sleeves at the shoulder), and no forearm or hand passes through the torso, at any frame of any new clip."""
    report = json.loads(DEFORM.read_text())
    for c in report["clips"]:
        if c["file"] != "boy2_motion.glb":
            continue
        for k, limit in LIMITS.items():
            assert c[k] <= limit, (c["clip"], k, c[k], c.get("bulge_at"), c.get("torso_at"))
