"""The room's mood layer (?mood=1): web/room/mood.js and the day's phases in web/room/window_view.js.

Runs tests/js/mood_check.js in node (no WebGL: createMood is never called) and checks its pure parts: the four day-phase
weights (sum, range, named hours, continuity), hourDelta, fmtHour, lampsByHour, the visitor's choices in storage (defaults
on any storage error, round trip, unknown ids, the key), and the swatch groups and looks. Then the arrange layer
(web/room/mood_arrange.js): spotOK against the room's routes, furniture and stands, skipBlock, loadArrange / saveArrange on
bad storage, and that the NODES / LINKS / BLOCK copied into mood_check.js still match web/room.html. Then static checks on
the text: the page loads mood.js only behind the MOOD flag, mood.js and mood_arrange.js make no network calls and keep
nothing outside localStorage, every localStorage use is inside try, and no other page imports it."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOOD_JS = ROOT / "web" / "room" / "mood.js"
WINDOW_JS = ROOT / "web" / "room" / "window_view.js"
ARRANGE_JS = ROOT / "web" / "room" / "mood_arrange.js"
ROOM = ROOT / "web" / "room.html"
CHECK = ROOT / "tests" / "js" / "mood_check.js"

DEFAULTS = {"floor": "oak", "wall": "chalk", "bed": "indigo", "soft": "mustard", "lamps": "auto", "rays": True, "open": True}
STORE = "sub01.room.mood.v1"


@pytest.fixture(scope="module")
def check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(CHECK)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _room_const(text, name):
    """the body of `const NAME = ...;` (up to the first ';', which none of these literals contains)"""
    found = re.findall(rf"const {name} = ([^;]*);", text)
    assert len(found) == 1, f"expected one `const {name} = ...;`, found {len(found)}"
    return found[0]


def _geometry(name, body):
    """NODES / LINKS / BLOCK as plain Python values, from the JS literal text"""
    if name == "NODES":
        val = {k: [float(x) for x in v.split(",")] for k, v in re.findall(r"(\w+):\[([^\]]*)\]", body)}
    elif name == "LINKS":
        val = [list(pair) for pair in re.findall(r'\["(\w+)",\s*"(\w+)"\]', body)]
    else:
        val = [[float(x) for x in inner.split(",")] for inner in re.findall(r"\[([^\[\]]*)\]", body)]
    return val


def _code_lines(text):
    """the lines that are not whole-line // comments"""
    return [l for l in text.splitlines() if not l.strip().startswith("//")]


# ---- the pure parts, from node ----

def test_day_phase_weights_are_a_partition(check):
    p = check["phase"]
    assert p["steps"] == 97                                      # 0..24 h every 0.25 h, both ends
    assert p["all_weights_ok"], "a weight is outside [0,1] or the name is not a phase"
    assert p["min_weight"] >= 0 and p["max_weight"] <= 1
    assert p["max_sum_error"] < 1e-9, p["max_sum_error"]


def test_day_phase_named_hours(check):
    assert check["phase"]["names"] == {"h8": "morning", "h12_5": "noon", "h18": "evening", "h1": "night", "h23": "night"}


def test_day_phase_is_continuous(check):
    """the largest change of any weight over a quarter hour; a ramp is about 1.5 / 1.2 h wide, so 0.25 h moves it by at
    most ~0.31. Anything near 1 would be a switch rather than a cross-fade."""
    step = check["phase"]["max_step_per_quarter_hour"]
    print(f"\nmax change of a day-phase weight per 0.25 h: {step:.4f} (at h={check['phase']['max_step_at_h']})")
    assert step < 0.35, f"weight jumps {step:.3f} between 0.25 h steps at h={check['phase']['max_step_at_h']}"


def test_hour_delta(check):
    d = check["hourDelta"]
    assert d["a"] == 2 and d["b"] == -2                          # 23 -> 1 is +2 the short way round
    assert d["c"] in (12, -12)                                   # half the clock either way
    assert d["d"] == 0


def test_fmt_hour(check):
    f = check["fmtHour"]
    assert f == {"h0": "00:00", "h13_5": "13:30", "h24": "00:00", "hm1": "23:00"}


def test_lamps_by_hour(check):
    lv = check["lamps"]["values"]
    assert lv["12"] == pytest.approx(0, abs=1e-6)
    assert lv["19"] == pytest.approx(1, abs=1e-6)
    assert lv["0"] == pytest.approx(1, abs=1e-6)
    assert lv["3"] == pytest.approx(0, abs=1e-6)
    assert lv["16"] == pytest.approx(0, abs=1e-6)
    assert check["lamps"]["all_in_range"]


def test_storage_falls_back_to_defaults_when_reading_fails(check):
    s = check["storage"]
    assert s["a_getItem_throws"] == DEFAULTS
    assert s["defaults"] == DEFAULTS


def test_storage_write_failure_returns_false_and_does_not_throw(check):
    assert check["storage"]["b_setItem_throws"] == {"ret": False, "threw": False}


def test_storage_round_trip(check):
    c = check["storage"]["c_round_trip"]
    assert c["ret"] is True
    assert c["loaded"] == c["expected"] == {"floor": "walnut", "wall": "clay", "bed": "rust", "soft": "terra",
                                            "lamps": "on", "rays": False, "open": False}


def test_storage_garbage_gives_defaults(check):
    assert check["storage"]["d_garbage"] == DEFAULTS


def test_storage_unknown_ids_fall_back_per_field(check):
    e = check["storage"]["e_unknown"]
    assert e == DEFAULTS                                         # floor "marble" and lamps "disco" are not options


def test_storage_uses_the_store_key(check):
    f = check["storage"]["f_key"]
    assert f["STORE_KEY"] == STORE and f["used"] is True
    assert check["storage"]["c_keys"] == [STORE]


def test_groups_have_five_variants_each(check):
    for g, info in check["groups"].items():
        assert info["count"] == 5, g
        assert len(set(info["ids"])) == 5, (g, info["ids"])
        assert info["problems"] == [], (g, info["problems"])
    assert set(check["groups"]) == {"floor", "wall", "bed", "soft"}


def test_looks_refer_to_existing_variants(check):
    assert check["looks"]["count"] == 5
    assert check["looks"]["problems"] == []
    assert check["lamp_options"] == ["auto", "on", "off"]


# ---- static checks on the text ----

def test_room_loads_mood_only_behind_the_flag():
    html = ROOM.read_text()
    lines = html.splitlines()
    assert 'const MOOD = !OLD_ROOM && new URLSearchParams(location.search).get("mood") === "1";' in html
    assert "const moodModule = MOOD ? import(\"./room/mood.js\") : null;" in lines
    # every other mention is a whole-line comment: none of them loads the module
    others = [l for l in lines if "mood.js" in l and l.strip() != 'const moodModule = MOOD ? import("./room/mood.js") : null;']
    assert all(l.strip().startswith("//") for l in others), others


def test_mood_js_makes_no_network_calls_and_keeps_nothing_else():
    code = "\n".join(_code_lines(MOOD_JS.read_text()))
    banned = ["fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "navigator.sendBeacon", "/api/", "document.cookie",
              "sessionStorage", "indexedDB"]
    found = [b for b in banned if b in code]
    assert found == [], found


def test_every_local_storage_use_is_inside_try():
    lines = MOOD_JS.read_text().splitlines()
    hits = [i for i, l in enumerate(lines) if "localStorage" in l and not l.strip().startswith("//")]
    assert hits, "expected mood.js to use localStorage (loadChoice / saveChoice)"
    for i in hits:
        window = lines[max(0, i - 6): i + 1]
        assert any(re.search(r"\btry\b", w) for w in window), f"line {i + 1} uses localStorage outside try: {lines[i]!r}"


def test_no_other_page_imports_mood():
    for path in (ROOT / "web").rglob("*"):
        if path.suffix not in (".html", ".js", ".mjs") or path == ROOM:
            continue
        for l in _code_lines(path.read_text(errors="ignore")):
            assert "mood.js" not in l, f"{path.relative_to(ROOT)} references mood.js: {l.strip()!r}"


def test_window_view_phases_are_the_mood_phases():
    src = WINDOW_JS.read_text()
    assert 'export const PHASES = ["morning", "noon", "evening", "night"];' in src
    assert "export function dayPhase(hour)" in src


# ---- the arrange layer (web/room/mood_arrange.js) ----

def test_arrange_copies_match_room_html(check):
    """NODES, LINKS and BLOCK in mood_check.js are the ones web/room.html has now, parsed from both texts with one regex"""
    room = ROOM.read_text()
    js = CHECK.read_text()
    for name in ("NODES", "LINKS", "BLOCK"):
        here = _geometry(name, _room_const(room, name))
        copy = _geometry(name, _room_const(js, name))
        assert here == copy, f"{name} in mood_check.js no longer matches web/room.html"
    # the parser itself: the room has 10 waypoints, 16 links and 6 boxes
    assert len(_geometry("NODES", _room_const(room, "NODES"))) == 10
    assert len(_geometry("LINKS", _room_const(room, "LINKS"))) == 16
    assert len(_geometry("BLOCK", _room_const(room, "BLOCK"))) == 6


def test_arrange_no_accepted_spot_breaks_a_rule(check):
    scan = check["arrange"]["scan"]
    assert set(scan) == {"lamp", "plant", "table", "books", "pouf"}
    for t, v in scan.items():
        assert v["breached"] == 0, f"{t}: {v['breached']} accepted spots break a rule, first {v['first']}"


def test_arrange_scan_grid_and_check_are_not_vacuous(check):
    a = check["arrange"]
    assert a["grid"] == [75, 59]                    # 0.05 m over BOUNDS, both ends in
    assert a["flagged"] > 0                         # the independent rules do reject spots


def test_arrange_each_type_has_room(check):
    counts = {t: v["accepted"] for t, v in check["arrange"]["scan"].items()}
    print(f"\naccepted spots per type: {counts}")
    for t, n in counts.items():
        assert n > 20, f"{t}: only {n} accepted spots"


def test_arrange_skip_block_leaves_out_exactly_one_box(check):
    skip = check["arrange"]["skip"]
    for k, v in skip.items():
        assert v["notMonotone"] == 0, (k, v)        # leaving a box out never takes a spot away
        assert v["breachedWithout"] == 0, (k, v)    # and the spots it lets through break no other rule
        assert v["newlyOutsideBox"] == 0, (k, v)    # a spot newly accepted lies in that box (grown by r + 3 cm)
        assert v["newlyOtherRule"] == 0, (k, v)
    assert any(v["newlyAccepted"] > 0 for k, v in skip.items() if k != "-1"), "no box ever changes the answer"


def test_arrange_spot_ok_rejects_nan(check):
    assert check["arrange"]["nan"] == [False, False, False, False]


def test_arrange_spot_ok_respects_others(check):
    o = check["arrange"]["others"]
    assert o["witness"] is not None and o["free"] is True
    assert o["near"] is False                       # 0.3 m from another thing of radius 0.2: overlapping
    assert o["far"] is True                         # 0.6 m away: clear


def test_arrange_load_falls_back_on_bad_storage(check):
    load = check["arrange"]["load"]
    empty = {"plant": None, "items": []}
    for k in ("throwing_get", "garbage", "null_json", "no_storage"):
        assert load[k] == empty, k


def test_arrange_load_drops_unknown_types_and_non_finite_numbers(check):
    load = check["arrange"]["load"]
    assert load["unknown_types"] == {"plant": None, "items": [["lamp", 0.5, 0.5, 0]]}
    assert load["non_finite"] == {"plant": None, "items": [["books", 0.2, 0.3, 0]]}
    assert load["plant_bad"] == {"plant": None, "items": []}
    assert load["plant_extra"] == {"plant": [0.1, 0.2, 0.3], "items": []}


def test_arrange_load_truncates_to_max_items(check):
    a = check["arrange"]
    items = a["load"]["truncated"]["items"]
    assert a["limits"]["MAX_ITEMS"] == 10
    assert len(items) == a["limits"]["MAX_ITEMS"]
    assert [it[1] for it in items] == pytest.approx([i * 0.1 for i in range(10)])   # the first ten, in order


def test_arrange_round_trip_and_key(check):
    a = check["arrange"]
    r = a["round"]
    assert r["ret"] is True
    assert r["loaded"] == r["expected"]
    assert r["keys"] == [a["key"]] == ["sub01.room.arrange.v1"]


def test_arrange_save_returns_false_when_storage_throws(check):
    assert check["arrange"]["save_throws"] is False


def _storage_uses_outside_try(path):
    lines = path.read_text().splitlines()
    bad = []
    for i, l in enumerate(lines):
        if "localStorage" in l and not l.strip().startswith("//"):
            window = lines[max(0, i - 6): i + 1]
            if not any(re.search(r"\btry\b", w) for w in window):
                bad.append((i + 1, l.strip()))
    return bad


def test_mood_arrange_makes_no_network_calls_and_keeps_nothing_else():
    code = "\n".join(_code_lines(ARRANGE_JS.read_text()))
    banned = ["fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "/api/", "document.cookie"]
    found = [b for b in banned if b in code]
    assert found == [], found


def test_every_arrange_local_storage_use_is_inside_try():
    lines = ARRANGE_JS.read_text().splitlines()
    assert any("localStorage" in l and not l.strip().startswith("//") for l in lines), "expected localStorage use"
    assert _storage_uses_outside_try(ARRANGE_JS) == []
