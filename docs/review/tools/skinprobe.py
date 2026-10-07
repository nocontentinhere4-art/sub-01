import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
h = Harness(OUT / "_h", log=lambda *a: None, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("390")
    r = {"last_skinned": pg.evaluate("(() => { let n = null; boy.traverse(o => { if (o.isSkinnedMesh && !/_inside$/.test(o.name)) n = o.name; }); return n; })()")}
    h.goto_scene(pg, "phone", 14)
    r["contacts_phone"] = pg.evaluate("JSON.parse(JSON.stringify(window.roomDbg && roomDbg.contacts ? roomDbg.contacts() : (window.contacts ? contacts() : null)))")
    print(json.dumps(r)[:1500]); h.browser.close()
