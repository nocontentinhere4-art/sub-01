"""The mood layer (?mood=1, web/room/mood.js) in the real page: it loads without errors, its card never covers him
(his bones projected to the screen against the card's box, at 1280 and at 390, in three scenes, with the camera that
follows him and with the overview), a swatch changes the floor and is kept in this browser's localStorage only, the
hour preview eases back to the real hour on its own, and the things a visitor adds stand clear of his paths.
Skipped where headless Chromium or Playwright is missing, like test_visual.py."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tests.visual import harness as H          # noqa: E402
from tests.visual.fake_server import Server    # noqa: E402

# his bones on the screen (CSS px of the page), and the card's box
OVERLAP = """() => {
  const r = renderer.domElement.getBoundingClientRect(), v = new THREE.Vector3();
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, n = 0;
  boy.updateMatrixWorld(true);
  boy.traverse(o => { if (!o.isBone) return; o.getWorldPosition(v); v.project(camera);
    if (v.z > 1 || v.z < -1) return;
    const x = r.left + (v.x + 1) / 2 * r.width, y = r.top + (1 - v.y) / 2 * r.height;
    if (x < r.left || x > r.right || y < r.top || y > r.bottom) return;
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); n++; });
  const c = document.getElementById('mood').getBoundingClientRect();
  const vis = {left: c.left, top: Math.max(c.top, 0), right: c.right, bottom: Math.min(c.bottom, innerHeight)};
  const pad = 6, hit = n > 0 && vis.bottom > vis.top && !(vis.right < x0 - pad || vis.left > x1 + pad || vis.bottom < y0 - pad || vis.top > y1 + pad);
  return {hit, him: [x0, y0, x1, y1].map(Math.round), card: [vis.left, vis.top, vis.right, vis.bottom].map(Math.round), bones: n};
}"""


def _page(h, size):
    ctx, pg, st = h.open(size)
    pg.wait_for_function("() => !!(window.moodLayer && moodLayer() && document.getElementById('mood'))", timeout=120000)
    return ctx, pg, st


def test_mood_layer_in_the_page(tmp_path):
    if not H.chromium_ok():
        pytest.skip("playwright / chromium not installed")
    from playwright.sync_api import sync_playwright
    h = H.Harness(tmp_path, log=lambda *a: None)
    h.query = "&mood=1"
    out = {}
    with Server() as server, sync_playwright() as p:
        h.server = server; h.base = server.base
        exe = H.CHROMIUM if Path(H.CHROMIUM).exists() else None
        h.browser = p.chromium.launch(executable_path=exe, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for size in ("1280", "390"):
            ctx, pg, st = _page(h, size)
            assert pg.evaluate("() => document.getElementById('mood').parentElement.id") == "side"
            for scene in ("desk", "sleeping", "window"):
                h.goto_scene(pg, scene, 19)
                pg.evaluate("() => { const m = moodLayer(); for (let i = 0; i < 20; i++) { m.tick(0.1, 19); m.light(0.1, {day: 0}); } }")
                for cam in ("follow", "overview"):
                    if cam == "overview":
                        pg.evaluate("__qa.lookFrom([5.2, 5.0, 6.0], [0, 0.6, 0])")
                    out[(size, scene, cam)] = pg.evaluate(OVERLAP)
            if size == "1280":
                # a swatch: the floor's texture changes, and the choice is in this browser's storage
                was = pg.evaluate("() => { let m = null; room.traverse(o => { if (o.isMesh && o.material.name === 'floor') m = o.material; }); window._fl = m; return m.map.uuid; }")
                pg.evaluate("() => document.querySelector('#mood .md-sw[data-group=floor] button[data-v=walnut]').click()")
                out["swatch"] = pg.evaluate("() => ({uuid: _fl.map.uuid, stored: localStorage.getItem('sub01.room.mood.v1'), on: !!document.querySelector('#mood .md-sw[data-group=floor] button[data-v=walnut].on')})")
                out["swatch_was"] = was
                pg.evaluate("() => document.getElementById('md-reset').click()")
                out["swatch_back"] = pg.evaluate("() => _fl.map.uuid")
                # the hour preview: held, then back to the real hour by itself
                out["preview"] = pg.evaluate("""() => { const m = moodLayer(); m.setPreview(3); const held = m.tick(0.1, 19);
                  for (let i = 0; i < 10 * 6; i++) m.tick(0.1, 19); const mid = m.state.preview;
                  for (let i = 0; i < 10 * 6; i++) m.tick(0.1, 19); return {held, mid, after: m.state.preview, hour: m.hour}; }""")
                # arrange: the things added stand clear of his paths
                out["arrange"] = pg.evaluate("""() => { const a = moodLayer().arrange; for (const k of ['lamp', 'plant', 'table', 'books', 'pouf']) a.add(k);
                  return a.things.map(t => ({type: t.type, ok: a.spotOK(t, t.g.position.x, t.g.position.z)})); }""")
            out[("errors", size)] = list(st["errors"])
        h.browser.close()
    for size in ("1280", "390"):
        assert not out[("errors", size)], out[("errors", size)][:3]
    covered = {k: v for k, v in out.items() if isinstance(k, tuple) and len(k) == 3 and v["hit"]}
    assert not covered, f"the mood card covers him: {covered}"
    seen = [k for k, v in out.items() if isinstance(k, tuple) and len(k) == 3 and v["bones"] > 0]
    assert len(seen) >= 8, f"he was on screen in too few views to check: {seen}"
    assert out["swatch"]["uuid"] != out["swatch_was"] and out["swatch"]["on"], out["swatch"]
    assert '"floor":"walnut"' in (out["swatch"]["stored"] or ""), out["swatch"]
    assert out["swatch_back"] == out["swatch_was"]
    pv = out["preview"]
    assert abs(pv["held"] - 3) < 1e-6 and pv["mid"] is not None, pv
    assert pv["after"] is None and abs(pv["hour"] - 19) < 1e-6, pv
    assert len(out["arrange"]) >= 5 and all(t["ok"] for t in out["arrange"]), out["arrange"]
