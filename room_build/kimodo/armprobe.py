import json, sys
sys.path.insert(0, ".")
from pathlib import Path
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
import tests.visual.contacts as C
JS = """(n) => { const ray = new THREE.Raycaster(), v = new THREE.Vector3(), res = [];
  const parts = []; boy.traverse(o => { if (o.isSkinnedMesh && o.visible) parts.push(o); });
  const deskMeshes = []; scene.traverse(m => { if (m.isMesh && !m.isSkinnedMesh && m.visible) deskMeshes.push(m); });
  for (let f = 0; f < n; f++) { animate_(1/30); if (f % 15) continue; boy.updateMatrixWorld(true); let worst = 0, nIn = 0, wp = null;
    for (const sm of parts) { const P = sm.geometry.attributes.position, I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight;
      for (let i = 0; i < P.count; i += 3) { let b = 0, bw = 0; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > bw) { bw = W.getComponent(i, k); b = I.getComponent(i, k); }
        const bn = sm.skeleton.bones[b].name; if (!/^L_Forearm|LeftForeArm|L_Hand|LeftHand/.test(bn)) continue;
        sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld); if (v.z > -0.80 || v.x < -1.86 || v.x > -0.36) continue;
        const d = 0.97 - v.y; if (d > 0 && d < 0.05) { nIn++; if (d > worst) { worst = d; wp = [v.x, v.y, v.z, bn]; } } } }
    const h = boy.getObjectByName("LeftHand").getWorldPosition(new THREE.Vector3()), e = boy.getObjectByName("LeftForeArm").getWorldPosition(new THREE.Vector3());
    res.push({f, mode: mh.M.mode, clip: pose().clip, worst: +worst.toFixed(3), nIn, wp, hand: h.toArray().map(x => +x.toFixed(3)), elbow: e.toArray().map(x => +x.toFixed(3)), boyY: +boy.position.y.toFixed(3)}); }
  return res; }"""
with Server() as server:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        h = Harness(Path("/tmp/ap"), log=lambda *x: None, cdn_cache=Path("tests/visual/.cdn_cache")); h.server = server; h.base = server.base
        h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx, pg, st = h.open("1280"); h.goto_scene(pg, "desk", 14); pg.wait_for_function("() => !window.mh || window.mh.ready", timeout=180000)
        for row in pg.evaluate(JS, 150): print(json.dumps(row))
