"""G22 (preview/standing-clips): the standing and in-between Mixamo captures baked for the Mixamo-rigged character
(web/room/char_mixamo.glb). Static checks: every row of room_build/kimodo/standing_clips.json has its baked clip under
web/room/mx_standing/ on the character's own skeleton (bone names, the hips' travel only), with its fit in
standing_clips.meta.json; no raw capture is in the web tree; and the page runs the preview only with ?char=mixamo&clip=,
so the default page is unchanged."""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "room"
ROWS = json.loads((ROOT / "room_build" / "kimodo" / "standing_clips.json").read_text())["clips"]
META = json.loads((WEB / "mx_standing" / "standing_clips.meta.json").read_text())


def glb_json(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n])


def test_the_nine_clips():
    assert set(ROWS) == {"Texting_While_Standing", "Standing_Using_Touchscreen_Tablet", "Standing_Clap", "Angry_Gesture", "Scared",
                         "Stand_To_Sit", "Sit_To_Stand", "Gaming", "Texting"}
    assert set(META) == set(ROWS)


def test_baked_on_the_characters_skeleton():
    char = {n.get("name") for n in glb_json(WEB / "char_mixamo.glb")["nodes"]}
    for clip in ROWS:
        g = glb_json(WEB / "mx_standing" / f"{clip}.glb")
        names = [n.get("name") for n in g["nodes"]]
        assert "mixamorig:Hips" in names and set(names) - {"mixamo"} <= char, clip
        ch = g["animations"][0]["channels"]
        paths = {(names[c["target"]["node"]], c["target"]["path"]) for c in ch}
        assert [p for p in paths if p[1] == "translation"] == [("mixamorig:Hips", "translation")], clip   # (only the hips travel)
        assert sum(1 for p in paths if p[1] == "rotation") >= 50, clip                                  # (fingers included)
        assert not any(c["target"]["path"] == "scale" for c in ch), clip


def test_the_fit_is_recorded():
    for clip, row in ROWS.items():
        m = META[clip]
        assert m["frames"] > 30 and m["hip_scale"] > 0.8, clip
        for s in "LR":
            assert m["soles_cm"][s][0] >= 0.0, (clip, s, m["soles_cm"])                 # (no sole under the floor in the bake)
            assert m["leg_ik_miss_cm"][s] < 1.0, (clip, s)
            assert m["hands_in_thighs_after"][s][0] == 0, (clip, s, m["hands_in_thighs_after"])   # (the bake's own self-contact test)
        if row["kind"] != "standing":
            assert m["seated_frames"] > 0 and abs(m["seat_hip_y"] - 0.71) < 0.03, clip    # (the hips seated on OUR cushion)


def test_no_raw_capture_in_the_web_tree():
    assert not list((ROOT / "web").rglob("*.fbx"))
    assert not list((ROOT / "web").rglob("*.bvh"))


def test_preview_only_with_its_parameters():
    html = (ROOT / "web" / "room.html").read_text()
    block = html[html.index("// ===== G22:"):html.index("// ===== end G22 =====")]
    assert 'q.get("char") === "mixamo" && q.get("clip")' in block
    assert re.search(r"if \(CLIP && /\^\[A-Za-z_\]\+\$/\.test\(CLIP\)\)", block)              # (a clip name, nothing else, goes into the URL it loads)
    js = (WEB / "standing_preview.js").read_text()
    assert "room/mx_standing/" in js and "char_mixamo.glb" in js
