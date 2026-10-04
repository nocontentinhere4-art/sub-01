"""Bed camera candidates: one frame each, him asleep (software WebGL)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.visual import scenes as S
from tests.visual.harness import Harness
S.SIZES["film"] = (1080, 1350, False)
out = Path(__file__).parent / "camtest"; out.mkdir(exist_ok=True)
C = {"F": ([0.0, 1.9, 0.95], [-1.5, 1.0, 0.9]), "G": ([-0.85, 1.55, 1.35], [-1.54, 1.08, 0.88]), "H": ([-0.6, 2.3, 0.9], [-1.55, 1.0, 0.88]), "I": ([0.4, 2.5, 1.6], [-1.4, 0.9, 0.9])}
h = Harness(out / "_qa", log=print, cdn_cache=ROOT / "tests/visual/.cdn_cache")
from playwright.sync_api import sync_playwright
from tests.visual.fake_server import Server
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("film")
    h.goto_scene(pg, "sleeping", 23)
    pg.evaluate("__qa.hud(false)")
    print(pg.evaluate("JSON.stringify({head: (()=>{boy.updateMatrixWorld(true); const v=new THREE.Vector3(); head.getWorldPosition(v); return v.toArray()})()})"))
    for k, (pos, tgt) in C.items():
        pg.evaluate("([p, t]) => __qa.lookFrom(p, t)", [pos, tgt]); pg.evaluate("__qa.render()")
        pg.screenshot(path=str(out / f"bed_{k}.jpg"), type="jpeg", quality=80)
