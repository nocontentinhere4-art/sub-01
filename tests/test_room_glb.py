"""The room model (#75): web/room/room_clean.glb stays small, keeps the nodes room.html reads, the lamp marker sits under
a lamp that is clear of the walls, and every Poly Haven asset the build imports is credited. Reads only the GLB's JSON
chunk (the meshes are meshopt-compressed; the full prop sweep runs in the Blender build, room_build/build_room.py)."""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLB = ROOT / "web" / "room" / "room_clean.glb"
IX, IZ = -1.9, -1.45                     # inner faces of the window wall and the back wall (build_room.py)
DTOP = 0.97


def gltf():
    data = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    n, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + n])


def nodes():
    return {n.get("name"): n for n in gltf()["nodes"]}


def test_size_budget():
    assert GLB.stat().st_size <= 7 * 1024 * 1024


def test_nodes_the_page_reads():
    names = nodes()
    for k in ("chair", "headphones", "hangers", "SURF_monitor", "SURF_window", "SURF_lamp"):
        assert k in names, k
    for k in ("chair", "headphones", "hangers"):
        assert names[k].get("children"), k                        # pivots kept: the mesh is in a child node


def test_lamp_marker_over_the_desk_and_off_the_walls():
    m = nodes()["SURF_lamp"]
    x, y, z = (m["matrix"][12:15] if "matrix" in m else m["translation"])
    assert -1.86 < x < -0.36 and -1.45 < z < -0.80, (x, z)        # over the desk
    assert y > DTOP + 0.1, y
    assert x > IX + 0.01 and z > IZ + 0.01, (x, z)


def test_headphones_hang_on_the_back_wall():
    t = nodes()["headphones"]["translation"]
    assert IZ < t[2] < IZ + 0.1 and 1.2 < t[1] < 1.7


def test_door_hangers_turn_about_the_door_hinge():
    t = nodes()["hangers"]["translation"]                         # room.html's opening leaf pivots at (1.11, F + 0.008, IZ)
    assert abs(t[0] - 1.11) < 1e-3 and abs(t[1] - 0.168) < 1e-3 and abs(t[2] - IZ) < 1e-3, t


def test_no_other_material_is_named_door():
    names = [m.get("name", "") for m in gltf()["materials"]]
    assert sum(n.lower().startswith("door") for n in names) == 1, names   # room.html takes the first "door*" material for its leaf


def test_every_imported_asset_is_credited():
    src = (ROOT / "room_build" / "build_room.py").read_text()
    credits = (ROOT / "web" / "room" / "CREDITS.md").read_text()
    used = set(re.findall(r'import_asset\("([a-z0-9_]+)"', src))
    assert used, "no import_asset calls found"
    for k in used:
        assert f"`{k}`" in credits, k


def test_every_texture_is_credited():
    """every Poly Haven texture tex_prep.py reads (tex/<id>/...) has a row in CREDITS.md"""
    src = (ROOT / "room_build" / "tex_prep.py").read_text()
    credits = (ROOT / "web" / "room" / "CREDITS.md").read_text()
    used = set(re.findall(r'\{T\}/([a-z0-9_]+)/', src))
    assert len(used) >= 14, used
    for k in used:
        assert f"`{k}`" in credits, k


# ---- the soft goods (#98 G4, room_build/props_soft.py)
SOFT_MATERIALS = ["sheet", "duvet", "curtain", "rug", "cushion", "bag", "knit", "terry", "denim", "jersey", "hang_hoodie", "hang_canvas", "hang_rib"]


def triangles(g):
    n = 0
    for m in g["meshes"]:
        for p in m["primitives"]:
            acc = g["accessors"][p["indices"]] if "indices" in p else g["accessors"][p["attributes"]["POSITION"]]
            n += acc["count"] // 3
    return n


def test_soft_goods_materials_present():
    names = {m.get("name") for m in gltf()["materials"]}
    for k in SOFT_MATERIALS:
        assert k in names, k
    assert "room_static" in nodes()


def test_fabrics_have_their_normal_maps_and_sheen():
    g = gltf(); by = {m.get("name"): m for m in g["materials"]}
    for k in ("knit", "terry", "duvet", "curtain", "denim", "hang_hoodie"):
        assert "normalTexture" in by[k], k
    for k in ("knit", "terry", "curtain", "duvet"):
        assert "KHR_materials_sheen" in by[k].get("extensions", {}), k


def test_triangle_and_draw_call_budget():
    """the room page must stay >= 30 FPS on a mid-range phone: the whole model stays under 230k triangles and 60 draw calls"""
    g = gltf()
    prims = sum(len(m["primitives"]) for m in g["meshes"])
    assert prims <= 60, prims
    assert 120_000 <= triangles(g) <= 230_000, triangles(g)


def test_phone_screen_module_has_no_brand_ui():
    code = "\n".join(l for l in (ROOT / "web" / "room_phone.js").read_text().splitlines() if not l.strip().startswith("//"))
    for w in ("iOS", "Android", "Apple", "iPhone", "Google", "Samsung", "Galaxy", "Pixel"):
        assert w not in code, w
