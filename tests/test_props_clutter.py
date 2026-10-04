"""The lived-in clutter (#98): web/room/props_clutter.glb stays small, holds the bottle the page drinks from and the props
it places about the room, each within the web budget (its triangles are in the scene's extras: the props are joined by
material), its scans credited, and room.html loads it and moves the bottle into PROP.bottle. Reads only the GLB's JSON
chunk (the meshes are meshopt-compressed; the placement sweep, with the collisions against the built room, runs in
room_build/props_clutter.py)."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLB = ROOT / "web" / "room" / "props_clutter.glb"
PROPS = ["notebook", "pen_pencil", "earbuds", "charger", "charger_cable", "glass", "apple", "succulent_shelf", "paper_balls",
         "mug", "phone", "socket", "phone_cable", "books_floor", "magazine", "laptop", "key_bowl", "keys", "wallet", "boots", "hamper"]
SCANS = ["binder_notebook", "stationery_supplies", "food_apple_01", "potted_plant_04", "wooden_bowl_02", "rubber_boots", "wicker_basket_02"]


def gltf():
    data = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    n, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + n])


def triangles(g, mesh):
    n = 0
    for p in g["meshes"][mesh]["primitives"]:
        acc = g["accessors"][p["indices"]] if "indices" in p else g["accessors"][p["attributes"]["POSITION"]]
        n += acc["count"] // 3
    return n


def test_size_and_draw_calls():
    assert GLB.stat().st_size <= 2.5 * 1024 * 1024
    g = gltf()
    assert sum(len(m["primitives"]) for m in g["meshes"]) <= 30          # one per material: the props are joined


def test_every_prop_within_the_web_budget():
    g = gltf(); names = {n.get("name"): n for n in g["nodes"]}
    ex = g["scenes"][0]["extras"]; tris, boxes = json.loads(ex["tris"]), json.loads(ex["boxes"])
    assert set(PROPS) <= set(boxes) and "props" not in ex             # (no other GLB's extras: the page reads those of props_tripo2)
    for k in PROPS + ["bottle"]:
        assert 0 < tris[k] <= 10_000, k
    b = names["bottle"]                                         # the bottle: a plain node (origin at its base) over its mesh
    assert "mesh" not in b and b.get("children"), b
    child = g["nodes"][b["children"][0]]
    assert triangles(g, child["mesh"]) <= 10_000


def test_textures_are_small():
    for im in gltf()["images"]:
        assert im.get("mimeType") == "image/webp", im.get("name")


def test_scans_are_credited():
    credits = (ROOT / "web" / "room" / "CREDITS.md").read_text()
    src = (ROOT / "room_build" / "props_clutter.py").read_text()
    for k in SCANS:
        assert f'import_scan("{k}"' in src and f"`{k}`" in credits, k


def test_page_loads_it_and_swaps_the_bottle():
    page = (ROOT / "web" / "room.html").read_text()
    assert 'load("room/props_clutter.glb")' in page
    assert 'getObjectByName("bottle")' in page and "PROP.bottle.add(b)" in page
