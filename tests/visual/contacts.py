"""Contact checks for the room upgrade (preview/room-upgrade): his skinned vertices against the desk chair (all of him)
and against the keyboard, the mouse and the game controller (his hands and fingers), frame by frame through every
seated scenario, in the page's own states (?debug act() / live() / variant()). Prints a JSON report.

    python -m tests.visual.contacts [--out DIR] [--stride 2] [--every 1]

A hit is a vertex inside a closed mesh (tests/visual/contacts.js: inside-intervals on 5 mm columns), with its depth."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM          # noqa: E402
from tests.visual.fake_server import Server                  # noqa: E402

DESK = "act('research', {screen: {device: 'desk', id: 'p1', kind: 'page'}}); for (let i = 0; i < 60; i++) animate_(1/30)"
SEAT = DESK + "; variant('%s', 7)"                         # an idle variant in the chair, forced (it is picked at random)
SCENARIOS = [  # label, setup (JS), seconds: the live character's seated clips and the ways in and out of the chair
    ("desk typing", "act('research', {screen: {device: 'desk', id: 'q1', kind: 'page', query: 'ramen near kichijoji'}})", 10),
    ("desk mouse", "act('chart', {screen: {device: 'desk', id: 'c1', kind: 'page'}})", 8),
    ("desk watch", "act('watch_video', {screen: {device: 'desk', id: 'v1', kind: 'video'}})", 6),
    ("desk chess", "act('play_chess', {screen: {device: 'desk', id: 'k1', kind: 'chess'}})", 6),
    ("eating at the desk", "act('eat', {eating: 'ramen', food: 1})", 8),
    ("seated: leaning back", SEAT % "lean", 8),
    ("seated: legs", SEAT % "legs", 8),
    ("seated: drinking", SEAT % "drink", 8),
    ("seated: phone", SEAT % "phone", 8),
    ("seated: stretch / scratch / look", DESK + "; variant('scratch', 3)", 4),
    ("getting up to the window", DESK + "; live('window', {activity: 'window'})", 12),
    ("bedtime: get up, to bed", DESK + "; live('sleep', {activity: 'sleep'})", 22),
    ("sitting down at the desk", "act('window'); for (let i = 0; i < 30; i++) animate_(1/30); live('research', {screen: {device: 'desk', id: 'p2', kind: 'page'}})", 16),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "tests" / "visual" / "out"))
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--chair-sdf", default="", help="a signed distance grid of the chair (tests/visual/chair_sdf.py) for its test, in place of ray parity")
    ap.add_argument("--chair-tol-mm", type=int, default=2)
    ap.add_argument("--occupancy", default="", help="instead of the checks: write where his skin goes in the chair's frame (JSON)")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    h = Harness(out, log=lambda *x: None, cdn_cache=ROOT / "tests" / "visual" / ".cdn_cache")
    report = {"objects": None, "scenarios": []}
    with Server() as server, sync_playwright() as p:
        h.server = server; h.base = server.base
        h.browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx, pg, st = h.open("1280"); h.goto_scene(pg, "desk", 14)
        pg.wait_for_function("() => !window.mh || window.mh.ready", timeout=120000)
        if a.chair_sdf:                                    # (a generated chair is not closed: its grid instead)
            import base64
            import numpy as np
            z = np.load(a.chair_sdf)
            pg.evaluate("(g) => { window.__chairSDF = g; }", {"b64": base64.b64encode(z["sd"].astype(np.int8).tobytes()).decode(), "lo": z["lo"].tolist(),
                                                              "step": float(z["step"]), "dims": list(z["sd"].shape), "tol": a.chair_tol_mm})
        pg.add_script_tag(path=str(Path(__file__).with_name("contacts.js")))
        report["objects"] = pg.evaluate("__contacts.build()")
        for label, setup, secs in SCENARIOS:
            if a.only and a.only not in label:
                continue
            if isinstance(secs, str):                      # a showcase clip: one loop of it
                secs = pg.evaluate(f"(() => {{ const c = mh.M.actions['act_{secs}']; return c ? c.getClip().duration : 0; }})()")
            t0 = time.time()
            if a.occupancy:
                occ = pg.evaluate(f"__contacts.occupy(() => {{ {setup}; }}, {secs}, {a.stride}, {a.every})")
                pg.evaluate("if (window.mh && mh.show) mh.show(null)")
                report.setdefault("occupancy", {})[label] = occ
                print(label, len(occ), "voxels", round(time.time() - t0, 1), "s", flush=True)
                continue
            r = pg.evaluate(f"__contacts.run({json.dumps(label)}, () => {{ {setup}; }}, {secs}, {a.stride}, {a.every})")
            pg.evaluate("if (window.mh && mh.show) mh.show(null)")
            r["seconds"] = round(secs, 2); r["wall_s"] = round(time.time() - t0, 1)
            report["scenarios"].append(r)
            print(json.dumps(r), flush=True)
        report["errors"] = st["errors"]
        h.browser.close()
    if a.occupancy:
        Path(a.occupancy).write_text(json.dumps(report["occupancy"]))
        return
    (out / "contacts.json").write_text(json.dumps(report, indent=1))
    print("objects", report["objects"])
    print("errors", report["errors"])


if __name__ == "__main__":
    main()
