"""Preview video of a motion change for the owner's approval (#98 G3): old (main) vs new, side by side, two cameras.

    python tests/motion_preview.py --old <main checkout>/web --new web --out docs/screens/motion/preview/clearance.mp4

Each version's room.html runs headless (?debug&nolive, the page clock stepped frame by frame with __qa.step(1/30) from
tests/visual/page_checks.js, software WebGL), through the scenes below; every frame is rendered from the page's own
follow camera and from a fixed close shot, then the four views (old | new, default over close) are laid out on one
1280x720 frame with labels and encoded at 30 fps H.264 with /usr/bin/ffmpeg. The CDN scripts come from
room_build/node_modules.
"""
import argparse
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NM = ROOT / "room_build" / "node_modules"
HERE = Path(__file__).resolve().parent
# name -> (setup JS run after the page is ready and seeded, frames recorded after it, the frame the close shot is set at)
SCENES = {
    "walk from the window past the bed": ("act('window', {activity:'window', place:'room'}); __qa.step(1/30, 30); live('order_food', {activity:'order_food', place:'room'});", 105, 12),
    "stretch beside the desk": ("act('research', {activity:'research', place:'room'}); live('get_delivery', {activity:'get_delivery', place:'room'}); __qa.step(1/30, 950); variant('stretch');", 135, 20),
}
# the close shot: of eight directions round him at four distances, the longest clear line of sight to his head and hips
# (rays against the room; his own meshes and glass ignored), set once per scene and held
CLOSE = """() => { const b = window.boy; const t = new THREE.Vector3(); b.getWorldPosition(t); t.y += 0.7;
  const tall = [[-0.12, 0.32, -1.45, -1.17], [0.45, 0.93, -1.45, -0.97], [-1.9, -1.84, -0.62, 0.9]];
  const inTall = p => tall.some(([x0, x1, z0, z1]) => p.x > x0 - 0.15 && p.x < x1 + 0.15 && p.z > z0 - 0.15 && p.z < z1 + 0.15);
  const box = p => { p.x = Math.min(1.85, Math.max(-1.75, p.x)); p.z = Math.min(1.5, Math.max(-1.3, p.z)); p.y = Math.min(2.3, p.y); return p; };
  const ray = new THREE.Raycaster(), ofBoy = o => { for (; o; o = o.parent) if (o === b) return true; return false; };
  const clear = (c, p) => { const d = p.clone().sub(c), len = d.length(); ray.set(c, d.normalize()); ray.far = len - 0.35;
    const h = ray.intersectObjects(scene.children, true).find(h => h.object.visible && !ofBoy(h.object) && !(h.object.material && h.object.material.transparent && h.object.material.opacity < 0.6));
    return h ? h.distance / len : 1; };
  const r = b.rotation.y; let best = null;
  for (const a of [0.7, -0.7, 1.2, -1.2, 0.2, -0.2, 1.8, -1.8, 2.5, -2.5, 3.1]) for (const s of [2.4, 1.9, 1.5]) for (const h of [0.5, 0.1]) {
    const d = new THREE.Vector3(Math.sin(r + a), 0, Math.cos(r + a)), c = box(t.clone().addScaledVector(d, s).add(new THREE.Vector3(0, h, 0)));
    const far = c.distanceTo(t), open = Math.min(clear(c, t), clear(c, t.clone().add(new THREE.Vector3(0, -0.6, 0))));
    const score = far * open - (Math.abs(a) > 1.5 ? 0.4 : 0) - (inTall(c) ? 5 : 0);
    if (!best || score > best.score) best = {c, score}; }
  return {pos: best.c.toArray(), target: t.toArray()}; }"""
SET_CAM = "([p, t, fov]) => { camera.fov = fov; camera.updateProjectionMatrix(); camera.position.set(...p); controls.target.set(...t); controls.update(); }"


def serve(web, port):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(web), **k)

        def log_message(self, *a):
            pass
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def record(web, port, frames_dir, tag, chromium, seed, log):
    """Render every scene of one version: <frames_dir>/<tag>_<scene index>_<cam>_<frame>.png; returns the frame counts."""
    from playwright.sync_api import sync_playwright
    srv = serve(web, port)
    counts = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)

            def cdn(route, request):
                url = request.url
                if "three@0.169.0/" in url:
                    path = NM / "three" / url.split("three@0.169.0/", 1)[1]
                elif "leaflet@1.9.4/dist/" in url:
                    path = NM / "leaflet" / "dist" / url.split("dist/", 1)[1]
                else:
                    return route.abort()
                ct = "text/javascript" if path.suffix == ".js" else "text/css"
                return route.fulfill(path=str(path), content_type=ct) if path.exists() else route.abort()
            pg.route("**/cdn.jsdelivr.net/**", cdn)
            pg.route("**/unpkg.com/**", cdn)
            pg.route("**/api/**", lambda r: r.fulfill(status=404, body=""))
            pg.route("**/tokyo_*.json", lambda r: r.fulfill(status=404, body=""))
            pg.goto(f"http://127.0.0.1:{port}/room.html?debug&nolive&hour=14", wait_until="load")
            pg.wait_for_function("window.boy && window.room && window.actions && ['walk','idle','door','eat','sleep','stand'].every(k => window.actions[k]) && (!window.motion || window.motion.ready)", timeout=180000)
            pg.evaluate("window.FREEZE = true")
            pg.add_script_tag(content=(HERE / "visual" / "page_checks.js").read_text())
            pg.evaluate("s => { settle(); setSeed(s); __qa.hideMarkers(); __qa.hud(false); }", seed)
            for si, (name, (setup, n, close_at)) in enumerate(SCENES.items()):
                pg.evaluate(setup)
                close = None
                for f in range(n):
                    pg.evaluate("__qa.step(1/30, 1)")
                    if f == close_at or (close is None and f == n - 1):
                        close = pg.evaluate(CLOSE)
                    for cam in ("default", "close"):
                        if cam == "default":
                            pg.evaluate("__qa.followCam()")
                        elif close:
                            pg.evaluate(SET_CAM, [close["pos"], close["target"], 46])
                        else:
                            continue
                        pg.evaluate("__qa.render()")
                        pg.screenshot(path=str(frames_dir / f"{tag}_{si}_{cam}_{f:04d}.png"), timeout=120000)
                    if f % 30 == 0:
                        log(f"  {tag} {name}: frame {f}/{n}")
                counts[si] = n
            browser.close()
    finally:
        srv.shutdown()
    return counts


def compose(frames_dir, out_dir, counts, log):
    """old | new, the follow camera over the close shot, labels; one 1280x720 PNG per output frame."""
    from PIL import Image, ImageDraw
    k = 0
    for si, name in enumerate(SCENES):
        for f in range(counts[si]):
            S = Image.new("RGB", (1280, 720), (8, 8, 10))
            d = ImageDraw.Draw(S)
            for col, tag in enumerate(("old", "new")):
                for row, cam in enumerate(("default", "close")):
                    p = frames_dir / f"{tag}_{si}_{cam}_{f:04d}.png"
                    if p.exists():
                        im = Image.open(p).convert("RGB").resize((640, 360))
                        S.paste(im, (col * 640, row * 360))
                    d.rectangle((col * 640, row * 360, col * 640 + 230, row * 360 + 18), fill=(0, 0, 0))
                    d.text((col * 640 + 6, row * 360 + 3), f"{'main (old)' if tag == 'old' else 'this PR (new)'} - {cam} camera", fill=(255, 220, 120) if tag == "new" else (200, 200, 210))
            d.rectangle((0, 702, 1280, 720), fill=(0, 0, 0))
            d.text((6, 705), f"{name}   {f / 30:.2f} s   (page clock stepped at 1/30 s, software WebGL)", fill=(230, 230, 235))
            S.save(out_dir / f"c_{k:05d}.png")
            k += 1
        log(f"  composed {name}: {counts[si]} frames")
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="web/ of a checkout of main")
    ap.add_argument("--new", default=str(ROOT / "web"))
    ap.add_argument("--out", default="docs/screens/motion/preview/clearance.mp4")
    ap.add_argument("--work", default="", help="frame directory (default: a temporary one)")
    ap.add_argument("--port", type=int, default=8840)
    ap.add_argument("--seed", type=int, default=63)
    ap.add_argument("--chromium", default=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"))
    ap.add_argument("--ffmpeg", default="/usr/bin/ffmpeg")
    args = ap.parse_args()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(args.work) if args.work else out.parent / ".frames"
    frames, comp = work / "frames", work / "composed"
    for d in (frames, comp):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    log = lambda *a: print(*a, flush=True)  # noqa: E731
    counts = record(Path(args.old).resolve(), args.port, frames, "old", args.chromium, args.seed, log)
    counts2 = record(Path(args.new).resolve(), args.port + 1, frames, "new", args.chromium, args.seed, log)
    assert counts == counts2, (counts, counts2)
    n = compose(frames, comp, counts, log)
    subprocess.run([args.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", "30", "-i", str(comp / "c_%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "medium", "-movflags", "+faststart", str(out)], check=True)
    size = out.stat().st_size
    log(f"wrote {out} ({n} frames, {n / 30:.1f} s, {size / 1e6:.1f} MB)")
    (out.parent / (out.stem + ".json")).write_text(json.dumps({"scenes": list(SCENES), "frames": n, "fps": 30, "bytes": size, "seed": args.seed}, indent=1))
    shutil.rmtree(work, ignore_errors=True)
    return 0 if size <= 25e6 else 1


if __name__ == "__main__":
    sys.exit(main())
