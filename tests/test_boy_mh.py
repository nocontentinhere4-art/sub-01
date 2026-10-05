"""preview/room-v5: the v5 character with room-mh's room clips and choreography (room/boy_mh.js). Static checks: the
body (room/char_v5.glb) and the clips retargeted onto it (room/mh_v5/, room-mh's names) are in place, the page's marked
motion block switches to room/boy_mh.js for it (through room/char_v5.js), the module encodes the owner's desk rule
(typing for a search, the mouse otherwise, sitting for videos; 0.4 s crossfades), and the licences are recorded."""
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


CLIPS = ("desk_type_ik", "desk_mouse_ik", "desk_watch", "room_window", "room_walk", "room_sit_down", "room_stand_up",
         "room_bed_lie", "room_bed_wake", "room_eat", "room_read", "room_phone", "room_drink", "room_door", "room_bedtime",
         "room_phone_scroll")


def test_body_is_the_v5_rig():
    g = glb_json(WEB / "char_v5.glb")
    names = {n.get("name") for n in g["nodes"]}
    for bone in ("Root", "Hip", "Spine02", "NeckTwist01", "Head", "L_Hand", "R_Hand", "L_Thigh", "L_Foot", "R_ToeBase"):
        assert bone in names, bone
    assert len(g["skins"][0]["joints"]) >= 41                              # (41; more once G13's fingers are in)


def test_room_clips_retargeted_onto_v5():
    have = sorted(p.stem for p in (WEB / "mh_v5").glob("*.glb"))
    assert set(have) <= set(CLIPS), set(have) - set(CLIPS)                  # (room-mh's names, 1:1; G14 drops them in)
    for clip in have:
        g = glb_json(WEB / "mh_v5" / f"{clip}.glb")
        assert g.get("animations"), clip
        ch = g["animations"][0]["channels"]
        targets = {(g["nodes"][c["target"]["node"]]["name"], c["target"]["path"]) for c in ch}
        assert ("Hip", "translation") in targets and ("L_Hand", "rotation") in targets, clip


def test_char_v5_module_maps_to_the_makehuman_names():
    js = (WEB / "char_v5.js").read_text()
    for s in ('Hip: "Hips"', "Thigh`]: `${S}UpLeg`", "Hand`]: `${S}Hand`", "turn.rotation.y = -Math.PI / 2", "turn.attach(hip)", "export function fixClip("):
        assert s in js, s


def test_hook_switches_to_the_module_for_the_makehuman_rig():
    html = (ROOT / "web" / "room.html").read_text()
    assert html.count('import("./room/boy_mh.js")') == 1
    assert 'bones["metacarpal1L"]' in html and '|| V5 ? "mh" : "old"' in html   # (MakeHuman fingers, or v5)
    assert 'load("room/char_v5.glb")' in html and 'clipDir: "room/mh_v5"' in html and "seatUp: 0" in html
    assert "mh.animate(dt)" in html


def test_module_encodes_the_desk_rule():
    js = (WEB / "boy_mh.js").read_text()
    for s in ('"desk_type_ik"', '"desk_mouse_ik"', '"desk_watch"', "search.query", 'kind === "video"', 'kind === "short"',
              '"watch_video"', '"chart"', '"play_chess"', "FADE = 0.4", "function ccd(", "function pin(", "keys.c[1] + 0.003", "P.pad + 0.011"):
        assert s in js, s
    assert "finger" in js and "getObjectByName(\"keyboard\")" in js and "getObjectByName(\"mouse\")" in js   # the fingers are only read; the props swap in


def test_licences_recorded():
    credits = (WEB / "CREDITS.md").read_text()
    assert "Character v5 in the room" in credits and "char_v5.glb" in credits and "mh_v5/" in credits and "Tripo" in credits


def test_props_wired():
    js = (WEB / "boy_mh.js").read_text()
    props = json.loads((WEB / "mh" / "props_g2.json").read_text())
    for k in ("room_eat", "room_read", "room_phone", "room_phone_scroll", "room_drink", "room_door", "room_window", "room_bedtime"):
        assert k in props, k
    assert 'fetch("room/mh/props_g2.json")' in js
