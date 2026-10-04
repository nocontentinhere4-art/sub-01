"""Before/after stills of the Tripo props: the room with the earlier props (`?props=old`) and with the Tripo ones, at the
visual QA's two sizes (1280 and 390), with the page's own loop frozen and both pages stepped alike, so each pair shows the
same moment. Shots: the overview, close-ups of the mug, the headphones on the hook, the sneakers, and him eating the
ramen. Writes docs/design/tripo/<size>_<shot>.webp, each the old frame over (390: beside) the new one.

    python room_build/tripo_stills.py          # from the repository root; needs what tests/visual needs
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, CHROMIUM          # noqa: E402
from tests.visual.fake_server import Server                 # noqa: E402

OUT = ROOT / "docs/design/tripo"
HOUR = 14
# name -> camera (position, target), or the harness's close-up recipe "hands"
SHOTS = {
    "overview": ((5.2, 5.0, 6.0), (0, 0.6, 0)),
    "mug": ((-0.30, 1.22, -0.62), (-0.50, 1.02, -0.98)),
    "headphones": ((-0.20, 1.45, -0.80), (-0.24, 1.36, -1.40)),
    "sneakers": ((1.05, 0.80, 0.75), (1.70, 0.22, 1.32)),
    "ramen": "hands",
}
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([8, 8, 20 + d.textlength(text, font=FONT), 40], fill=(0, 0, 0))
    d.text((14, 10), text, font=FONT, fill=(255, 255, 255))
    return im


def main():
    tmp = Path(tempfile.mkdtemp(prefix="tripo_stills_"))
    from playwright.sync_api import sync_playwright
    with Server() as server, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM if Path(CHROMIUM).exists() else None,
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for size in ("1280", "390"):
            shots = {}
            for tag, q in (("old", "&props=old"), ("new", "")):
                h = Harness(tmp / tag, log=lambda *a: None, cdn_cache=ROOT / "tests/visual/.cdn_cache")
                h.query = q; h.server = server; h.base = server.base; h.browser = browser
                server.set_scene("desk", HOUR)    # a fresh page must start the meal after the harness has cleared the desk
                ctx, pg, st = h.open(size)
                h.goto_scene(pg, "eating", HOUR)
                pg.evaluate("__qa.step(1/30, 60); __qa.hud(false)")
                for name, cam in SHOTS.items():
                    if cam == "hands":
                        pg.evaluate("__qa.closeup('hands')")
                    else:
                        (x, y, z), (a, b, c) = cam
                        pg.evaluate(f"camera.position.set({x}, {y}, {z}); controls.target.set({a}, {b}, {c}); controls.update()")
                    pg.evaluate("__qa.render()")
                    f = tmp / f"{size}_{tag}_{name}.png"
                    pg.screenshot(path=str(f), animations="disabled")
                    shots[(tag, name)] = f
                if st["errors"]:
                    print(f"{size} {tag}: page errors {st['errors'][:3]}")
                ctx.close()
            for name in SHOTS:
                old = label(Image.open(shots[("old", name)]).convert("RGB"), "before")
                new = label(Image.open(shots[("new", name)]).convert("RGB"), "after: Tripo")
                w, hh = old.size
                both = Image.new("RGB", (w, 2 * hh) if size == "1280" else (2 * w, hh))
                both.paste(old, (0, 0)); both.paste(new, (0, hh) if size == "1280" else (w, 0))
                if size == "1280":
                    both = both.resize((w * 3 // 4, hh * 3 // 2))
                both.save(OUT / f"{size}_{name}.webp", quality=82)
                print(OUT / f"{size}_{name}.webp")
        browser.close()


if __name__ == "__main__":
    main()
