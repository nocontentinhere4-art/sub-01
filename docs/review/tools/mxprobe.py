import json, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); Q = sys.argv[2]
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
h = Harness(Path("/tmp/claude-0/-home-user-sub-01/0b4952cd-7189-567a-a743-1c98d015426e/scratchpad/_mxp"), log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base; h.query = Q
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("390")
    t0 = time.time()
    while time.time() - t0 < 180 and not pg.evaluate("!!(window.mh && mh.ready)"): pg.wait_for_timeout(1000)
    print("mh.ready", pg.evaluate("!!(window.mh && mh.ready)"), "after", round(time.time() - t0), "s; mode", pg.evaluate("window.mh && mh.mode"))
    h.goto_scene(pg, "desk", 14)
    print("pose", pg.evaluate("JSON.stringify({at: pose().at, clip: pose().clip, cur: window.current && current._clip && current._clip.name})"))
    print("boy pos", pg.evaluate("boy.position.toArray().map(x=>+x.toFixed(2))"), "hips world", pg.evaluate("bones.Hips.getWorldPosition(new THREE.Vector3()).toArray().map(x=>+x.toFixed(2))"))
    print("errors", st["errors"][:5]); print("console", [c for c in st["console"] if "favicon" not in c][:15])
    h.browser.close()
