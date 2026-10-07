"""G23 review shooter: python shoot.py <worktree> <out> [scene,scene] [query]"""
import json, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else None
QUERY = sys.argv[4] if len(sys.argv) > 4 else ""
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
HERE = Path(__file__).parent
SCENES = [("door", 14), ("desk", 14), ("window", 14), ("phone", 14), ("sleeping", 23)]
FRAMES = [0, 45, 90]   # frames stepped between samples (1/30 s)
CAMS = [  # name, part, az, dist, up, fov
    ("page", None, 0, 0, 0, None),
    ("neck_front", "neck", 0, 0.32, 0.15, 40), ("neck_back", "neck", 3.14, 0.32, 0.15, 40),
    ("neck_left", "neck", 1.57, 0.32, 0.15, 40), ("neck_right", "neck", -1.57, 0.32, 0.15, 40),
    ("neck_top", "neck", 0.3, 0.30, 1.35, 40),
    ("feet_front", "feet", 0, 0.55, 0.25, 40), ("feet_side", "feet", -1.57, 0.55, 0.15, 40),
    ("feet_back", "feet", 3.14, 0.55, 0.25, 40), ("feet_low", "feet", 0.5, 0.45, 0.02, 40),
    ("lhand", "lhand", 1.2, 0.35, 0.6, 40), ("rhand", "rhand", -1.2, 0.35, 0.6, 40),
    ("larmpit", "larm", 1.9, 0.40, -0.2, 40), ("rarmpit", "rarm", -1.9, 0.40, -0.2, 40),
]
import os
if os.environ.get("CAMS"): CAMS = [c for c in CAMS if any(c[0].startswith(k) for k in os.environ["CAMS"].split(","))]
rep = {"root": str(ROOT), "query": QUERY, "scenes": {}}
h = Harness(OUT / "_h", log=lambda *x: print(*x, flush=True), cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
from playwright.sync_api import sync_playwright
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base; h.query = QUERY
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("1280")
    pg.add_script_tag(content=(HERE / "rv.js").read_text())
    rep["bones"] = pg.evaluate("__rv.which()"); rep["meshes"] = pg.evaluate("__rv.meshes()")
    print(rep["bones"], flush=True)
    for scene, hour in SCENES:
        if ONLY and scene not in ONLY: continue
        h.goto_scene(pg, scene, hour)
        sc = rep["scenes"][scene] = {"frames": []}
        for fi, adv in enumerate(FRAMES):
            if adv: pg.evaluate(f"__qa.step(1/30, {adv})")
            fr = {"clip": pg.evaluate("__rv.clip()"), "soles_cm": pg.evaluate("__rv.soles()")}
            # sole sweep over the next 45 frames isn't shot; record worst of every frame up to next sample
            for name, part, az, d, up, fov in CAMS:
                if name == "page": pg.evaluate("__rv.resetFov(); __qa.followCam()")
                else: pg.evaluate(f"__rv.cam({json.dumps(part)}, {az}, {d}, {up}, {fov})")
                pg.evaluate("__qa.render()")
                h.shoot(pg, OUT / f"{scene}_f{fi}_{name}.png", hud=False)
            pg.evaluate("__rv.resetFov(); __qa.followCam()")
            sc["frames"].append(fr); print(scene, fi, fr, flush=True)
        # soles every frame for 6 s
        sweep = pg.evaluate("(() => { const a = []; for (let i = 0; i < 180; i++) { animate_(1/30); if (i % 3 == 0) a.push(__rv.soles()); } return a; })()")
        L = [s["L"] for s in sweep]; Rr = [s["R"] for s in sweep]
        sc["sole_sweep_cm"] = {"L": [min(L), max(L)], "R": [min(Rr), max(Rr)], "lowest_foot": [min(min(a, b) for a, b in zip(L, Rr)), max(min(a, b) for a, b in zip(L, Rr))]}
        print(scene, sc["sole_sweep_cm"], flush=True)
    rep["errors"] = st["errors"]
    h.browser.close()
(OUT / "rep.json").write_text(json.dumps(rep, indent=1))
print("done", rep["errors"])
