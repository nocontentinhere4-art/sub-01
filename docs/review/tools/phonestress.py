"""G26: phone camera under fresh, live (unfrozen) loads. python phonestress.py <worktree> <out> <size,size> <loads> [scene]
Each load: a fresh page, the fake server already in <scene> (default sleeping, 23 h) so the first tick puts him there;
the page runs live (no FREEZE), the camera is sampled every 0.25 s from 'load' until 25 s after mh.ready (cap 200 s); shots at ready and at the end.
Bad frame: camera NaN or outside |x|,|z| < 8, 0 < y < 8. Black: the canvas under the header has mean luminance < 8."""
import json, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
SIZES = sys.argv[3].split(","); N = int(sys.argv[4]); SCENE = sys.argv[5] if len(sys.argv) > 5 else "sleeping"
sys.path.insert(0, str(ROOT))
from tests.visual.harness import CHROMIUM
from tests.visual import scenes as S
from tests.visual.fake_server import Server
from tests.visual.cdn_cache import CdnCache
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat
CAM = """(() => { if (!window.camera) return null; const p = camera.position;
  return [p.x, p.y, p.z].map(v => +v.toFixed(2)).concat([+(!!(window.mh && mh.ready)), +(!!(window.boy && boy.visible))]); })()"""
TOP = "(() => { const c = renderer.domElement.getBoundingClientRect(), t = document.getElementById('top').getBoundingClientRect(); return c.width > 900 ? 0 : Math.max(0, Math.round(t.bottom - c.top)); })()"
def bad(c): return c is not None and (any(v != v for v in c[:3]) or abs(c[0]) > 8 or abs(c[2]) > 8 or not (0 < c[1] < 8))
def lum(path, top):
    im = Image.open(path).convert("L"); w, h = im.size; return round(ImageStat.Stat(im.crop((0, top, w, h))).mean[0], 1)
rep = {}; cdn = CdnCache(ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    br = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    for size in SIZES:
        w, hh, mob = S.SIZES[size]
        for k in range(N):
            server.set_scene(SCENE, 23 if SCENE == "sleeping" else 14)
            ctx = br.new_context(viewport={"width": w, "height": hh}, device_scale_factor=1, is_mobile=mob, has_touch=mob)
            pg = ctx.new_page(); pg.set_default_timeout(150000); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); cdn.install(pg)
            pg.goto(server.base + f"/room.html?debug&hour={23 if SCENE == 'sleeping' else 14}", wait_until="load")
            samples, shots, t0 = [], {}, time.time()
            rdy = None
            while time.time() - t0 < 200 and not (rdy and time.time() - rdy > 25):
                c = pg.evaluate(CAM); samples.append([round(time.time() - t0, 2), c])
                if c and c[3] and not rdy:
                    rdy = time.time(); f = OUT / f"{size}_{k}_ready.png"; pg.screenshot(path=str(f), timeout=150000, animations="disabled", caret="initial"); shots["ready"] = lum(f, pg.evaluate(TOP))
                pg.wait_for_timeout(250)
            f = OUT / f"{size}_{k}_end.png"; pg.screenshot(path=str(f), timeout=150000, animations="disabled", caret="initial"); shots["end"] = lum(f, pg.evaluate(TOP))
            badf = [s for s in samples if bad(s[1])]
            ready_at = next((s[0] for s in samples if s[1] and s[1][3]), None)
            r = rep[f"{size}_{k}"] = {"samples": len(samples), "bad": len(badf), "first_bad": badf[:3], "ready_at_s": ready_at,
                                      "cam_end": samples[-1][1], "lum": shots, "errors": errs}
            print(size, k, json.dumps({x: r[x] for x in ["samples", "bad", "first_bad", "ready_at_s", "cam_end", "lum", "errors"]}), flush=True)
            ctx.close()
    br.close()
(OUT / "stress.json").write_text(json.dumps(rep)); print("done")
