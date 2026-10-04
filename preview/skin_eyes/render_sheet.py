"""Render the skin-and-eyes preview sheet (preview/skin_eyes/index.html) to sheet.jpg with headless Chromium.

    python preview/skin_eyes/render_sheet.py [--out preview/skin_eyes/sheet.jpg]

Serves this folder over HTTP, opens the page (three.js r169 from jsDelivr, through a local cache as
tests/room_render_shots.py does), waits for both views to be drawn and saves the canvas. Software WebGL is fine:
it is one still.
"""
import argparse
import base64
import functools
import http.server
import json
import os
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import CDN_HOSTS, cdn_router   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "sheet.jpg"))
    ap.add_argument("--port", type=int, default=8931)
    ap.add_argument("--chromium", default=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"))
    args = ap.parse_args()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=args.chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = b.new_page(viewport={"width": 2000, "height": 2000}, ignore_https_errors=True)
            for h in CDN_HOSTS:
                pg.route(f"https://{h}/**", cdn_router(os.environ.get("SUB01_CDN_CACHE", "/tmp/sub01-cdn-cache")))
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.goto(f"http://127.0.0.1:{args.port}/index.html", timeout=120000)
            pg.wait_for_function("() => window.__done === true || false", timeout=600000, polling=1000)
            data = pg.evaluate("window.__sheet()")
            Path(args.out).write_bytes(base64.b64decode(data.split(",", 1)[1]))
            print(json.dumps({"out": args.out, "info": pg.evaluate("window.__info"), "errors": errors[:5]}))
            b.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
