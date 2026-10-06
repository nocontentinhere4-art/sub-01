# hips / knees / ankles / hands in the chair's frame, in the page (room-v5), per scenario (G14 probe; run from the repo root)
import json, sys, base64
sys.path.insert(0, ".")
from pathlib import Path
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
import tests.visual.contacts as C
only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
out = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/pp"); out.mkdir(parents=True, exist_ok=True)
JS = """(n) => { const D = window.roomDbg ? roomDbg() : null; const ch = D.chairNode(); const res = [];
  for (let f = 0; f < n; f++) { animate_(1/30); if (f % 10) continue; ch.updateMatrixWorld(true); const inv = ch.matrixWorld.clone().invert(); const o = {f};
    for (const b of ["Hips", "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftHand", "RightHand", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm"]) {
      const x = boy.getObjectByName(b); if (!x) continue; const p = x.getWorldPosition(new THREE.Vector3()); o[b] = p.clone().applyMatrix4(inv).toArray().map(v => +v.toFixed(3)); o[b + "_w"] = p.toArray().map(v => +v.toFixed(3)); }
    o.clip = pose().clip; o.at = pose().at; o.mode = window.mh && mh.M ? mh.M.mode : null; o.roll = window.mh && mh.M ? mh.M.off : null; o.chair = [ch.position.x, ch.position.y, ch.position.z, ch.rotation.y].map(v => +v.toFixed(3)); res.push(o); }
  return res; }"""
with Server() as server:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        h = Harness(out, log=lambda *x: None, cdn_cache=Path("tests/visual/.cdn_cache")); h.server = server; h.base = server.base
        h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx, pg, st = h.open("1280"); h.goto_scene(pg, "desk", 14); pg.wait_for_function("() => !window.mh || window.mh.ready", timeout=180000)
        R = {}
        for label, setup, secs in C.SCENARIOS_MH:
            if only and not any(o in label for o in only): continue
            if isinstance(secs, str): secs = pg.evaluate(f"(() => {{ const c = mh.M.actions['act_{secs}']; return c ? c.getClip().duration : 0; }})()")
            pg.evaluate(f"() => {{ {setup}; }}")
            R[label] = pg.evaluate(JS, int(secs * 30)); pg.evaluate("if (window.mh && mh.show) mh.show(null)")
            print(label, json.dumps(R[label][len(R[label]) // 2]), flush=True)
        (out / "pp.json").write_text(json.dumps(R))
