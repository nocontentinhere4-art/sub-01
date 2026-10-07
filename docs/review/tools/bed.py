"""G23: bed clips. python bed.py <worktree> <out>: listen (music), asleep, the side turn; shots + head/feet/hands close-ups"""
import json, os, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM
from tests.visual.fake_server import Server
from playwright.sync_api import sync_playwright
HERE = Path(__file__).parent
CAMS = [("page", None, 0, 0, 0), ("over", "neck", -1.57, 1.1, 0.9), ("head", "neck", -1.2, 0.45, 0.6), ("headtop", "neck", -0.3, 0.45, 1.2),
        ("feet", "feet", -0.6, 0.7, 0.5), ("lhand", "lhand", -1.2, 0.4, 0.8), ("rhand", "rhand", -1.2, 0.4, 0.8), ("side_low", "neck", -1.57, 1.4, 0.15)]
def shoot(pg, h, tag):
    for name, part, az, d, up in CAMS:
        if part is None: pg.evaluate("__rv.resetFov(); __qa.followCam()")
        else: pg.evaluate(f"__rv.cam({json.dumps(part)}, {az}, {d}, {up}, 40)")
        pg.evaluate("__qa.render()"); h.shoot(pg, OUT / f"{tag}_{name}.png", hud=False)
    pg.evaluate("__rv.resetFov(); __qa.followCam()")
STATE = "JSON.stringify({p: pose().at, g: pose().goal && pose().goal.clip, step: pose().step && pose().step.k, cur: window.current && current._clip && current._clip.name, turning: window.mh && mh.turning})"
rep = {}
h = Harness(OUT / "_h", log=print, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
with Server() as server, sync_playwright() as p:
    h.server = server; h.base = server.base
    h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx, pg, st = h.open("1280")
    pg.add_script_tag(content=(HERE / "rv.js").read_text())
    def settle_into(act, X, want="bedlie"):
        pg.evaluate(f"""(() => {{ settle(); live({json.dumps(act)}, {json.dumps(X)}); let t = 0, still = 0;
          while (t < 150 && still < 1) {{ animate_(1/30); t += 1/30; still = pose().step || pose().at !== {json.dumps(want)} ? 0 : still + 1/30; }} return t; }})()""")
    # listening with music
    h.goto_scene(pg, "window", 15)
    settle_into("listen_music", {"music": {"title": "a quiet track", "artist": "someone", "playing": True}})
    for k, adv in enumerate([30, 120, 120]):
        pg.evaluate(f"__qa.step(1/30, {adv})"); rep[f"listen_{k}"] = pg.evaluate(STATE); shoot(pg, h, f"listen_{k}")
    # asleep
    settle_into("sleep", {})
    pg.evaluate("__qa.step(1/30, 60)"); rep["sleep_0"] = pg.evaluate(STATE); shoot(pg, h, "sleep_0")
    # the turn: start at the next wrap, shoot at 1.3 s (rolling), 6 s (on his side), 15.5 s (rolling back)
    pg.evaluate("mh.sleepTurn()")
    for i in range(30 * 40):
        pg.evaluate("animate_(1/30)")
        if pg.evaluate("!!(window.mh && mh.turning)"): break
    rep["turn_started_after_frames"] = i
    t = 0
    for k, at in enumerate([1.3, 6.0, 15.5]):
        n = int((at - t) * 30); pg.evaluate(f"__qa.step(1/30, {n})"); t = at
        rep[f"turn_{k}"] = pg.evaluate(STATE); shoot(pg, h, f"turn_{k}")
    rep["errors"] = st["errors"]
    h.browser.close()
(OUT / "bed.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep)); print("done")
