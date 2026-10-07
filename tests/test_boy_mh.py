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
# the Mixamo captures retargeted onto v5 (docs/design/mixamo): one row each in room_build/kimodo/mixamo_clips.json
MIXAMO = tuple(r["out"] for r in json.loads((ROOT / "room_build" / "kimodo" / "mixamo_clips.json").read_text())["clips"].values())
EXTRA = ("room_bed_music_in", "room_bed_music", "room_bed_music_out", "room_laying_nodding", "room_laying_sleeping", "room_sleeping_idle",
         "room_sleep_turn")   # (optional clips, loaded when present)


def test_body_is_the_v5_rig():
    g = glb_json(WEB / "char_v5.glb")
    names = {n.get("name") for n in g["nodes"]}
    for bone in ("Root", "Hip", "Spine02", "NeckTwist01", "Head", "L_Hand", "R_Hand", "L_Thigh", "L_Foot", "R_ToeBase"):
        assert bone in names, bone
    assert len(g["skins"][0]["joints"]) >= 41                              # (41; more once G13's fingers are in)


def test_room_clips_retargeted_onto_v5():
    have = sorted(p.stem for p in (WEB / "mh_v5").glob("*.glb"))
    assert set(have) <= set(CLIPS) | set(MIXAMO) | set(EXTRA), set(have) - set(CLIPS) - set(MIXAMO) - set(EXTRA)   # (room-mh's names, 1:1, the Mixamo rows and the optional clips)
    assert set(CLIPS) <= set(have), set(CLIPS) - set(have)                  # (every required clip is there: boy_mh.js load() throws without one)
    for clip in have:
        g = glb_json(WEB / "mh_v5" / f"{clip}.glb")
        assert g.get("animations"), clip
        ch = g["animations"][0]["channels"]
        targets = {(g["nodes"][c["target"]["node"]]["name"], c["target"]["path"]) for c in ch}
        assert ("Hip", "translation") in targets and ("L_Hand", "rotation") in targets, clip


def test_bed_captures_wired_and_rebakeable():
    # G17 (docs/design/bed-clips): the bed captures the page loads are on disk, and one command re-bakes them
    js = (WEB / "boy_mh.js").read_text()
    for k, f in (("music", "room_laying_nodding"), ("sleep_loop", "room_laying_sleeping"), ("sleep_turn", "room_sleep_turn")):
        assert f'{k}: "{f}"' in js, k
        assert (WEB / "mh_v5" / f"{f}.glb").exists(), f
    bed = json.loads((ROOT / "room_build" / "kimodo" / "mixamo_clips.json").read_text())["bed"]
    assert bed["turn"]["out"] == "room_sleep_turn" and bed["turn"]["loop"] == "Laying_Sleeping"
    sh = ROOT / "room_build" / "kimodo" / "bed_rebake.sh"
    assert sh.exists() and sh.stat().st_mode & 0o111
    # the captured bed clips rest ON the bed (the page's lift both ways for them), and the turn starts at the loop's wrap
    assert "function capBed(" in js and "measureLift(2, cap)" in js and "function sleepTurn(" in js


def test_char_v5_module_maps_to_the_makehuman_names():
    js = (WEB / "char_v5.js").read_text()
    for s in ('Hip: "Hips"', "Thigh`]: `${S}UpLeg`", "Hand`]: `${S}Hand`", "turn.rotation.y = -Math.PI / 2", "sc.attach(hip)", "export function fixClip("):
        assert s in js, s


def test_hook_switches_to_the_module_for_the_makehuman_rig():
    html = (ROOT / "web" / "room.html").read_text()
    assert html.count('import("./room/boy_mh.js")') == 1
    assert 'bones["metacarpal1L"]' in html and '|| V5 ? "mh" : "old"' in html   # (MakeHuman fingers, or v5)
    assert 'load("room/char_v5.glb")' in html and 'clipDir: "room/mh_v5"' in html and "seatUp: 0" in html
    assert "mh.animate(dt)" in html


def _js_function(js, head):
    """The source of one function in the module, from its head to its matching brace."""
    i = js.index(head); j = js.index("{", i); depth = 0
    for k in range(j, len(js)):
        depth += {"{": 1, "}": -1}.get(js[k], 0)
        if depth == 0:
            return js[i:k + 1]
    raise AssertionError(head)


# runs the module's own desk rule (wanted) and its per-frame hand dispatch (hands) in node, against stubs: which mode
# each screen gives, and which hand code runs in each mode
DESK_RULE_JS = r"""
const SRC = JSON.parse(process.env.DESK_RULE_SRC);
const out = {};
// 1. wanted(st): the screen -> the desk mode
{ const M = {lastScreen: null, typeUntil: 0};
  const wanted = new Function("M", SRC.wanted + "; return wanted;")(M);
  const st = (act, screen, T = 0, at = "desk") => ({at, step: null, T, life: {activity: act, screen}});
  out.search = wanted(st("research", {id: "s1", kind: "page", search: {query: "ramen near kichijoji"}}, 0));
  out.searchLater = wanted(st("research", {id: "s1", kind: "page", search: {query: "ramen near kichijoji"}}, 60));
  out.chart = wanted(st("chart", {id: "c1", kind: "page"}, 61));
  out.video = wanted(st("watch_video", {id: "v1", kind: "video"}, 62));
  out.short = wanted(st("research", {id: "v2", kind: "short"}, 63));
  out.away = wanted(st("research", {id: "s2", kind: "page", search: {query: "x"}}, 64, "bed")); }
// 2. hands(dt): which hand code runs per mode (any vector op is a no-op stub)
const calls = [];
const vec = () => new Proxy(function () {}, {get: (t, p) => p === "x" || p === "y" || p === "z" ? 0 : p === "distanceTo" ? () => 0.07 : () => vec(), apply: () => vec()});
const rec = name => (...a) => { calls.push([name, a[0], a[3] && a[3].rest ? "rest" : ""]); };
function run(mode, frames) {
  calls.length = 0;
  const M = {mode, w: {type: 0, mouse: 0}, noIK: false};
  const env = {boy: {updateMatrixWorld() {}, rotation: {y: 0}}};
  const P = {keys: {c: [0, 0, 0]}, kbNode: {}, mouseNode: {}, mouse: [0, 0, 0]};
  const OT = {json: {speed: 0.75}, t: 0, tr: 0};
  const deps = {M, env, P, OT, OT_REST: 0.2, HUMP: 0.02, CLIP: {mouse: [0, 0, 0]}, V: vec, _k: vec(), _c: vec(), _a: vec(), dK: vec(),
    toWorld: () => vec(), kbRef: () => [0, 0, 0], fwdV: () => vec(), S: () => vec(),
    ownerKeys: rec("ownerKeys"), keyOn: rec("keyOn"), pin: () => {}, follow: () => {}, mouseHold: rec("mouseHold"),
    omStep: rec("omStep"), omNow: () => ({move: [0, 0]})};
  const names = Object.keys(deps);
  const hands = new Function(...names, SRC.kCtx + "; " + SRC.hands + "; return hands;")(...names.map(n => deps[n]));
  for (let i = 0; i < frames; i++) hands(1 / 30);
  const by = {}; for (const [n, side, o] of calls) { const k = n + (side && typeof side === "string" ? ":" + side : "") + (o ? ":" + o : ""); by[k] = (by[k] || 0) + 1; }
  return by;
}
out.typing = run("desk_type", 60);
out.mousing = run("desk_mouse", 60);
console.log(JSON.stringify(out));
"""


def test_module_encodes_the_desk_rule():
    """The owner's desk rule, run from the module itself: a search he is typing -> typing, a chart (anything else at the
    desk) -> the mouse, a video -> sitting back; and in each mode the owner-driven hands run - typing: both hands from his
    typing take (ownerKeys), never the old capture path (keyOn); mousing: the right hand from his mouse take (mouseHold,
    stepping it), the left at rest on the keys from his typing take."""
    import shutil
    import subprocess
    import pytest
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    js = (WEB / "boy_mh.js").read_text()
    src = {"wanted": _js_function(js, "function wanted(st)"), "hands": _js_function(js, "function hands(dt)"),
           "kCtx": next(line.strip() for line in js.splitlines() if line.strip().startswith("const kCtx ="))}
    import os
    r = subprocess.run([node, "-e", DESK_RULE_JS], capture_output=True, text=True, timeout=60, env={**os.environ, "DESK_RULE_SRC": json.dumps(src)})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["search"] == "desk_type", out                      # (typing for a search he has just typed)
    assert out["searchLater"] == "desk_mouse", out                # (then back to the mouse)
    assert out["chart"] == "desk_mouse" and out["video"] == "desk_watch" and out["short"] == "desk_watch" and out["away"] is None, out
    t, m = out["typing"], out["mousing"]
    assert t.get("ownerKeys:Left", 0) > 30 and t.get("ownerKeys:Right", 0) > 30, t   # (both hands: the owner's typing)
    assert not any(k.startswith(("keyOn", "mouseHold", "omStep")) for k in t), t
    assert m.get("mouseHold", 0) > 30 and m.get("omStep", 0) > 30, m                  # (the right hand: the owner's mouse take)
    assert m.get("ownerKeys:Left:rest", 0) > 30, m                                    # (the left hand at rest on the keys)
    assert not any(k.startswith("keyOn") or k == "ownerKeys:Right" or k == "ownerKeys:Left" for k in m), m
    assert "const FADE = 0.4;" in js                                                  # (0.4 s crossfades between the modes)
    assert 'fetch("room/mh/owner_typing.json")' in js and 'fetch("room/mh/owner_mouse.json")' in js   # (the takes the page drives)
    for f in ("web/room/mh/owner_typing.json", "web/room/mh/owner_mouse.json"):
        assert (ROOT / f).is_file(), f


def test_licences_recorded():
    credits = (WEB / "CREDITS.md").read_text()
    assert "Character v5 in the room" in credits and "char_v5.glb" in credits and "mh_v5/" in credits and "Tripo" in credits


def test_props_wired():
    js = (WEB / "boy_mh.js").read_text()
    props = json.loads((WEB / "mh" / "props_g2.json").read_text())
    for k in ("room_eat", "room_read", "room_phone", "room_phone_scroll", "room_drink", "room_door", "room_window", "room_bedtime"):
        assert k in props, k
    assert 'fetch("room/mh/props_g2.json")' in js
