"""Black cloth stays black in daylight (#98 G6; the coordinator's review of #103): the owner keeps the original look, so
his hoodie reads black or charcoal by day, not grey or white. The metric and the budget live in tests/room_render_shots.py
(`cloth_means`, CLOTH_MAX): the mean luminance of the lit frame over his dark texels, in the page's own face and medium
shots at 08 (the desk, the sun low through the window) and 14 (the window sill, the sky right beside him), on the high
tier. Headless Chromium with software WebGL, like the rest of tests/visual; skipped where it is missing."""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tests import room_render_shots as RS     # noqa: E402
from tests.visual import harness as H          # noqa: E402

OUT = Path(os.environ.get("SUB01_VISUAL_OUT", HERE / "out")) / "cloth"


@pytest.fixture(scope="module")
def cloth():
    if not H.chromium_ok():
        if os.environ.get("SUB01_VISUAL"):
            pytest.fail("SUB01_VISUAL=1 but playwright / chromium are not available")
        pytest.skip("playwright / chromium not installed")
    try:
        with RS.Run(port=8793, post="high") as run:
            res = RS.cloth_means(run, OUT)
    except Exception as e:                                    # a browser that does not start here: skip, as test_visual.py does
        if "chromium" in repr(e).lower() or "browser" in repr(e).lower():
            pytest.skip(f"chromium did not start: {e!r}"[:200])
        raise
    (OUT / "results.json").write_text(json.dumps(res, indent=1))
    return res


def test_every_daylight_shot_was_measured(cloth):
    assert set(cloth) == {f"cloth_1280_h{h:02d}_{s}" for h, s in RS.CLOTH_SHOTS}
    for k, r in cloth.items():
        errs = [e for e in r["errors"] if not e.startswith("console.error: Failed to load resource")]   # a map tile or a font the sandbox could not fetch: not the page's
        assert errs == [], (k, errs)
        assert r["post"] == "high", k
        assert r["cloth_px"] > 2000, (k, r["cloth_px"])              # he is in the frame, his hoodie a real share of it


def test_black_cloth_stays_black_by_day(cloth):
    over = {k: r["cloth_mean"] for k, r in cloth.items() if r["cloth_mean"] is None or r["cloth_mean"] > RS.CLOTH_MAX}
    assert not over, f"hoodie mean luminance over {RS.CLOTH_MAX}/255: {over}"
    for k, r in cloth.items():
        assert r["cloth_over_120"] < 0.12, (k, r["cloth_over_120"])   # and no large patch of it reads light grey (the hood's side to the sky window at the sill)
