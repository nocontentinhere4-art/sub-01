"""G26: listening on the bed. python bedprobe.py <worktree> <out>: the music state, the headphones, close-ups from above"""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
PROBE = """(() => { const hp = boy.getObjectByName('headphones_on'); const H = new THREE.Vector3(); boy.getObjectByName('Head').getWorldPosition(H);
  let cur = []; if (window.mixer) mixer._actions.forEach(a => { if (a.isRunning() && a.getEffectiveWeight() > 0.05) cur.push(a.getClip().name + ':' + a.getEffectiveWeight().toFixed(2)); });
  return {mode: window.mh && mh.M && mh.M.mode, music: !!(window.mh && mh.M && mh.M.music), hp: hp ? hp.visible : null, head: H.toArray().map(v => +v.toFixed(3)), running: cur, at: pose().at, goal: pose().goal && pose().goal.clip}; })()"""
CAM = """(([dx, dy, dz, fov]) => { const H = new THREE.Vector3(); boy.getObjectByName('Head').getWorldPosition(H);
  camera.fov = fov; camera.updateProjectionMatrix(); camera.position.set(H.x + dx, H.y + dy, H.z + dz); controls.target.copy(H); controls.update(); __qa.render(); })"""
rep = {}
h = Harness(OUT / "_h", log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base; h.query = "&nolive"
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("1280")
    pg.evaluate("setHour(15)")
    pg.evaluate("""(() => { settle(); live('listen_music', {music: {id: 'rv', title: 'a quiet track', artist: 'someone', playing: true}}); for (let i = 0; i < 30 * 20; i++) animate_(1/30); })()""")
    for k in range(3):
        pg.evaluate("__qa.step(1/30, 45)"); rep[f"listen_{k}"] = pg.evaluate(PROBE); print(rep[f"listen_{k}"], flush=True)
        for name, c in [("above", [0.0, 0.45, 0.0, 40]), ("left", [0.0, 0.12, 0.35, 40]), ("right", [0.0, 0.12, -0.35, 40]), ("page", None)]:
            if c is None: pg.evaluate("__qa.followCam(); __qa.render()")
            else: pg.evaluate(CAM + f"({json.dumps(c)})")
            h.shoot(pg, OUT / f"listen_{k}_{name}.png", hud=False)
    rep["errors"] = st["errors"]; h.browser.close()
(OUT / "probe.json").write_text(json.dumps(rep, indent=1)); print("done")
