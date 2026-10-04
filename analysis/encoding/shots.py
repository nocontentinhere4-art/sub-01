"""Screenshots of /brain's "What it's seeing -> predicted cortex" card for docs/encoding/screens/.

Polls a running live server's /api/sensory until a real prediction is fresh (his screen went through the encoding
model; the page shows it on load), then opens /brain in headless Chromium (software WebGL: costly, so only then) and
shoots the whole page and the card, at desktop and phone widths.
Usage: python analysis/encoding/shots.py --url http://localhost:8790 [--wait 900] [--proxy URL]
(--proxy: for the page's three.js CDN behind a sandbox proxy; localhost is never proxied).
"""
import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "encoding" / "screens"


def main():
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8790")
    ap.add_argument("--wait", type=float, default=900)
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"))
    ap.add_argument("--chromium", default=os.environ.get("BROWSE_CHROMIUM"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t_end = time.time() + a.wait
    while True:
        last = json.load(urllib.request.urlopen(a.url + "/api/sensory", timeout=10)).get("last")
        if last and time.time() - last["t"] < 30:
            break
        if time.time() > t_end:
            raise SystemExit("no fresh sensory prediction")
        time.sleep(5)
    print("fresh prediction:", last["kind"], last.get("title"), [r["label"] for r in last["top"][:3]], flush=True)
    kw = {"args": ["--ignore-certificate-errors", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"]}
    if a.chromium:
        kw["executable_path"] = a.chromium
    if a.proxy:
        kw["proxy"] = {"server": a.proxy, "bypass": "localhost,127.0.0.1"}
    with sync_playwright() as p:
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(a.url + "/brain", timeout=60000)
        pg.wait_for_selector("#sense:not([hidden])", state="visible", timeout=60000)
        # software WebGL loads the 3D brain slowly: once the cortex is there, show the same (real) prediction again so
        # its regions are lit when the shot is taken (live, a new prediction arrives every 4 s)
        pg.wait_for_function("scene.getObjectByName('cortex') && scene.getObjectByName('cortex').material !== cortexMat",
                             timeout=120000)
        pg.wait_for_timeout(1500)
        pg.evaluate("onSense(sense)")
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(OUT / "brain_desktop.png"))
        # a second view facing the lit regions (the top regions' centroids, seen from outside, a little from above)
        pg.evaluate("""(() => {
          const qs = sense.top.slice(0, 4).map(r => nodes[r.i].q), t = controls.target, d = camera.position.distanceTo(t);
          const v = new THREE.Vector3(...[0, 1, 2].map(k => qs.reduce((a, q) => a + q[k], 0) / qs.length))
            .sub(t).normalize();
          v.z = Math.max(v.z, 0.3); v.normalize();
          controls.autoRotate = false; camera.position.copy(t).addScaledVector(v, d); controls.update(); onSense(sense);
        })()""")
        pg.wait_for_timeout(2000)
        pg.screenshot(path=str(OUT / "brain_lit.png"))
        box = pg.locator("#sense").bounding_box()
        pg.screenshot(path=str(OUT / "card.png"), clip={k: box[k] + d for k, d in
                                                       (("x", -6), ("y", -6), ("width", 12), ("height", 12))})
        pg.close()                                         # one software-WebGL page at a time
        ph = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ph.goto(a.url + "/brain", timeout=60000)
        ph.wait_for_selector("#sense:not([hidden])", state="visible", timeout=60000)
        ph.wait_for_timeout(2500)
        ph.evaluate("onSense(sense); document.getElementById('sense').scrollIntoView({block: 'start'})")
        ph.wait_for_timeout(1500)
        pb = ph.locator("#sense").bounding_box()          # cropped to the card's column: no third-party video beside it
        ph.screenshot(path=str(OUT / "brain_phone.png"), timeout=120000,
                      clip={"x": 0, "y": 0, "width": pb["x"] + pb["width"] + 12, "height": pb["y"] + pb["height"] + 12})
        b.close()
    print("saved", sorted(x.name for x in OUT.iterdir()))


if __name__ == "__main__":
    main()
