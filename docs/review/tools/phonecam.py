"""G26: phone framing. python phonecam.py <worktree> <out> [size,size] [scene,scene]
Opens the page at each size, puts him in each scene, lets the follow camera run 4 s (page goal + 1.2/s lerp), shoots
with the header (what the visitor sees) and records his head's screen position against the header's bottom."""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
SIZES = (sys.argv[3] if len(sys.argv) > 3 else "390,1280").split(",")
SCENES = (sys.argv[4] if len(sys.argv) > 4 else "sleeping,phone,door,desk").split(",")
HOURS = {"sleeping": 23, "phone": 14, "door": 14, "desk": 14, "window": 14, "walking": 14}
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
JS = r"""(() => { window.FREEZE = true; const H = new THREE.Vector3(), V = new THREE.Vector3();
  for (let i = 0; i < 120; i++) { animate_(1/30); updateCameraGoal(); const k = 1 - Math.exp(-1/30 * 1.2);
    camera.position.lerp(camGoal.pos, k); controls.target.lerp(camGoal.target, k); controls.update(); }
  for (let i = 0; i < 30; i++) { updateCameraGoal(); camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); controls.update(); }
  camera.updateMatrixWorld(true); boy.updateMatrixWorld(true);
  const c = renderer.domElement.getBoundingClientRect(), t = document.getElementById("top").getBoundingClientRect();
  const B = n => { let r = null; boy.traverse(o => { if (!r && o.isBone && o.name.toLowerCase() === n) r = o; }); return r; }; const hb = B("head"); hb.getWorldPosition(H); H.project(camera);
  const hips = B("hips").getWorldPosition(V).project(camera);
  const px = p => [Math.round((p.x + 1) / 2 * c.width), Math.round((1 - p.y) / 2 * c.height + c.top)];
  return {canvas: [Math.round(c.width), Math.round(c.height), Math.round(c.top)], header_bottom_px: Math.round(t.bottom), head_px: px(H), hips_px: px(hips),
          cam: camera.position.toArray().map(v => +v.toFixed(2)), at: pose().at, clip: pose().clip}; })()"""
rep = {}
h = Harness(OUT / "_h", log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    for size in SIZES:
        h.pages = {}; ctx, pg, st = h.open(size)
        for sc in SCENES:
            h.goto_scene(pg, sc, HOURS.get(sc, 14))
            r = rep[f"{size}_{sc}"] = pg.evaluate(JS); print(size, sc, json.dumps(r), flush=True)
            pg.evaluate("__qa.render ? __qa.render() : renderer.render(scene, camera)")
            pg.screenshot(path=str(OUT / f"{size}_{sc}.png"), animations="disabled")
        rep[f"{size}_errors"] = st["errors"]; ctx.close()
    h.browser.close()
(OUT / "phonecam.json").write_text(json.dumps(rep, indent=1)); print("done")
