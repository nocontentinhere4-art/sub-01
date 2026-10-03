"""The character (#98 G2): web/room/boy.glb keeps the rig the clips and room.html depend on, stays within its budgets,
and carries the eye and eyelid nodes documented for the motion layer. Reads only the GLB's JSON chunk (the meshes are
meshopt-compressed; the build is room_build/boy_asset/)."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLB = ROOT / "web" / "room" / "boy.glb"
BONES = ["Hips", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase",
         "Spine02", "Spine01", "Spine", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "RightShoulder", "RightArm",
         "RightForeArm", "RightHand", "neck", "Head", "head_end", "headfront"]


def gltf():
    data = GLB.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    n, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + n])


def test_size_budget():
    assert GLB.stat().st_size <= 3 * 1024 * 1024


def test_rig_unchanged():
    g = gltf()
    skin = g["skins"][0]
    names = [g["nodes"][j]["name"] for j in skin["joints"]]
    assert names == BONES                                        # same 24 joints, same order (the clips bind by name)
    hips = g["nodes"][skin["joints"][0]]
    assert [round(x, 3) for x in hips["translation"]] == [-0.46, 91.896, 1.802]   # rest pose of the root
    assert any(n.get("name") == "char1" and "skin" in n for n in g["nodes"])


def test_sit_clip_kept():
    g = gltf()
    assert len(g["animations"]) == 1
    assert g["animations"][0]["name"].startswith("Armature|Chair_Sit_Idle")
    assert len(g["animations"][0]["channels"]) == 72


def test_triangle_budget_and_primitive_order():
    g = gltf()
    body = next(m for m in g["meshes"] if m["name"] == "char1")
    mats = [g["materials"][p["material"]]["name"] for p in body["primitives"]]
    assert mats[0] == "boy_skin"                                 # room.html's handVertices takes the first skinned mesh
    assert mats == ["boy_skin", "boy_hair", "boy_hoodie", "boy_pants", "boy_socks", "boy_slides"]
    tris = 0
    for m in g["meshes"]:
        for p in m["primitives"]:
            tris += g["accessors"][p["indices"]]["count"] // 3
    assert tris <= 80_000
    for p in body["primitives"]:
        assert {"POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"} <= set(p["attributes"])
    # the LAST skinned mesh is his whole body to room.html's bed code (bedInit, slidesInit): the slides primitive carries
    # an invisible low-poly proxy of the body (alpha-masked texels), so it has far more vertices than the slides alone
    last = body["primitives"][-1]
    assert g["accessors"][last["attributes"]["POSITION"]]["count"] > 5000
    assert g["materials"][last["material"]].get("alphaMode") == "MASK"


def test_eye_nodes_under_the_head():
    g = gltf()
    by_name = {n.get("name"): i for i, n in enumerate(g["nodes"])}
    head = g["nodes"][by_name["Head"]]
    kids = {g["nodes"][c]["name"] for c in head.get("children", [])}
    assert {"LeftEye", "RightEye", "LeftEyelid", "RightEyelid", "head_end", "headfront"} <= kids
    for side in ("Left", "Right"):
        eye = g["nodes"][by_name[side + "Eye"]]
        ball = g["nodes"][eye["children"][0]]
        assert "mesh" in ball and "skin" not in ball            # plain meshes that follow the Head joint; rotate the node to look
        assert g["materials"][g["meshes"][ball["mesh"]]["primitives"][0]["material"]]["name"] == "boy_eye"
    skin_mat = next(m for m in g["materials"] if m["name"] == "boy_skin")
    assert skin_mat.get("alphaMode") == "MASK"                    # the eye openings are cut out of the face
