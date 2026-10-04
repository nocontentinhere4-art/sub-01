"""A preview video of the room for the owner's approval (#98 G6; the coordinator's ask on #103): old vs new, side by
side and labelled, 30 fps H.264. Run by hand (no `test_` prefix):

    python tests/room_preview_video.py --old /path/to/a/main/checkout --out docs/design/room-render/preview

Each frame is one step of the page's own clock (1/30 s: his animation, the window, the lights, the camera cycle with
its cuts and dollies, exactly the loop's order) followed by one render and one screenshot of the viewport, so the video
shows what a viewer sees at 30 fps whatever the sandbox's software WebGL manages. Segments: 60 s of the camera cycle at
14:00 (he is at the window sill) and 30 s at 23:00 (the phone in bed, lights off), at 1280 x 800 and then at 390 x 844
(the phone, with its overlays). The new page runs on the high tier (`?post=high`). The old page is the `--old` checkout
(main), served by its own live_server. ffmpeg (/usr/bin/ffmpeg, libx264) stacks old | new, concatenates the desktop
and the phone parts, and the CRF is raised until the file is under --max-mb.
"""
import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.room_render_shots import HOURS, Run     # noqa: E402

FPS = 30
SEGMENTS = ((14, 60), (23, 30))                     # (hour, seconds)
SIZES = ((1280, 800, False), (390, 844, True))
if os.environ.get("PREVIEW_TEST"):                  # a 2 s + 1 s dry run at the desktop size, for the timing
    SEGMENTS, SIZES = ((14, 2), (23, 1)), ((1280, 800, False),)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
# one frame: his step, the window, the camera (a cut or a dolly, as the page's loop does it), the lights and the render.
# The page's loop is frozen (?debug FREEZE); sim(0, 1) is the page's own lighting + shadow update + render
STEP_JS = """([dt, hour]) => {
  animate_(dt); if (window.windowView) windowView.update(dt, hour);
  updateCameraGoal();
  if (window.CAM && CAM.cut) { camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); CAM.cut = false; }
  else { const k = 1 - Math.exp(-dt * 1.2); camera.position.lerp(camGoal.pos, k); controls.target.lerp(camGoal.target, k); }
  sim(0, 1);
  // the canvas's own pixels, read right after the render (a viewport screenshot waits on the compositor: 20 s a frame here)
  return [window.CAM ? CAM.kind : null, renderer.domElement.toDataURL("image/jpeg", 0.9)]; }"""
RECT_JS = "() => { const r = renderer.domElement.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }"
HUD_OFF = "#top,#side,#corner,#dock,#vignette,#away{display:none!important}"


def label(im, text):
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 22 if im.width > 600 else 15)
    w = d.textlength(text, font=f)
    x, y = 12, im.height - (40 if im.width > 600 else 28)
    d.rectangle([x - 8, y - 6, x + w + 8, y + (30 if im.width > 600 else 20)], fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=(255, 200, 80))
    return im


def overlays(pg):
    """The page around the canvas, once per segment: a screenshot with the HUD and one without; the pixels that differ
    are the overlays (title, plan, chip, panels), pasted over every frame's canvas."""
    import numpy as np
    from PIL import Image
    full = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", timeout=480000, animations="disabled"))).convert("RGB"))
    pg.evaluate(f"() => {{ const s = document.createElement('style'); s.id = 'hudoff'; s.textContent = {json.dumps(HUD_OFF)}; document.head.appendChild(s); }}")
    bare = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", timeout=480000, animations="disabled"))).convert("RGB"))
    pg.evaluate("() => { const s = document.getElementById('hudoff'); if (s) s.remove(); }")
    mask = (np.abs(full.astype(int) - bare.astype(int)).max(axis=2) > 10)
    return full, mask


def capture(run, out, tag, log=print):
    """Every segment at every size for one page: frames/<tag>_<w>/%05d.jpg (labelled), and a manifest of the shots."""
    import numpy as np
    from PIL import Image
    manifest = {}
    for w, h, mobile in SIZES:
        d = out / f"frames_{tag}_{w}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        n = 0
        for hour, secs in SEGMENTS:
            ctx, pg, errors = run.page(w, h, hour, mobile)
            run.settle(pg, hour)
            pg.evaluate("if (window.setShot) setShot(null); window.FREEZE = true")   # the cycle runs free; the loop is ours now
            page, mask = overlays(pg)
            x, y, cw, ch = pg.evaluate(RECT_JS)
            kinds, t0 = [], time.time()
            for i in range(secs * FPS):
                kind, data = pg.evaluate(STEP_JS, [1 / FPS, hour])
                canvas = Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))).convert("RGB")
                if canvas.size != (cw, ch):                                   # the page's adaptive pixel ratio
                    canvas = canvas.resize((cw, ch), Image.BILINEAR)
                frame = page.copy()
                frame[y:y + ch, x:x + cw] = np.asarray(canvas)
                frame[mask] = page[mask]
                im = label(Image.fromarray(frame), f"{tag}  {w} x {h}  {hour:02d}:00  {i / FPS:4.1f} s" + (f"  shot: {kind}" if kind else ""))
                im.save(d / f"{n:05d}.jpg", "JPEG", quality=90)
                n += 1
                if kind != (kinds[-1][1] if kinds else None):
                    kinds.append((round(i / FPS, 2), kind))
                if i % 150 == 0:
                    log(f"  {tag} {w} {hour:02d}:00 frame {i}/{secs * FPS} ({(time.time() - t0) / max(1, i):.2f} s/frame)", flush=True)
            manifest[f"{tag}_{w}_{hour}"] = {"frames": secs * FPS, "shots": kinds, "errors": errors[:5], "seconds": round(time.time() - t0, 1),
                                             "post": pg.evaluate("window.post ? post.info().tier : null")}
            ctx.close()
        manifest[f"{tag}_{w}"] = {"frames": n}
    return manifest


def encode(out, final, max_mb, log=print):
    """old | new side by side, the desktop part then the phone part (scaled to the desktop's height, centred)."""
    for crf in (26, 28, 30, 32, 34):
        cmd = ["/usr/bin/ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-framerate", str(FPS), "-i", str(out / "frames_old_1280" / "%05d.jpg"),
               "-framerate", str(FPS), "-i", str(out / "frames_new_1280" / "%05d.jpg"),
               "-framerate", str(FPS), "-i", str(out / "frames_old_390" / "%05d.jpg"),
               "-framerate", str(FPS), "-i", str(out / "frames_new_390" / "%05d.jpg"),
               "-filter_complex", "[0:v][1:v]hstack[top];[2:v][3:v]hstack,scale=-2:800,pad=2560:800:(ow-iw)/2:0[bot];[top][bot]concat=n=2:v=1:a=0[v]",
               "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)]
        subprocess.run(cmd, check=True)
        mb = final.stat().st_size / 1e6
        log(f"  encoded crf {crf}: {mb:.1f} MB", flush=True)
        if mb <= max_mb:
            return {"crf": crf, "mb": round(mb, 1)}
    return {"crf": crf, "mb": round(mb, 1), "over_budget": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="a checkout of main (the old page), served by its own live_server")
    ap.add_argument("--out", default="docs/design/room-render/preview")
    ap.add_argument("--frames", default=None, help="where the frames go (default: a temp dir; they are not committed)")
    ap.add_argument("--only", default=None, help="old or new: capture one side only (the other's frames must exist in --frames)")
    ap.add_argument("--encode-only", action="store_true")
    ap.add_argument("--max-mb", type=float, default=25)
    ap.add_argument("--port", type=int, default=8871)
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    frames = Path(args.frames) if args.frames else Path(os.environ.get("TMPDIR", "/tmp")) / "room-preview-frames"
    frames.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if not args.encode_only:
        if args.only in (None, "new"):
            with Run(port=args.port, post="high") as run:
                manifest.update(capture(run, frames, "new"))
        if args.only in (None, "old"):
            with Run(port=args.port + 1, root=args.old) as run:
                manifest.update(capture(run, frames, "old"))
        (frames / f"manifest_{args.only or 'all'}.json").write_text(json.dumps(manifest, indent=1))
    if args.only is None or args.encode_only:
        final = out / "room_preview_old_vs_new.mp4"
        enc = encode(frames, final, args.max_mb)
        for m in frames.glob("manifest_*.json"):
            manifest.update(json.loads(m.read_text()))
        manifest["encode"] = enc
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
        print("written", final, enc, flush=True)


if __name__ == "__main__":
    main()
