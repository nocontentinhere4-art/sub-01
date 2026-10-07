"""G23: shoot + measure ?char=mixamo&clip=<Clip> (G22 standing_preview). python clips.py <worktree> <out> Clip[,Clip]"""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
CLIPS = sys.argv[3].split(",")
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
JS = r"""
window.__cv = (() => { const V = () => new THREE.Vector3(), C = SP.char, F = SP.holder.position.y;
  const bone = n => SP.bone(n); const wp = b => b.getWorldPosition(V());
  const skins = []; C.traverse(o => { if (o.isSkinnedMesh) skins.push(o); });
  const soles = () => { C.updateMatrixWorld(true); const lf = wp(bone("LeftFoot")), rf = wp(bone("RightFoot")), v = V(), o = {L: 9, R: 9};
    for (const m of skins) { const P = m.geometry.attributes.position; for (let i = 0; i < P.count; i += 2) { m.getVertexPosition(i, v).applyMatrix4(m.matrixWorld);
      if (v.y > F + 0.25) continue; const dl = v.distanceTo(lf), dr = v.distanceTo(rf); if (Math.min(dl, dr) > 0.22) continue; const s = dl < dr ? "L" : "R"; if (v.y < o[s]) o[s] = v.y; } }
    return {L: +((o.L - F) * 100).toFixed(2), R: +((o.R - F) * 100).toFixed(2)}; };
  const cam = (t, pos, fov) => { camera.fov = fov || 40; camera.updateProjectionMatrix(); camera.position.copy(pos); controls.target.copy(t); controls.update(); };
  const fwd = () => V().set(0, 0, 1).applyQuaternion(SP.holder.quaternion).setY(0).normalize();
  const shots = {
    front: () => { const v = SP.view("front"); cam(v.target, v.pos, 45); },
    side: () => { const v = SP.view("side"); cam(v.target, v.pos, 45); },
    feet: () => { const t = wp(bone("LeftFoot")).add(wp(bone("RightFoot"))).multiplyScalar(0.5); t.y = Math.max(F + 0.05, t.y - 0.03); const f = fwd(), r = V().set(-f.z, 0, f.x);
      cam(t, t.clone().addScaledVector(f, 0.45).addScaledVector(r, 0.25).add(V().set(0, 0.12, 0)), 40); },
    hands: () => { const t = wp(bone("LeftHand")).add(wp(bone("RightHand"))).multiplyScalar(0.5); const f = fwd(), r = V().set(-f.z, 0, f.x);
      cam(t, t.clone().addScaledVector(f, 0.45).addScaledVector(r, -0.3).add(V().set(0, 0.25, 0)), 40); },
  };
  const render = () => { scene.traverse(o => { if (o.isLight && o.shadow) o.shadow.needsUpdate = true; }); renderer.render(scene, camera); };
  const sweep = () => { const n = Math.round(SP.duration * 30), a = []; for (let i = 0; i < n; i++) { SP.setTime(i / 30); a.push(soles()); } return a; };
  return {soles, shots, render, sweep};
})(); true
"""
rep = {}
h = Harness(OUT / "_h", log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    for clip in CLIPS:
        h.pages = {}; h.query = f"&char=mixamo&clip={clip}"
        ctx, pg, st = h.open("1280")
        pg.wait_for_function("() => window.SP && SP.ready", timeout=180000)
        pg.evaluate(JS); pg.evaluate("__qa.hud(false)")
        sw = pg.evaluate("__cv.sweep()")
        L = [s["L"] for s in sw]; R = [s["R"] for s in sw]; low = [min(a, b) for a, b in zip(L, R)]
        r = rep[clip] = {"duration": pg.evaluate("SP.duration"), "kind": pg.evaluate("SP.meta.row.kind"), "chair": pg.evaluate("SP.chair || null"),
                         "L_cm": [min(L), max(L)], "R_cm": [min(R), max(R)], "lowest_foot_cm": [min(low), max(low)],
                         "frames_lowest_over_1cm": sum(1 for x in low if x > 1.0), "frames_below_-0.5cm": sum(1 for x in low if x < -0.5), "frames": len(low),
                         "worst_over_t": round(low.index(max(low)) / 30, 2), "errors": st["errors"]}
        print(clip, json.dumps(r), flush=True)
        D = r["duration"]
        for k, t in enumerate([0.1, 0.45, 0.8]):
            pg.evaluate(f"SP.setTime({D * t})")
            for c in ["front", "side", "feet", "hands"]:
                pg.evaluate(f"__cv.shots.{c}(); __cv.render()")
                pg.screenshot(path=str(OUT / f"{clip}_t{k}_{c}.png"), animations="disabled")
        ctx.close()
    h.browser.close()
(OUT / "clips.json").write_text(json.dumps(rep, indent=1))
print("done")
