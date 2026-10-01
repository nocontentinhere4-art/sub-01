"""Screenshots of the "Twin" panel on /brain and / (life page) from a local `live_server.py --demo`.

    OMP_NUM_THREADS=1 python twin/screenshots.py [--out docs/twin/screenshots]

Needs `pip install playwright` and the Chromium that is already installed (PLAYWRIGHT_BROWSERS_PATH; do not run
"playwright install"). To show a memory and a non-zero drift, the temporary data dir is first filled by one
accelerated synthetic night (the same driver as tests/test_integration.py). The three.js and leaflet libraries the pages
load from their CDNs are fetched once through the environment's proxy and handed to the browser; every other external
request (map tiles, embeds) is blocked, so the pictures do not depend on the network and nothing else is requested.
A digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the person.
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDN = {"https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js": "application/javascript",
       "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js": "application/javascript",
       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js": "application/javascript",
       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css": "text/css"}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seed_data_dir(tmp):
    """One synthetic night with chat messages so the panel has a memory and a drift to show."""
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT))
    import test_integration as T
    n = T.Night(tmp)
    n.live.store.save(n.live.engine, n.live.memory)
    n.live.save_twin()
    return n.live.memories


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "twin" / "screenshots"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    libs = {u: urllib.request.urlopen(u, timeout=60).read() for u in CDN}
    tmp = tempfile.mkdtemp()
    print("memories seeded:", len(seed_data_dir(tmp)))
    port = free_port()
    env = dict(os.environ, OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1")
    env.pop("SITE_PASSWORD", None)
    proc = subprocess.Popen([sys.executable, "live_server.py", "--demo", "--port", str(port), "--data-dir", tmp],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.5)
        with sync_playwright() as pw:
            kw = {}
            if not Path(pw.chromium.executable_path).exists():       # installed playwright wants a newer build than the preinstalled one
                found = sorted(Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")).glob("chromium-*/chrome-linux/chrome"))
                if found:
                    kw["executable_path"] = str(found[-1])
            br = pw.chromium.launch(**kw, args=["--no-proxy-server", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            for path, name, w, h in (("/brain", "brain_twin_panel.png", 1280, 1100), ("/", "life_twin_panel.png", 1280, 1100)):
                ctx = br.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                blocked = []

                def route(r):
                    u = r.request.url
                    if u in libs:
                        r.fulfill(status=200, body=libs[u], content_type=CDN[u])
                    elif u.startswith(f"http://127.0.0.1:{port}"):
                        r.continue_()
                    else:
                        blocked.append(u)
                        r.abort()
                page.route("**/*", route)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{port}{path}", wait_until="domcontentloaded")
                page.wait_for_function("document.querySelector('#twin-host .tw-mem') !== null", timeout=60000)
                page.wait_for_timeout(4000)                               # a few seconds of ticks
                rect = "(s) => { const r = document.querySelector(s).getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }"
                box = page.evaluate(rect, "#twin-host")
                host_text = page.evaluate("document.querySelector('#twin-host').innerText")
                side = page.evaluate(rect, "#panel" if path == "/brain" else "#side")
                page.screenshot(path=str(out / name), clip={"x": side["x"] - 6, "y": 0, "width": side["width"] + 6, "height": h}, timeout=180000)
                print(name, "panel box", box, "js errors:", errors[:3], "blocked external requests:", len(blocked))
                print(host_text[:600].replace("\n", " | "))
                ctx.close()
            br.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
