"""preview/room-mh: the MakeHuman body with real mocap at the desk (#98). Static checks: the body and the clips are in
place, the page's marked motion block switches to room/boy_mh.js for the MakeHuman rig, the module encodes the owner's
desk rule (typing for a search, the mouse otherwise, sitting for videos; 0.4 s crossfades; fingers as recorded), and the
licences are recorded."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "room"


def glb_json(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n])


def test_body_is_the_makehuman_rig():
    g = glb_json(WEB / "boy.glb")
    names = {n.get("name") for n in g["nodes"]}
    for bone in ("Hips", "Spine", "Head", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "metacarpal1.L", "finger3-1.R"):
        assert bone in names, bone
    assert len(g["skins"][0]["joints"]) == 163


def test_desk_clips_animate_the_fingers():
    for clip in ("desk_type_ik", "desk_mouse_ik", "desk_watch", "room_window", "room_walk", "room_sit_down",
                 "room_stand_up", "room_bed_lie", "room_bed_wake", "room_eat", "room_read", "room_phone", "room_drink",
                 "room_door", "room_bedtime", "room_phone_scroll"):
        g = glb_json(WEB / "mh" / f"{clip}.glb")
        assert g.get("animations"), clip
        targets = {g["nodes"][c["target"]["node"]]["name"] for c in g["animations"][0]["channels"]}
        assert "Hips" in targets and "LeftHand" in targets, clip
        assert any(t.startswith("finger3-") for t in targets), clip       # the recorded fingers


def test_hook_switches_to_the_module_for_the_makehuman_rig():
    html = (ROOT / "web" / "room.html").read_text()
    assert html.count('import("./room/boy_mh.js")') == 1
    assert 'bones["metacarpal1L"]' in html                                 # (three.js drops the dot from node names)
    assert "mh.animate(dt)" in html


def test_module_encodes_the_desk_rule():
    js = (WEB / "boy_mh.js").read_text()
    for s in ('"desk_type_ik"', '"desk_mouse_ik"', '"desk_watch"', "search.query", 'kind === "video"', 'kind === "short"',
              '"watch_video"', '"chart"', '"play_chess"', "FADE = 0.4", "function ccd(", "function pin(", "keys.c[1] + 0.003", "P.pad + 0.011"):
        assert s in js, s
    assert "finger" in js and "getObjectByName(\"keyboard\")" in js and "getObjectByName(\"mouse\")" in js   # the fingers are only read; the props swap in


def test_licences_recorded():
    credits = (WEB / "CREDITS.md").read_text()
    assert "MakeHuman" in credits and "CC0" in credits and "Anderson Rohr" in credits


def test_props_and_correctives_wired():
    js = (WEB / "boy_mh.js").read_text()
    props = json.loads((WEB / "mh" / "props_g2.json").read_text())
    for k in ("room_eat", "room_read", "room_phone", "room_phone_scroll", "room_drink", "room_door", "room_window", "room_bedtime"):
        assert k in props, k
    assert 'fetch("room/mh/props_g2.json")' in js and "morphTargetInfluences" in js and "correctives" in js
    g = glb_json(WEB / "boy.glb")
    assert set(g["extras"]["correctives"]["drivers"]) == {"seated", "elbow_L", "elbow_R", "lying"}
