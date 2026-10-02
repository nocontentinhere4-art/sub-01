"""Screenshots of the character test page (web/boy_test.html) for #76: old/new comparisons and a frame strip per clip.

    python boy_shots.py [out/shots] [--docs] [--motion | --motion-only]   # needs `pip install playwright pillow` and a Chromium (PLAYWRIGHT_BROWSERS_PATH)

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
    if "--motion" in sys.argv: await motion_strips(port)


# the new motion set (boy2_motion.glb): a strip per clip, and the old clip above the new one where there was one
PAIRS = {"sit": "sit_idle_upright", "idle": "stand_idle", "walk": "walk", "sleep": "lie_back_idle", "eat": "sit_eat_chopsticks", "door": "door_open_pull"}
SEATED = ("sit_", "type", "mouse")
BEDS = ("lie_", "sleep_", "roll_", "get_up")


def cam_for(clip):
    if clip.startswith(BEDS) or clip in ("sleep",): return "T.bed(true); T.seat(false); T.view(0.3, 2.9, 1.3, 0, 0.8, 0, 36)"
    if clip.startswith(("sit_down_bed", "stand_up_bed", "sit_edge")) or clip == "lie_down_from_edge": return "T.bed(false); T.seat(false); T.view(2.2, 1.4, 2.0, 0, 0.8, -0.1, 36)"
    if clip.startswith(SEATED) or clip in ("sit", "eat", "sit_down_chair", "stand_up_chair"): return "T.bed(false); T.seat(true); T.view(2.0, 1.4, 2.0, 0, 0.8, -0.1, 34)"
    return "T.bed(false); T.seat(false); T.view(2.0, 1.4, 2.6, 0, 0.9, 0, 34)"


async def strip(pg, clip, label, frames=6):
    ims = []
    for i in range(frames):
        await pg.evaluate(f"{cam_for(clip.split(':')[-1])}; T.set('{clip}', {i / frames}, null, true)")
        f = OUT / "_f.png"; await pg.screenshot(path=str(f)); ims.append(Image.open(f).convert("RGB"))
    s = Image.new("RGB", (300 * frames, 340 + 22), (22, 23, 27)); d = ImageDraw.Draw(s)
    for i, im in enumerate(ims): s.paste(im, (i * 300, 22))
    d.text((6, 4), label, fill=(220, 220, 225)); return s


async def motion_strips(port):
    import re
    DOCS.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = await page_for(b, port, 300, 340, "boy=new")
        names = await pg.evaluate("Object.keys(T.chars[0].clips).filter(n => n.startsWith('m:')).map(n => n.slice(2))")
        sheet = []
        for n in names:
            st = await strip(pg, "m:" + n, f"{n} (new)"); st.save(OUT / f"motion_{n}.png"); sheet.append(st)
        old = await page_for(b, port, 300, 340, "boy=old")
        for o, n in PAIRS.items():
            if n not in names: continue
            a = await strip(old, o, f"{o} (old)"); c = Image.open(OUT / f"motion_{n}.png")
            pair = Image.new("RGB", (a.width, a.height + c.height)); pair.paste(a, (0, 0)); pair.paste(c, (0, a.height))
            pair.resize((pair.width // 2, pair.height // 2), Image.LANCZOS).save(DOCS / f"motion_vs_{o}.jpg", quality=80, optimize=True)
        # all new clips, half size, 4 per sheet
        for k in range(0, len(sheet), 4):
            part = sheet[k:k + 4]; h = sum(x.height for x in part); im = Image.new("RGB", (part[0].width, h)); y = 0
            for x in part: im.paste(x, (0, y)); y += x.height
            im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(DOCS / f"motion_{k // 4 + 1:02d}.jpg", quality=78, optimize=True)
        await b.close()


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
    if "--motion-only" in sys.argv:
        OUT.mkdir(parents=True, exist_ok=True); asyncio.run(motion_strips(serve()))
    else:
        asyncio.run(main())
