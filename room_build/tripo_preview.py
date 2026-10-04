"""The Tripo props' preview video: the room with the earlier props (left, `?props=old`) and the Tripo ones (right), side by
side, 30 fps, every frame stepped with the visual QA harness (`__qa.step(1/30, 1)`, the page's own loop frozen), so both
halves show the same moment. Shots: the overview, the mug on the desk, the headphones on the hook, the sneakers, then
him eating the ramen. Needs what tests/visual needs (Playwright, Chromium) and ffmpeg.

    python room_build/tripo_preview.py --out docs/design/tripo/tripo_props_preview.mp4      # from the repository root
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM          # noqa: E402
from tests.visual.fake_server import Server                 # noqa: E402

W, H, FPS = 960, 540, 30
# (name, seconds, camera from, camera to): a camera is (position, target), or "hands" for the harness's close-up on them
SHOTS = [
    ("overview", 3.0, ((5.2, 5.0, 6.0), (0, 0.6, 0)), ((4.6, 4.2, 5.4), (0, 0.6, 0))),
    ("mug", 3.0, ((-0.15, 1.30, -0.55), (-0.55, 1.0, -1.0)), ((-0.30, 1.22, -0.62), (-0.50, 1.02, -0.98))),
    ("headphones", 2.5, ((0.05, 1.50, -0.65), (-0.24, 1.38, -1.40)), ((-0.20, 1.45, -0.80), (-0.24, 1.36, -1.40))),
    ("sneakers", 2.5, ((0.80, 1.05, 0.55), (1.70, 0.22, 1.32)), ((1.05, 0.80, 0.75), (1.70, 0.22, 1.32))),
    ("ramen", 4.0, "hands", "hands"),
]


def lerp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs/design/tripo/tripo_props_preview.mp4"))
    ap.add_argument("--hour", type=int, default=14)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="tripo_preview_"))
    from playwright.sync_api import sync_playwright
    with Server() as server, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM if Path(CHROMIUM).exists() else None,
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pages = []
        for tag, q in (("old", "&props=old"), ("new", "")):
            h = Harness(tmp / tag, log=lambda *a: None, cdn_cache=ROOT / "tests/visual/.cdn_cache")
            h.query = q; h.server = server; h.base = server.base; h.browser = browser
            ctx, pg, st = h.open("1280")
            pg.set_viewport_size({"width": W, "height": H})
            h.goto_scene(pg, "eating", args.hour)
            pg.evaluate("__qa.hud(false)")
            pages.append((tag, pg, st))
        f1, f2 = font(26), font(18)
        n = 0
        for name, secs, a, b in SHOTS:
            frames = int(round(secs * FPS))
            for i in range(frames):
                t = i / max(1, frames - 1); t = t * t * (3 - 2 * t)          # ease in and out
                halves = []
                for tag, pg, st in pages:
                    pg.evaluate("__qa.step(1/30, 1)")
                    if a == "hands":
                        pg.evaluate("__qa.closeup('hands')")
                    else:
                        pos, tgt = lerp(a[0], b[0], t), lerp(a[1], b[1], t)
                        pg.evaluate(f"camera.position.set({pos[0]}, {pos[1]}, {pos[2]}); controls.target.set({tgt[0]}, {tgt[1]}, {tgt[2]}); controls.update()")
                    pg.evaluate("__qa.render()")
                    shot = tmp / f"{tag}.png"
                    pg.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": W, "height": H}, animations="disabled")
                    halves.append(Image.open(shot).convert("RGB"))
                frame = Image.new("RGB", (2 * W, H))
                frame.paste(halves[0], (0, 0)); frame.paste(halves[1], (W, 0))
                d = ImageDraw.Draw(frame)
                for x, label in ((0, "before"), (W, "after: made with Tripo (paid API)")):
                    d.rectangle([x + 12, 12, x + 24 + d.textlength(label, font=f1), 50], fill=(0, 0, 0))
                    d.text((x + 18, 15), label, font=f1, fill=(255, 255, 255))
                d.text((2 * W - 18 - d.textlength(name, font=f2), H - 32), name, font=f2, fill=(255, 255, 255))
                frame.save(tmp / f"f{n:05d}.png"); n += 1
        for tag, pg, st in pages:
            if st["errors"]:
                print(f"{tag}: page errors {st['errors'][:3]}")
        browser.close()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    ff = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(tmp / "f%05d.png"), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    print(out, f"{n} frames, {out.stat().st_size / 1e6:.1f} MB")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
