"""A preview video of the room for the owner's approval (#98 G6; the coordinator's ask on #103): old vs new, side by
side and labelled, H.264. Run by hand (no `test_` prefix):

    python tests/room_preview_video.py --old /path/to/a/main/checkout --side new --hour 14 --frames /tmp/pf   # one side, one segment
    python tests/room_preview_video.py --old ... --side old --hour 14 --frames /tmp/pf                         # (in parallel)
    python tests/room_preview_video.py --encode-only --frames /tmp/pf --out docs/design/room-render/preview

Each frame is one step of the page's own clock (1/FPS s: his animation, the window, the lights, the camera's cuts and
dollies in the loop's order) followed by one render, so the video shows what a viewer sees at FPS whatever the
sandbox's software WebGL manages (about 5 s a frame for the new page's high tier at 1280 x 800, so the sides and the
segments run as separate processes). The canvas's own pixels are read back after the render; the page's overlays
(title, plan, chip, panels) are screenshot once per segment and composited over every frame. Segments (the short
preview): 15 s at 14:00 at the window sill, the new page's shots forced in turn (medium, face, overview, 5 s each) so
all three are seen, and 8 s at 23:00 with the phone in bed (over the shoulder, then his face); the old page follows
him as it always did. 1280 x 800 only (the phone is covered by the after_390_*.jpg stills). The new page runs on the
high tier (`?post=high`); the old page is the `--old` checkout (main), served by its own live_server. ffmpeg
(/usr/bin/ffmpeg, libx264) stacks old | new and raises the CRF until the file is under --max-mb.
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
from tests.room_render_shots import Run     # noqa: E402

FPS = 15
SEGMENTS = {14: 15, 23: 8}                           # hour -> seconds
SHOTS_AT = {14: ((0, "medium"), (5, "face"), (10, "overview")), 23: ((0, "over"), (4, "face"))}   # the new page's shots, forced by time
W, H = 1280, 800
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
# one frame: his step, the window, the camera (a cut or a dolly, as the page's loop does it), the lights and the render.
# The page's loop is frozen (?debug FREEZE); sim(0, 1) is the page's own lighting + shadow update + render, and runs
# every third frame (the 2048 px sun shadow map costs seconds in software GL); the other frames only render
STEP_JS = """([dt, hour, full, force]) => {
  animate_(dt); if (window.windowView) windowView.update(dt, hour);
  if (window.setShot && force !== undefined) setShot(force);
  updateCameraGoal();
  if (window.CAM && CAM.cut) { camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); CAM.cut = false; }
  else { const k = 1 - Math.exp(-dt * 1.2); camera.position.lerp(camGoal.pos, k); controls.target.lerp(camGoal.target, k); }
  if (full) sim(0, 1); else { controls.update(); if (window.post) post.render(dt); else renderer.render(scene, camera); }
  return [window.CAM ? CAM.kind : null, renderer.domElement.toDataURL("image/jpeg", 0.9)]; }"""
SHADOW_EVERY = 3
RECT_JS = "() => { const r = renderer.domElement.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }"
HUD_OFF = "#top,#side,#corner,#dock,#vignette,#away{display:none!important}"


def label(im, text):
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 22)
    w = d.textlength(text, font=f)
    x, y = 12, im.height - 40
    d.rectangle([x - 8, y - 6, x + w + 8, y + 30], fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=(255, 200, 80))
    return im


def overlays(pg):
    """The page around the canvas, once per segment: a screenshot with the HUD and one without; the pixels that differ
    are the overlays, pasted over every frame's canvas."""
    import numpy as np
    from PIL import Image
    full = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", timeout=480000, animations="disabled"))).convert("RGB"))
    pg.evaluate(f"() => {{ const s = document.createElement('style'); s.id = 'hudoff'; s.textContent = {json.dumps(HUD_OFF)}; document.head.appendChild(s); }}")
    bare = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", timeout=480000, animations="disabled"))).convert("RGB"))
    pg.evaluate("() => { const s = document.getElementById('hudoff'); if (s) s.remove(); }")
    mask = (np.abs(full.astype(int) - bare.astype(int)).max(axis=2) > 10)
    return full, mask


def shot_at(hour, t):
    k = None
    for t0, kind in SHOTS_AT.get(hour, ()):
        if t >= t0:
            k = kind
    return k


def capture(run, out, side, hour, log=print):
    """One segment of one page: frames/<side>_<hour>/%05d.jpg (labelled) and a manifest of the shots."""
    import numpy as np
    from PIL import Image
    d = Path(out) / f"frames_{side}_{hour:02d}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    secs = SEGMENTS[hour]
    ctx, pg, errors = run.page(W, H, hour, False)
    run.settle(pg, hour)
    pg.evaluate("if (window.setShot) setShot(null); window.FREEZE = true")   # the loop is ours now
    page, mask = overlays(pg)
    x, y, cw, ch = pg.evaluate(RECT_JS)
    kinds, t0 = [], time.time()
    name = {"old": "main (old)", "new": "#103 (new)"}[side]
    for i in range(secs * FPS):
        t = i / FPS
        kind, data = pg.evaluate(STEP_JS, [1 / FPS, hour, i % SHADOW_EVERY == 0, shot_at(hour, t) if side == "new" else None])
        canvas = Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))).convert("RGB")
        if canvas.size != (cw, ch):                                       # the page's adaptive pixel ratio
            canvas = canvas.resize((cw, ch), Image.BILINEAR)
        frame = page.copy()
        frame[y:y + ch, x:x + cw] = np.asarray(canvas)
        frame[mask] = page[mask]
        im = label(Image.fromarray(frame), f"{name}   {hour:02d}:00   {t:4.1f} s" + (f"   shot: {kind}" if kind else "   camera: follows him"))
        im.save(d / f"{i:05d}.jpg", "JPEG", quality=90)
        if kind != (kinds[-1][1] if kinds else None):
            kinds.append((round(t, 2), kind))
        if i % 30 == 0:
            log(f"  {side} {hour:02d}:00 frame {i}/{secs * FPS} ({(time.time() - t0) / max(1, i):.2f} s/frame)", flush=True)
    r = {"frames": secs * FPS, "fps": FPS, "shots": kinds, "errors": errors[:5], "seconds": round(time.time() - t0, 1),
         "post": pg.evaluate("window.post ? post.info().tier : null")}
    ctx.close()
    (Path(out) / f"manifest_{side}_{hour:02d}.json").write_text(json.dumps(r, indent=1))
    return r


def encode(frames, final, max_mb, log=print):
    """old | new side by side, the 14:00 segment then the 23:00 one (a sorted glob over both frame folders)."""
    frames = Path(frames)
    for crf in (24, 26, 28, 30, 32, 34):
        cmd = ["/usr/bin/ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-framerate", str(FPS), "-pattern_type", "glob", "-i", str(frames / "frames_old_*" / "*.jpg"),
               "-framerate", str(FPS), "-pattern_type", "glob", "-i", str(frames / "frames_new_*" / "*.jpg"),
               "-filter_complex", "[0:v][1:v]hstack,format=yuv420p,setsar=1[v]",
               "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)]
        subprocess.run(cmd, check=True)
        mb = final.stat().st_size / 1e6
        log(f"  encoded crf {crf}: {mb:.1f} MB", flush=True)
        if mb <= max_mb:
            return {"crf": crf, "mb": round(mb, 1)}
    return {"crf": crf, "mb": round(mb, 1), "over_budget": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default=None, help="a checkout of main (the old page), served by its own live_server")
    ap.add_argument("--out", default="docs/design/room-render/preview")
    ap.add_argument("--frames", required=True, help="where the frames go (not committed)")
    ap.add_argument("--side", choices=("old", "new"), default=None)
    ap.add_argument("--hour", type=int, choices=tuple(SEGMENTS), default=None)
    ap.add_argument("--encode-only", action="store_true")
    ap.add_argument("--max-mb", type=float, default=25)
    ap.add_argument("--port", type=int, default=8871)
    args = ap.parse_args()
    frames = Path(args.frames)
    frames.mkdir(parents=True, exist_ok=True)
    if not args.encode_only:
        if not args.side or not args.hour:
            sys.exit("--side and --hour (or --encode-only)")
        if args.side == "old" and not args.old:
            sys.exit("--old is the main checkout")
        with Run(port=args.port, post="high" if args.side == "new" else None, root=args.old if args.side == "old" else None) as run:
            capture(run, frames, args.side, args.hour)
        return
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    final = out / "room_preview_old_vs_new.mp4"
    manifest = {"fps": FPS, "size": [W, H], "segments": SEGMENTS, "encode": encode(frames, final, args.max_mb)}
    for m in sorted(frames.glob("manifest_*.json")):
        manifest[m.stem[len("manifest_"):]] = json.loads(m.read_text())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("written", final, manifest["encode"], flush=True)


if __name__ == "__main__":
    main()
