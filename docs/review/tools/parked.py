import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
h = Harness(OUT / "_h", log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("1280")
    h.goto_scene(pg, "phone", 14)
    info = pg.evaluate("""(() => { const out = []; let tgt = null; const inBoy = new Set(); boy.traverse(o => inBoy.add(o));
      scene.traverse(o => { if (o.isMesh && o.visible && (() => { let q = o; while (q) { if (q.name === "slides_parked") return true; q = q.parent; } return false; })()) { const b = new THREE.Box3().setFromObject(o); const c = b.getCenter(new THREE.Vector3()); out.push([o.name, c.toArray()]); if (!tgt) { let q = o; while (q.name !== 'slides_parked') q = q.parent; tgt = q.getWorldPosition(new THREE.Vector3()); tgt.y += 0.03; } } });
      if (tgt) { camera.fov = 40; camera.updateProjectionMatrix(); camera.position.set(tgt.x + 0.25, tgt.y + 0.35, tgt.z + 0.3); controls.target.copy(tgt); controls.update(); }
      return out; })()""")
    print(info)
    pg.evaluate("__qa.render()"); h.shoot(pg, OUT / "parked.png", hud=False)
    pg.evaluate("(() => { const t = controls.target; camera.position.set(t.x - 0.05, t.y + 0.5, t.z + 0.05); controls.update(); })()")
    pg.evaluate("__qa.render()"); h.shoot(pg, OUT / "parked_top.png", hud=False)
    h.browser.close()
