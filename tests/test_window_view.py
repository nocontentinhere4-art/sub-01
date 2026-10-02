"""The view out of the room's window (#98 G7): web/room/window_view.js + the cards in web/room/window/.

Checks the asset budget, that the cards are exactly what room_build/window_cards.py draws (deterministic, so a
regenerated set is byte-identical), the lights masks' encoding, the module's pure parts in node (tests/js/window_view_check.js:
the weather pattern's shares and smoothness, the lit-window curve, the shader's contract), the tight wiring in room.html
(the old in-page sky shader is gone, the view is built on the window marker and updated every frame), the credits, and
that nothing in the view names a brand, a chain or a landmark. The pixels are checked by hand with tests/room_window_shots.py."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "web" / "room" / "window"
JS = ROOT / "web" / "room" / "window_view.js"
ROOM = ROOT / "web" / "room.html"
GEN = ROOT / "room_build" / "window_cards.py"
CARDS = ("near", "mid", "far", "ground")
BUDGET = 1.5 * 1024 * 1024


@pytest.fixture(scope="module")
def check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(ROOT / "tests" / "js" / "window_view_check.js")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_assets_exist_and_fit_the_budget():
    files = sorted(WIN.glob("*.webp"))
    names = {f.name for f in files}
    for c in CARDS:
        assert f"{c}.webp" in names, c
    for c in ("near", "mid", "far"):
        assert f"{c}_l.webp" in names, c                                    # the lights masks
    assert "noise.webp" in names
    total = sum(f.stat().st_size for f in files) + JS.stat().st_size
    assert total <= BUDGET, f"{total / 1024:.0f} KB over the 1.5 MB budget"


def test_cards_are_webp_of_the_documented_size():
    from PIL import Image
    sizes = {"near": (1024, 1024), "mid": (2048, 1024), "far": (2048, 256), "ground": (1024, 1024), "noise": (256, 256)}
    for name, size in sizes.items():
        with Image.open(WIN / f"{name}.webp") as im:
            assert im.format == "WEBP" and im.size == size, (name, im.format, im.size)
            assert im.mode == "RGBA", name                                   # alpha: the sky shows through the cards
    for name in ("near", "mid", "far"):
        with Image.open(WIN / f"{name}_l.webp") as im:
            assert im.size == sizes[name] and im.mode == "RGB"


def test_lights_masks_encode_pane_kind_and_id():
    import numpy as np
    from PIL import Image
    kinds_seen = set()
    for name in ("near", "mid", "far"):
        a = np.asarray(Image.open(WIN / f"{name}_l.webp").convert("RGB"))
        pane = a[..., 0] > 200                                                # R = coverage, full inside a pane
        assert pane.mean() > 0.002, name                                      # there are windows
        ids = np.unique(a[..., 2][pane])
        assert len(ids) >= (5 if name == "near" else 10), (name, len(ids))   # distinct windows switch on their own
        assert ids.max() <= 250 and ids.min() >= 1
        kinds_seen |= set(np.unique(a[..., 1][pane]).tolist())
        assert not pane[0].any() or name == "far"                             # the top row is sky (far: the mast's light may reach)
    for k in (0, 100, 200):                                                   # homes, warm always-on (lamp), cool always-on (shop, stair)
        assert any(abs(x - k) <= 2 for x in kinds_seen), (k, sorted(kinds_seen))
    assert any(abs(x - 50) <= 2 for x in kinds_seen)                          # a red aviation light on a tower


def test_generator_is_deterministic(tmp_path):
    """the committed cards are exactly what the generator draws (one seed; the build does not depend on the machine's clock)"""
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    sys.path.insert(0, str(GEN.parent))
    import importlib
    wc = importlib.import_module("window_cards")
    wc.OUT = tmp_path
    files = wc.build()
    assert sum(files.values()) <= wc.BUDGET
    import numpy as np
    from PIL import Image
    for f in files:
        if (tmp_path / f).read_bytes() == (WIN / f).read_bytes():
            continue
        # another libwebp may encode the same pixels differently: then the decoded pictures must still agree
        a = np.asarray(Image.open(tmp_path / f).convert("RGBA")).astype(int); b = np.asarray(Image.open(WIN / f).convert("RGBA")).astype(int)
        assert a.shape == b.shape and np.abs(a - b).mean() < 1.5, f"{f} differs from the committed card: rerun room_build/window_cards.py"


def test_generator_draws_no_text_and_no_brands():
    src = GEN.read_text()
    assert "ImageFont" not in src and ".text(" not in src                    # no signage, no lettering of any kind
    for w in ("Sony", "Toshiba", "Coca", "Suntory", "Asahi", "Kirin", "Lawson", "FamilyMart", "7-Eleven", "Skytree", "Tokyo Tower", "Chuo", "Chūō"):
        assert w not in src, w


def test_weather_pattern_shares_and_smoothness(check):
    w = check["weather"]
    # autumn Tokyo: about a fifth of the hours wet, a third overcast, the rest clear; fronts move slowly (no jumps)
    assert 0.12 <= w["rain"] <= 0.30, w
    assert 0.22 <= w["overcast"] <= 0.45, w
    assert 0.35 <= w["clear"] <= 0.62, w
    assert w["max_step_per_10min"] < 0.25, w
    assert 1.0 <= w["changes_per_day"] <= 6.0, w
    assert check["deterministic"] and check["range_ok"]


def test_lit_windows_follow_the_evening(check):
    lit = check["lit"]
    assert lit["h20"] > 0.6 and lit["h3"] < 0.2 and lit["h12"] < 0.4 and lit["h24_eq_h0"]
    assert lit["max_jump_per_3min"] < 0.03                                     # no sudden mass switch
    assert check["lit_uniform_follows_hour"]


def test_sun_curve_matches_the_room(check):
    s = check["sun"]
    assert s["noon"] > 0.95 and s["midnight"] < -0.95 and abs(s["rise"]) < 1e-6
    assert check["sun_crosses"]                                                # left in the morning, right in the afternoon


def test_shader_contract(check):
    t = check["textures"]
    assert t["every_sampler_has_a_uniform"] and check["uniforms_declared"]
    assert set(t["loaded"]) == {f"{c}.webp" for c in CARDS} | {f"{c}_l.webp" for c in ("near", "mid", "far")} | {"noise.webp"}
    assert all(check["layers"].values()), check["layers"]
    assert check["colorspace_included"] and check["built"] and check["brand_free"]
    g = check["gain"]
    assert 0.5 <= g["h"] <= 1.0 and 0.3 <= g["v"] <= 1.0 and 0 <= g["pitch"] <= 0.2 and g["pitchMax"] <= 0.5


def test_weather_override_and_the_train(check):
    r = check["rain_override"]
    assert r["rain"] > 0.95 and r["cloud"] > 0.95 and r["sun_factor"] < 0.3
    assert check["state_kind_after_reset"] in ("clear", "overcast", "rain")
    tr = check["train"]
    assert tr["steps_visible"] > 10 and tr["directions"] == [-1, 1]


def test_room_html_wiring_is_tight():
    html = ROOM.read_text()
    assert 'import { createWindowView } from "./room/window_view.js";' in html
    assert "createWindowView(THREE, {base:\"room/window/\"" in html
    assert "sky = windowView.build(w, scene);" in html                          # on the GLB's SURF_window marker, as before
    assert "windowView.update(dt, hour);" in html                               # once per frame, driven by his Tokyo clock
    assert "skyMaterial" not in html and "ShaderMaterial" not in html            # the old in-page sky shader is gone
    assert html.count("windowView") <= 8                                         # a small block, nothing else touched


def test_credits_cover_the_window():
    credits = (ROOT / "web" / "room" / "CREDITS.md").read_text()
    assert "window_cards.py" in credits and "window_view.js" in credits and "CC0" in credits
    doc = (ROOT / "docs" / "design" / "room-window" / "README.md").read_text()
    assert re.search(r"no weather (feed|API)", doc, re.I) and "deterministic" in doc.lower()   # honest about the weather


def test_module_header_states_the_weather_is_a_pattern():
    src = JS.read_text()
    assert "no\n// weather feed" in src or "no weather feed" in src.replace("\n// ", " ")
    assert "never\n// presented as real" in src or "never presented as real" in src.replace("\n// ", " ")
