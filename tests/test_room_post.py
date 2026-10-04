"""The room's rendering layer (#98 G6, web/room_post.js): the module loads (node, a THREE stub, stub passes), each
quality tier's pass chain, the clean fallbacks (a pass whose import fails is left out, no composer or no WebGL2 means
plain rendering, a render that throws turns the chain off for good), the adaptive governor (resolution first, then a tier
down after slow frames, back up after fast ones, a failed tier retried later), the device detection, the grade per time of
day, the environment-map class per material, shadow-map texel snapping, the sun shafts, the contact shadow and the
captured room environment. Plus the page: room.html imports the module, maps n8ao in its import map, and credits it.
The pixels are checked by hand with tests/room_render_shots.py (headless Chromium, software WebGL)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "web" / "room_post.js"
PAGE = ROOT / "web" / "room.html"
HOURS = (8, 14, 19, 23)


@pytest.fixture(scope="module")
def check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(ROOT / "tests" / "js" / "room_post_check.js")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_module_loads_and_tiers(check):
    assert check["tiers"] == ["low", "medium", "high"]
    C = check["chains"]
    assert C["high"]["chain"] == ["ao", "dof", "grade", "smaa"] and C["high"]["mode"] == "composer" and C["high"]["active"]
    assert C["medium"]["chain"] == ["render", "grade"] and C["medium"]["aa"] == "msaa"                 # phones: one post pass over a 4x MSAA target
    assert C["medium"]["msaa"] and not C["high"]["msaa"] and not C["high"]["halfRes"]
    assert not C["high"]["bloom"] and not C["medium"]["bloom"]                                            # owner: no stylised bloom or glow
    assert C["low"]["chain"] == [] and C["low"]["mode"] == "direct" and not C["low"]["active"] and C["low"]["aa"] == "msaa"
    assert C["high"]["shadow"] == 2048 and C["medium"]["shadow"] == 1024 and C["low"]["shadow"] == 1024
    assert C["high"]["hdr"] and C["medium"]["hdr"] and not C["low"]["hdr"]
    assert not C["low"]["env"] and not C["low"]["shafts"] and C["medium"]["env"] and C["medium"]["shafts"]
    assert C["high"]["dof_on"] and not C["high"]["dof_off"] and C["high"]["depth_from"] == "n8ao-depth"   # the depth N8AO already drew
    assert C["high"]["grade_exposure"] == 0.9                                                             # the renderer's exposure reaches the grade
    assert C["high"]["grade_grain"] > 0 and C["medium"]["grade_grain"] == 0                               # grain only on the high tier
    S = C["sizes"]
    assert S["composer"] == [1280, 800] and S["pr"] == 1.5 and S["rt"] == [1920, 1200]
    assert abs(S["fxaa"]["x"] - 1 / 1920) < 1e-9 and abs(S["fxaa"]["y"] - 1 / 1200) < 1e-9


def test_fallbacks(check):
    F = check["fallbacks"]
    assert F["no_ao"]["chain"] == ["render", "dof", "grade", "smaa"] and F["no_ao"]["failed"] == ["ao"] and F["no_ao"]["mode"] == "composer"
    assert F["no_ao"]["depth_from_rt"]                                     # without N8AO the depth comes from the composer's own target
    assert F["no_aa"]["chain"] == ["ao", "dof", "grade"] and F["no_aa"]["aa"] is None
    B = F["bloom_opt"]                                                     # opt-in only: a faint veil, threshold well above white
    assert B["high"] == ["ao", "bloom", "dof", "grade", "smaa"] and B["medium"] == ["render", "bloom", "grade"] and B["low"] == []
    assert B["strength"] <= 0.15 and B["threshold"] >= 1.5
    assert not F["no_composer"]["active"] and F["no_composer"]["mode"] == "direct" and F["no_composer"]["direct"] == 1
    assert "EffectComposer" in F["no_composer"]["failed"] and F["no_composer"]["aa"] == "msaa"
    assert F["render_throws"] == {"first": "direct", "second": "direct", "direct": 2, "broken": True, "active": False}
    assert not F["no_webgl2"]["active"] and F["no_webgl2"]["mode"] == "direct" and F["no_webgl2"]["failed"] == "no WebGL2"
    assert F["no_half_float"]["rtType"] == "byte" and F["no_half_float"]["active"]


def test_governor_switches_tiers(check):
    G = check["governor"]
    assert G["slow_with_dpr_left"] == []                                   # while the page can lower its pixel ratio: no tier change
    assert [t for _, t in G["slow"]] == ["medium", "low"] and G["tier_after_slow"] == "low"
    assert G["slow"][0][0] < 60 and G["slow"][1][0] < 110                 # ~2 windows of a second each per step at 40 ms a frame
    assert G["fast_short"] == []                                           # a tier that just failed is not retried at once
    assert [t for _, t in G["fast_retry"]][:1] == ["medium"] and G["tier_after_fast"] in ("medium", "high")
    assert G["hitch_ignored"] == [] and G["hidden_tab"]


def test_device_detection(check):
    D = check["detect"]
    assert D["desktop_nvidia"] == "high" and D["desktop_apple"] == "high" and D["no_info_desktop"] == "high"
    assert D["desktop_intel_uhd620"] == "medium"
    assert D["iphone"] == "medium" and D["android_mid"] == "medium" and D["no_info_phone"] == "medium"
    assert D["android_weak"] == "low" and D["android_adreno610"] == "low"
    assert D["software"] == "low"


def test_grade_per_time_of_day(check):
    G = check["grade"]
    m, n, e, nt = G["8"], G["14"], G["19"], G["23"]
    assert m["balance"][0] > m["balance"][2]                               # morning: warm
    assert n["balance"][2] >= n["balance"][0] and n["contrast"] >= m["contrast"]   # midday: neutral-cool, crisp
    assert e["highs"][0] > e["highs"][2] and e["shadows"][2] > e["shadows"][0]     # evening with the lamp: warm highlights, teal shadows
    assert nt["balance"][2] > nt["balance"][0] and nt["sat"] < m["sat"] and nt["vignette"] > m["vignette"] and nt["lift"] > m["lift"]   # night: cool, muted, heavier vignette, lifted blacks
    assert 0.25 <= min(x["vignette"] for x in (m, n, e, nt)) and max(x["vignette"] for x in (m, n, e, nt)) <= 0.55
    assert all(0.8 <= x["sat"] <= 1.2 and 1.0 <= x["contrast"] <= 1.15 for x in (m, n, e, nt))
    assert G["continuous"] < 0.02 and G["wraps"]                           # no jump at any minute of the day, midnight wraps


def test_env_class_per_material(check):
    E = check["env"]
    assert E["wall_clock_glass"] == 1.0 and E["screen"] == 1.0
    assert E["steel"] == E["metal_dark"] == 0.9
    assert E["plastic_black"] == E["desk_lamp_arm_01"] == 0.45
    assert E["oak"] == E["floor"] == 0.35 and E["wall"] == 0.2
    assert E["duvet"] == E["curtain"] == E["rug"] == E["hp_pad"] == E["chair_fabric_black"] == E["potted_plant_02_leaves"] == 0.1
    assert E["unknown_thing"] == 0.3 and E["(empty)"] == 0.3


def test_shadow_snapping_shafts_blob_env(check):
    S = check["snap"]
    assert S["moved_under_texel"] and S["on_grid"] and S["dir_same"] and S["second_call_zero"] and S["bad_map"] == 0
    H = check["shafts"]
    assert H["slices"] == 12 and H["panes"] == 2 and H["inside_room"] and H["descending"] and H["on_beam"] and H["ordered"]
    assert H["visible"] and H["uStrength"] == 0.5 and H["hidden_when_zero"] and 2.0 <= H["max_depth"] <= 2.6
    B = check["blob"]
    assert B["on"] == 1 and abs(B["on_opacity"] - 0.5) < 1e-6 and 0.5 < B["lifted"] < 0.7 and B["hanging"] == 0 and B["hidden"] == 0
    assert abs(B["y"] - 0.164) < 1e-6 and not B["visible_hanging"]
    R = check["roomenv"]
    assert R["first"] and not R["again"] and R["changed"] and R["captures"] == 3 and R["updates"] == 4   # 4 cube renders, 3 kept (one NaN capture dropped)
    assert R["hidden_during"] == [False, True] and R["restored"] and R["has_texture"]
    assert R["nan_rejected"] and R["key_kept"] and R["rejected"] == 1 and R["retried"] and R["env_off_during"] and R["env_restored"]   # a NaN capture is dropped and retried; no feedback through the environment


def test_page_wires_the_module():
    html = PAGE.read_text()
    assert 'from "./room_post.js"' in html
    im = re.search(r'<script type="importmap">(.*?)</script>', html, re.S).group(1)
    imports = json.loads(im)["imports"]
    assert imports["n8ao"].startswith("https://cdn.jsdelivr.net/npm/n8ao@") and imports["three/examples/jsm/"] == imports["three/addons/"]
    assert imports["postprocessing"].startswith("data:text/javascript,")       # N8AO's optional base class: a one-line shim, not the 300 KB package
    for host in re.findall(r'https?://([\w.-]+)/', im):
        assert host == "cdn.jsdelivr.net", host                                  # only the CDN the page already used
    assert "post.render(" in html and "renderer.render(scene, camera)" not in html.split("function frame(now)")[1]
    assert "post.frame(now - frameAt" in html and "post.setSize(w, h, dpr)" in html
    assert "gradeAt(hour" in html and "snapShadow(THREE, sun" in html and "new SunShafts(" in html and "new ContactBlob(" in html and "roomEnv.update(" in html
    assert "new THREE.SpotLight(" in html                                       # the desk lamp: one shadow map instead of six
    assert "darken(m); m.needsUpdate = true" in html and "m.specularIntensity = 0.45" in html   # black cloth stays black by day (tests/visual/test_black_cloth.py measures it)
    assert "THREE.AgXToneMapping" in html and "vec3 agx(" in JS.read_text()        # the same film-like curve on both paths
    cam = html.split("function updateCameraGoal")[1].split("// ---------- day and night")[0]
    for kind in ('"face"', '"screen"', '"medium"', '"over"', '"overview"'):       # the camera shots (G8 #10, #18)
        assert kind in cam, kind
    lists = re.findall(r'\[((?:"\w+", )*"\w+")\]', cam.split("const list =")[1].split(";")[0])
    assert len(lists) >= 4 and all('"overview"' in l for l in lists)            # the overview is in every cycle (the phone's desk cycle has no screen shot) ...
    assert 'narrow ? ["face", "medium", "overview"]' in cam and "0.12 * camGoal.pos.distanceTo(camGoal.target)" in cam   # a phone held upright: no back-of-head shot, him in the lower middle
    assert "holdOf(CAM.kind, list)" in cam and "0.75 * list.reduce" in html      # ... and holds >= 40 % of it (0.75 / 1.75)
    assert "CAM.cut" in html.split("function frame(now)")[1]
    assert 'CAM.force = pinned ? "overview" : null' in html                      # the chip: the cycle, or the overview pinned
    assert "post.focus(cd, smooth(2.4, 1.0, cd) * (atScreen ? 0.25 : 1))" in html   # the page on the monitor stays readable in the desk close-ups
    assert JS.stat().st_size < 60 * 1024


def test_credits_and_docs():
    credits = (ROOT / "web" / "room" / "CREDITS.md").read_text()
    assert "N8AO" in credits and "ISC" in credits
    doc = ROOT / "docs" / "design" / "room-render"
    assert (doc / "README.md").exists()
    for size in ("1280", "390"):
        for h in [f"{h:02d}" for h in HOURS] + ["23s"]:                    # 23s: asleep at 23:00 with the lights off (G8 #15)
            for tag in ("before", "after"):
                assert (doc / f"{tag}_{size}_h{h}.jpg").exists(), f"{tag}_{size}_h{h}.jpg"
