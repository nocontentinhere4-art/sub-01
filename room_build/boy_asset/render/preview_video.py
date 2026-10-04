"""The owner's preview video of the character, old vs new (coordinator's ask on #117):
    python room_build/boy_asset/render/preview_video.py --old room_build/boy_asset/work/boy_old.glb \
        --out docs/design/character/preview/boy_old_vs_new.mp4
Rendered IN /room (tests/visual's harness: fake server, headless Chromium in software GL, the page's own loop frozen and
stepped by hand with __qa.step(1/30)), 30 fps, H.264 (/usr/bin/ffmpeg), ~40 s:
    0-10 s   a slow 360 degree turn of his head, the OLD asset (standing just inside the door at 14:00, the camera
             fixed in front of him at head height; he turns on the spot, so the room stays behind him)
   10-20 s   the same turn, the NEW asset
   20-30 s   at the desk (14:00), old (left) vs new (right), the same camera on both
   30-40 s   walking from the door to the desk (08:00), old vs new, the page's own follow camera
The old asset is served in place of web/room/boy.glb by a Playwright route; nothing on disk changes. Each frame is the
WebGL canvas itself (toDataURL right after the render), labelled with PIL; the frames go to a scratch directory and are
deleted after the encode."""
import argparse, base64, io, math, os, shutil, sys, tempfile, time, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from tests.visual.harness import Harness, wait_js, CHROMIUM, GLB_FILES   # noqa: E402
from tests.visual.fake_server import Server                              # noqa: E402

FPS = 30; W, H = 1280, 800
FONT = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf") if os.path.exists(f)), None)

class VideoHarness(Harness):
    def __init__(self, out, old_glb):
        super().__init__(out, full=False, log=print)
        self.old_glb = Path(old_glb).read_bytes(); self.serve_old = False
    def open(self, size):
        """one page per asset: the old asset is routed in for web/room/boy.glb"""
        key = (size, self.serve_old)
        if key in self.pages: return self.pages[key]
        ctx = self.browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg = ctx.new_page()
        st = {"errors": [], "failed": [], "glb": 0, "console": []}
        pg.on("pageerror", lambda e: st["errors"].append(str(e)))
        if self.serve_old:
            pg.route("**/room/boy.glb", lambda route: route.fulfill(status=200, content_type="model/gltf-binary", body=self.old_glb))
        pg.on("response", lambda r: st.__setitem__("glb", st["glb"] + 1) if r.url.endswith(".glb") and r.ok else None)
        if self.cdn: self.cdn.install(pg)
        pg.goto(self.base + "/room.html?debug&hour=14", wait_until="load")
        wait_js(pg, "() => !!(window.boy && window.room && !document.getElementById('boot') && Object.keys(window.actions).length >= 9)", timeout=180000)
        t0 = time.time()
        while st["glb"] < GLB_FILES and time.time() - t0 < 60: pg.wait_for_timeout(200)
        wait_js(pg, "() => !window.motion || !!window.motion.ready", timeout=60000)
        pg.evaluate("window.FREEZE = true")
        pg.add_script_tag(content=(ROOT / "tests" / "visual" / "page_checks.js").read_text())
        pg.wait_for_timeout(300)
        pg.evaluate("__qa.hideMarkers(); __qa.hud(false)")
        self.pages[key] = (ctx, pg, st); print("  page", "old" if self.serve_old else "new", "ready", f"{time.time() - t0:.1f}s", flush=True)
        return self.pages[key]
    def page(self, old):
        self.serve_old = old; return self.open("1280")[1]

def label(img, text):
    d = ImageDraw.Draw(img); f = ImageFont.truetype(FONT, 30) if FONT else ImageFont.load_default()
    x, y = 24, img.height - 56; d.rectangle([x - 12, y - 8, x + 12 + d.textlength(text, font=f), y + 42], fill=(0, 0, 0)); d.text((x, y), text, fill=(255, 255, 255), font=f)
    return img

def grab(pg, js_before=""):
    """step + camera + render + the canvas as an image, in ONE page task (the drawing buffer is read before any composite)"""
    data = pg.evaluate("(() => { %s; __qa.render(); return renderer.domElement.toDataURL('image/jpeg', 0.93); })()" % js_before)
    return Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))).convert("RGB")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--old", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=10.0, help="per segment"); ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(); out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    N = int(round(a.seconds * FPS))
    tmp = Path(tempfile.mkdtemp(prefix="boy_preview_")); seq = tmp / "seq"; seq.mkdir(); k = [0]
    def emit(img): img.save(seq / f"{k[0]:05d}.jpg", quality=93); k[0] += 1
    from playwright.sync_api import sync_playwright
    hv = VideoHarness(tmp / "harness", a.old)
    with Server() as server, sync_playwright() as p:
        hv.server = server; hv.base = server.base
        hv.browser = p.chromium.launch(executable_path=CHROMIUM if Path(CHROMIUM).exists() else None, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        try:
            # ---- 1 + 2: the turn, old then new: standing just inside the door (14:00); the camera 1 m in front of his head,
            # fixed; he turns on the spot (boy.rotation.y set after each step, before the render)
            for old in (True, False):
                pg = hv.page(old); hv.goto_scene(pg, "door", 14)
                head, yaw0 = pg.evaluate("(() => { const b = boy.getObjectByName('Head'); const v = new THREE.Vector3(); b.getWorldPosition(v); return [[v.x, v.y + 0.04, v.z], boy.rotation.y]; })()")
                cc = pg.evaluate("__qa.characterCam()")                              # a clear medium shot from his front-right: its direction, 1 m from the head
                d = [cc["pos"][k] - head[k] for k in range(3)]; d[1] = 0.0; n = math.hypot(d[0], d[2]) or 1.0
                cam = [head[0] + d[0] / n * 1.0, head[1] + 0.03, head[2] + d[2] / n * 1.0]
                yaw_face = math.atan2(d[0], d[2])                                        # facing the camera first (facing = (sin yaw, 0, cos yaw))
                for i in range(N):
                    yaw = yaw_face + 2 * math.pi * i / N
                    img = grab(pg, f"__qa.step(1/{FPS}, 1); boy.rotation.y = {yaw}; boy.updateMatrixWorld(true); __qa.lookFrom({cam}, {head})")
                    emit(label(img, "OLD  (the shipped boy.glb)" if old else "NEW  (#117)"))
                pg.evaluate(f"boy.rotation.y = {yaw0}")
                print("turn", "old" if old else "new", "done", f"{time.time() - hv.t0:.0f}s", flush=True)
            # ---- 3 + 4: the desk and the walk, old (left) vs new (right): both pages stepped frame by frame, centre crops
            for scene, hour, cam in (("desk", 14, "character"), ("walking", 8, "follow")):
                pgs = {}
                for old in (True, False):
                    pg = hv.page(old); hv.goto_scene(pg, scene, hour); pgs[old] = pg
                if cam == "character":                                               # the same camera on both pages (the raycast picks differently per page)
                    c = pgs[False].evaluate("__qa.characterCam()")
                    for pg in pgs.values(): pg.evaluate(f"__qa.lookFrom({c['pos']}, {c['target']})")
                for i in range(N):
                    halves = []
                    for old in (True, False):
                        img = grab(pgs[old], f"__qa.step(1/{FPS}, 1)" + ("; __qa.followCam()" if cam == "follow" else ""))
                        halves.append(label(img.crop((W // 4, 0, 3 * W // 4, H)), "OLD" if old else "NEW"))
                    fr = Image.new("RGB", (W, H)); fr.paste(halves[0], (0, 0)); fr.paste(halves[1], (W // 2, 0))
                    ImageDraw.Draw(fr).rectangle([W // 2 - 1, 0, W // 2 + 1, H], fill=(20, 20, 20)); emit(fr)
                print(scene, "done", f"{time.time() - hv.t0:.0f}s", flush=True)
        finally:
            for ctx, pg, st in hv.pages.values(): ctx.close()
            hv.browser.close()
    cmd = ["/usr/bin/ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(FPS), "-i", str(seq / "%05d.jpg"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-crf", "23", "-preset", "slow", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    size = out.stat().st_size / 1e6; print("wrote %s: %.1f MB, %d frames, %.1f s" % (out, size, k[0], k[0] / FPS))
    if size > 25:
        subprocess.run([c if c != "23" else "28" for c in cmd], check=True); print("re-encoded at crf 28: %.1f MB" % (out.stat().st_size / 1e6))
    if not a.keep: shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
