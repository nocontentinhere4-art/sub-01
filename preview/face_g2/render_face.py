"""Render the G2 face sheet: BEFORE | AFTER at front, three-quarter and side, beside the detail references.

    python preview/face_g2/render_face.py [--branch origin/preview/room-mh] [--out preview/face_g2/face_sheet.jpg]

The dressed character, its hair and the hair shader are read from `--branch` with `git show` (web/room/boy.glb,
web/room/hair/hair_mh.glb, web/room/hair/hair_strands.js) and served to the page in memory: nothing of them is
copied here. The page (face.html) imports ../skin_eyes/body.js, so preview/ is the server's root. The real
references are the crops in refs/ and ../skin_eyes/refs/ (sources and licences in README.md).
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
PREVIEW = HERE.parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import CDN_HOSTS, cdn_router   # noqa: E402

FROM_BRANCH = {"boy_dressed.glb": "web/room/boy.glb", "hair_mh.glb": "web/room/hair/hair_mh.glb", "hair_strands.js": "web/room/hair/hair_strands.js"}
FROM_REF = {"g2_face_delta.json": ("9612b7b", "room_build/mh/glb/boy_g2_face_delta.json")}   # G2's adult face (preview/mh-motion)
DETAILS = [("d_eye", PREVIEW / "skin_eyes/refs/eye.jpg", "REAL eye (Pexels 946727)"),
           ("d_brow", HERE / "refs/brow.jpg", "REAL brow (Pexels 4823600)"),
           ("d_skin", PREVIEW / "skin_eyes/refs/skin.jpg", "REAL skin (Pexels 4046562)"),
           ("d_lips", HERE / "refs/lips.jpg", "REAL lips (Pexels 3749984)"),
           ("d_chin", HERE / "refs/stubble.jpg", "REAL stubble (Pexels 13072564, b/w)")]


def serve(blob, ctype):
    # (a route handler of its own: Playwright passes the request as a second argument to a two-parameter lambda)
    return lambda route: route.fulfill(status=200, body=blob, content_type=ctype)


def compose(panels, out):
    img = {k: Image.open(io.BytesIO(base64.b64decode(v.split(",", 1)[1]))).convert("RGB") for k, v in panels.items()}
    PW, PH, DW, DH, PAD, CAP = 600, 750, 400, 300, 12, 30
    W = 2 * PW + 2 * DW + 5 * PAD
    H = 3 * (PH + CAP + PAD) + PAD + 40
    sheet = Image.new("RGB", (W, H), (22, 22, 24))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except OSError:
        f = fb = ImageFont.load_default()
    x0, x1, x2, x3 = PAD, 2 * PAD + PW, 3 * PAD + 2 * PW, 4 * PAD + 2 * PW + DW
    d.text((x0, 10), "BEFORE (room-mh today)", fill=(240, 140, 120), font=fb)
    d.text((x1, 10), "AFTER", fill=(130, 220, 130), font=fb)
    d.text((x2, 10), "AFTER, detail", fill=(130, 220, 130), font=fb)
    d.text((x3, 10), "REAL, same detail", fill=(232, 190, 110), font=fb)
    for r, view in enumerate(["front", "three_quarter", "side"]):
        y = 40 + PAD + r * (PH + CAP + PAD)
        sheet.paste(img[f"before_{view}"], (x0, y)); sheet.paste(img[f"after_{view}"], (x1, y))
        label = view.replace("_", "-")
        d.text((x0 + 4, y + PH + 4), f"before, {label}", fill=(220, 220, 220), font=f)
        d.text((x1 + 4, y + PH + 4), f"after, {label}", fill=(220, 220, 220), font=f)
    for r, (key, ref, cap) in enumerate(DETAILS):                  # the details, stacked down the right
        dy = 40 + PAD + r * (DH + CAP + 2 * PAD)
        sheet.paste(img[key], (x2, dy))
        sheet.paste(Image.open(ref).convert("RGB").resize((DW, DH)), (x3, dy))
        d.text((x2 + 4, dy + DH + 4), "after, " + key[2:], fill=(220, 220, 220), font=f)
        d.text((x3 + 4, dy + DH + 4), cap, fill=(232, 190, 110), font=f)
    sheet.save(out, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="origin/preview/room-mh")
    ap.add_argument("--out", default=str(HERE / "face_sheet.jpg"))
    ap.add_argument("--port", type=int, default=8933)
    ap.add_argument("--chromium", default=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"))
    args = ap.parse_args()
    blobs = {k: subprocess.run(["git", "show", f"{args.branch}:{p}"], cwd=ROOT, check=True, capture_output=True).stdout for k, p in FROM_BRANCH.items()}
    blobs.update({k: subprocess.run(["git", "show", f"{ref}:{p}"], cwd=ROOT, check=True, capture_output=True).stdout for k, (ref, p) in FROM_REF.items()})
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PREVIEW))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=args.chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = b.new_page(viewport={"width": 700, "height": 800}, ignore_https_errors=True)
            for h in CDN_HOSTS:
                pg.route(f"https://{h}/**", cdn_router(os.environ.get("SUB01_CDN_CACHE", "/tmp/sub01-cdn-cache")))
            for name, blob in blobs.items():
                ctype = "text/javascript" if name.endswith(".js") else "application/json" if name.endswith(".json") else "model/gltf-binary"
                pg.route(f"**/face_g2/{name}", serve(blob, ctype))
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.goto(f"http://127.0.0.1:{args.port}/face_g2/face.html", timeout=120000, wait_until="commit")   # (the module renders before "load")
            for _ in range(1200):
                if pg.evaluate("window.__done === true"):
                    break
                if errors:
                    sys.exit("page error: " + " | ".join(errors[:5]))
                pg.wait_for_timeout(1000)
            compose(pg.evaluate("window.__panels()"), args.out)
            panels = pg.evaluate("window.__panels()")
            strip = Image.new("RGB", (3 * 600 + 4 * 12, 220 + 50), (22, 22, 24)); sd = ImageDraw.Draw(strip)
            try:
                sf = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            except OSError:
                sf = ImageFont.load_default()
            for i, c in enumerate((0, 50, 100)):
                strip.paste(Image.open(io.BytesIO(base64.b64decode(panels[f"blink_{c}"].split(",", 1)[1]))).convert("RGB"), (12 + i * 612, 12))
                sd.text((16 + i * 612, 238), f"blink: lids {c} % closed", fill=(220, 220, 220), font=sf)
            strip.save(HERE / "blink_strip.jpg", quality=88)
            hc = Image.new("RGB", (2 * 500 + 3 * 12, 2 * 375 + 3 * 12 + 60), (22, 22, 24)); hd = ImageDraw.Draw(hc)
            for c, nm in enumerate(("before", "after")):
                hd.text((12 + c * 512, 8), "BEFORE (MakeHuman face)" if nm == "before" else "AFTER (G2's adult face)", fill=(220, 220, 220), font=sf)
                for r, view in enumerate(("front", "side")):
                    hc.paste(Image.open(io.BytesIO(base64.b64decode(panels[f"hair_{view}_{nm}"].split(",", 1)[1]))).convert("RGB"), (12 + c * 512, 40 + r * 387))
            hc.save(HERE / "hair_check.jpg", quality=88)
            print(json.dumps({"out": args.out, "info": pg.evaluate("window.__info"), "errors": errors[:5]}, default=str)[:4000])
            b.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
