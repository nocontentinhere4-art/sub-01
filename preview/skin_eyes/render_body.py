"""Render the skin, eyes and hands on G2's body (body.html) beside the real reference photos: body_sheet.jpg.

    python preview/skin_eyes/render_body.py [--glb PATH] [--out preview/skin_eyes/body_sheet.jpg]

The body is G2's room_build/mh/glb/boy_g2.glb; by default it is read from the preview/mh-motion branch with
`git show` and served to the page in memory (no copy of it is committed here). The references are the crops in refs/
(sources and licences in README.md). Each row: the render on the left, the real photo on the right.
"""
import argparse
import base64
import functools
import http.server
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import CDN_HOSTS, cdn_router   # noqa: E402

# panel order in body.html, the reference crop beside it, and the row's caption
ROWS = [
    ("eye, his left, lamp light", "refs/eye.jpg", "REAL eye (Pexels 946727)"),
    ("cheek patch at 6 cm, daylight", "refs/skin.jpg", "REAL skin (Pexels 4046562)"),
    ("back of the right hand", "refs/hand.jpg", "REAL hand (Pexels 7298848)"),
    ("fingertips and nails", "refs/nails.jpg", "REAL fingertips (Pexels 7479569)"),
]
PW, PH, PAD, CAP = 900, 675, 12, 34


def compose(panels, out):
    sheet = Image.new("RGB", (2 * PW + 3 * PAD, len(ROWS) * (PH + CAP + PAD) + PAD), (24, 24, 26))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for r, ((cap3d, ref, capref), png) in enumerate(zip(ROWS, panels)):
        y = PAD + r * (PH + CAP + PAD)
        sheet.paste(png.resize((PW, PH)), (PAD, y))
        sheet.paste(Image.open(HERE / ref).convert("RGB").resize((PW, PH)), (2 * PAD + PW, y))
        d.text((PAD + 4, y + PH + 5), "3D  " + cap3d, fill=(220, 220, 220), font=font)
        d.text((2 * PAD + PW + 4, y + PH + 5), capref, fill=(232, 190, 110), font=font)
    sheet.save(out, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=None, help="boy_g2.glb (default: git show origin/preview/mh-motion:...)")
    ap.add_argument("--out", default=str(HERE / "body_sheet.jpg"))
    ap.add_argument("--port", type=int, default=8932)
    ap.add_argument("--chromium", default=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"))
    args = ap.parse_args()
    glb = Path(args.glb).read_bytes() if args.glb else subprocess.run(
        ["git", "show", "origin/preview/mh-motion:room_build/mh/glb/boy_g2.glb"], cwd=ROOT, check=True, capture_output=True).stdout
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=args.chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            print("launched", flush=True)
            pg = b.new_page(viewport={"width": 1000, "height": 800}, ignore_https_errors=True)
            for h in CDN_HOSTS:
                pg.route(f"https://{h}/**", cdn_router(os.environ.get("SUB01_CDN_CACHE", "/tmp/sub01-cdn-cache")))
            pg.route("**/boy_g2.glb", lambda route: route.fulfill(status=200, body=glb, content_type="model/gltf-binary"))
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.goto(f"http://127.0.0.1:{args.port}/body.html", timeout=120000, wait_until="commit")
            print("opened", flush=True)
            for _ in range(900):
                if pg.evaluate("window.__done === true"):
                    break
                if errors:
                    sys.exit("page error: " + " | ".join(errors[:5]))
                if _ % 20 == 0:
                    print("stage", pg.evaluate("window.__stage"), flush=True)
                pg.wait_for_timeout(1000)
            panels = [Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1]))).convert("RGB") for u in pg.evaluate("window.__panels()")]
            if os.environ.get("SUB01_PANELS"):
                for i, im in enumerate(panels):
                    im.save(Path(os.environ["SUB01_PANELS"]) / f"panel{i}.jpg", quality=92)
            compose(panels, args.out)
            print(json.dumps({"out": args.out, "info": pg.evaluate("window.__info"), "errors": errors[:5]}, default=str)[:3000])
            b.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
