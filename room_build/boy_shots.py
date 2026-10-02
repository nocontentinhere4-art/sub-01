"""Screenshots of the character test page (web/boy_test.html) for #76: old/new comparisons and a frame strip per clip.

    python boy_shots.py [out/shots] [--docs]   # needs `pip install playwright pillow` and a Chromium (PLAYWRIGHT_BROWSERS_PATH)

Serves web/ on a local port; three.js comes from room_build/node_modules (npm install) instead of the CDN, so it runs
offline. Writes compare_<clip>_<width>.png (old left, new right), strip_<clip>.png (new, 6 frames) and info.json;
--docs also composes the small JPEGs the PR shows (docs/character/).
"""
import asyncio, functools, http.server, json, os, sys, threading
from pathlib import Path
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "web"
THREE = HERE / "node_modules" / "three"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(ARGS[0]) if ARGS else HERE / "out" / "shots"
DOCS = HERE.parent / "docs" / "character"
CHROMIUM = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")
# clip, time (fraction of the clip), camera (x, y, z, target x, y, z, fov), seat shown
SHOTS = {
    "walk": (0.3, (0.9, 1.25, 4.0, 0, 0.9, 0, 30), False),
    "sit": (0.25, (1.6, 1.2, 3.6, 0, 0.7, -0.1, 30), True),
    "sleep": (0.3, (0.4, 2.6, 3.2, 0, 0.6, -0.4, 34), False),
    "eat": (0.4, (1.6, 1.2, 3.6, 0, 0.7, -0.1, 30), True),
    "hold": (0.5, (0.9, 1.3, 3.6, 0, 1.0, 0, 30), False),
    "idle": (0.3, (0.9, 1.25, 4.0, 0, 0.9, 0, 30), False),
    "door": (0.4, (0.9, 1.25, 4.0, 0, 0.9, 0, 30), False),
}


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Quiet, directory=str(WEB))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_address[1]


async def page_for(browser, port, width, height, query):
    pg = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)

    async def cdn(route):
        f = THREE / route.request.url.split("three@0.169.0/", 1)[1]
        await (route.fulfill(path=str(f), content_type="text/javascript") if f.is_file() else route.abort())
    await pg.route("https://cdn.jsdelivr.net/npm/three@0.169.0/**", cdn)
    pg.on("pageerror", lambda e: print("pageerror", e))
    await pg.goto(f"http://127.0.0.1:{port}/boy_test.html?shot&{query}")
    await pg.wait_for_function("window.T && T.ready", timeout=120000)
    return pg


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    port = serve()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        info = {}
        for width, height in ((1280, 800), (390, 844)):
            pg = await page_for(b, port, width, height, "cmp")
            info = await pg.evaluate("T.info()")
            for clip, (frac, cam, seat) in SHOTS.items():
                x, y, z, tx, ty, tz, fov = cam
                if width < 600: fov += 22                     # a phone: portrait, so widen the view
                await pg.evaluate(f"T.apart(0.9, 0); T.seat({str(seat).lower()}); T.view({x},{y},{z},{tx},{ty},{tz},{fov}); T.set('{clip}', {frac}, null, true)")
                await pg.screenshot(path=str(OUT / f"compare_{clip}_{width}.png"))
            await pg.close()
        # frame strips: the new one alone, 6 moments of each clip
        pg = await page_for(b, port, 360, 560, "boy=new")
        for clip, (frac, cam, seat) in SHOTS.items():
            x, y, z, tx, ty, tz, fov = cam
            frames = []
            for i in range(6):
                await pg.evaluate(f"T.seat({str(seat).lower()}); T.view({x},{y},{z},{tx},{ty},{tz},{fov + 4}); T.set('{clip}', {i / 6}, null, true)")
                f = OUT / f"_f{i}.png"; await pg.screenshot(path=str(f)); frames.append(Image.open(f).convert("RGB"))
            strip = Image.new("RGB", (360 * 6, 560 + 26), (22, 23, 27)); d = ImageDraw.Draw(strip)
            for i, im in enumerate(frames):
                strip.paste(im, (i * 360, 26)); d.text((i * 360 + 8, 6), f"{clip}  {i}/6", fill=(220, 220, 225))
            strip.save(OUT / f"strip_{clip}.png")
            for f in OUT.glob("_f*.png"): f.unlink()
        (OUT / "info.json").write_text(json.dumps(info, indent=1))
        await b.close()
    print(json.dumps(info))
    if "--docs" in sys.argv: docs()


def docs():
    """The PR's pictures: old | new for the five scenes the issue asks for, at 1280 and 390 px, and the strips."""
    DOCS.mkdir(parents=True, exist_ok=True)
    scenes = ["walk", "sit", "sleep", "eat", "hold"]
    labels = {"walk": "walking", "sit": "sitting at the desk", "sleep": "lying in bed", "eat": "eating", "hold": "texting"}
    for width, (w, h), cols in ((1280, (640, 400), 2), (390, (195, 422), 5)):
        rows = -(-len(scenes) // cols)
        sheet = Image.new("RGB", (w * cols, (h + 22) * rows), (22, 23, 27)); d = ImageDraw.Draw(sheet)
        for i, sc in enumerate(scenes):
            im = Image.open(OUT / f"compare_{sc}_{width}.png").convert("RGB").resize((w, h), Image.LANCZOS)
            x, y = (i % cols) * w, (i // cols) * (h + 22)
            sheet.paste(im, (x, y + 22)); d.text((x + 6, y + 5), f"{labels[sc]} (old left, new right)", fill=(220, 220, 225))
        sheet.save(DOCS / f"compare_{width}.jpg", quality=82, optimize=True)
    for f in OUT.glob("strip_*.png"):
        im = Image.open(f).convert("RGB"); im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        im.save(DOCS / (f.stem + ".jpg"), quality=80, optimize=True)


if __name__ == "__main__":
    asyncio.run(main())
