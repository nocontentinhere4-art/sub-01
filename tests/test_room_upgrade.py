"""preview/room-upgrade: the new office chair, the picked props and the sneakers, the clothes taken out."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "room.html").read_text()


def glb(name):
    data = (ROOT / "web" / "room" / name).read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    return data, json.loads(data[20:20 + n])


def tris(j):
    return sum(j["accessors"][p["indices"]]["count"] // 3 for m in j["meshes"] for p in m["primitives"])


def test_office_chair_seat_is_052_and_light():
    data, j = glb("chair_office.glb")
    assert len(data) <= 1024 * 1024 and 0 < tris(j) <= 40000
    node = next(nd for nd in j["nodes"] if nd.get("name") == "chair_office")
    assert node["extras"]["seatTop"] == 0.52 and abs(node["extras"]["seatAt"][1] - 0.52) < 1e-4
    names = {nd.get("name") for nd in j["nodes"]}
    for part in ("cushion", "back_frame", "back_mesh", "arms", "base", "casters"):
        assert "chair_" + part in names                                          # (one closed mesh per part)
    assert 'load("room/chair_office.glb")' in HTML and "n.userData.raised = true" in HTML   # (not lifted again by raiseChair)


def test_picked_props_only_the_approved_ones():
    data, j = glb("props_picked.glb")
    mats = {m["name"] for m in j["materials"]}
    assert mats <= {"wicker_basket_02", "wooden_bowl_02", "brass", "leather", "connector", "binder_notebook", "stationery_supplies"}
    assert {"wicker_basket_02", "wooden_bowl_02", "binder_notebook", "stationery_supplies"} <= mats
    assert len(data) <= 2 * 1024 * 1024 and 'load("room/props_picked.glb")' in HTML


def test_sneakers_by_the_door():
    data, j = glb("sneakers_door.glb")
    assert {m["name"] for m in j["materials"]} == {"painted", "jersey"} and 0 < tris(j) <= 8000
    assert 'load("room/sneakers_door.glb")' in HTML


def test_rejected_clothes_taken_out():
    for m in ("hang_hoodie", "hang_rib", "denim", "cushion", "jersey"):
        assert f'"{m}"' in HTML.split("const UPGRADE_DROP", 1)[1].split("\n\n", 1)[0]
