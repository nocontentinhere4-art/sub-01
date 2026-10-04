"""Screenshots, frame timings and the black-cloth metric of the room page (#98 G6, rendering). Run by hand (no `test_`
prefix: pytest does not collect it); tests/visual/test_black_cloth.py runs the cloth metric in CI:

    python tests/room_render_shots.py --tag before --out docs/design/room-render
    python tests/room_render_shots.py --tag after  --out docs/design/room-render --post high
    python tests/room_render_shots.py --cloth --post high                 # the hoodie's brightness by day (face and medium shots at 08 and 14)

Starts `live_server.py --demo` (BROWSE=0) and opens `/?debug&nolive&hour=H` in headless Chromium at 1280 x 800 and at
390 x 844 (mobile), for the hours 8, 14, 19 and 23, with him placed in the same spot each time (desk in the morning,
the window sill in the afternoon, the desk with the lamp in the evening, the phone on the bed at night). After the
screenshots it measures, on the 1280 and the 390 page:
  - the frames per second of the page's own loop over --fps-s seconds, and the JS main-thread ms per frame;
  - the same under a mid-phone profile (390 px, devtools CPU throttle x4);
  - with room_post.js present (the "after" build): each quality tier in turn (post.setTier), and the post module's info.
Headless Chromium here draws WebGL in software (SwiftShader): the FPS numbers are those of a CPU rasteriser, not of a
phone GPU, and results.json says so. The JS ms per frame under throttle is the number that transfers to a phone.

The cloth metric (the owner keeps the original look: black cloth stays black or charcoal in daylight too): the lit frame
of a shot, and the same frame with his mesh drawn unlit in its own texture against a blue background (nothing else
drawn). A pixel whose texel is dark (luminance < 50 of 255: the hoodie, the hair, the trousers) is cloth; the metric is
the mean luminance of the lit frame over those pixels. The budget is CLOTH_MAX.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# scene per shot: hour -> (activity, sleep stage, screen); "23s" is 23:00 asleep with the lights off (G8's #15)
HOURS = {8: ("research", "AWAKE", "desk", "face"), 14: ("window", "AWAKE", None, "medium"), 19: ("research", "AWAKE", "desk", "face"),
         23: ("phone", "AWAKE", "phone", "over"), "23s": ("sleep", "NREM", None, "overview")}   # the 4th item: the camera shot pinned (after this branch); 23s keeps the overview for the night metric
CLOTH_SHOTS = ((8, "face"), (8, "medium"), (14, "face"), (14, "medium"))   # daylight on his black hoodie: at the desk in the morning, at the sill at 14
CLOTH_MAX = 70            # mean luminance (0-255) of the lit frame over his dark texels, at most (the coordinator's target)
CLOTH_TEXEL = 110         # a texel darker than this is cloth (boy.glb's texture: the hoodie ~77 as painted, the hair ~27, skin > 150; the page darkens the cloth once)
INJECT = """
(() => {
  window.__fps = (ms) => new Promise(res => { let n = 0; const t0 = performance.now();
    const f = () => { n++; if (performance.now() - t0 < ms) requestAnimationFrame(f); else res(n * 1000 / (performance.now() - t0)); };
    requestAnimationFrame(f); });
  // main-thread ms per frame of the page's own loop: time between a frame's start and the next rAF callback's start
  // cannot be read from outside a module script, so the page exposes __frameMs under ?debug (room.html, loop block)
})();
"""
# his mesh unlit in its own texture, everything else pure blue (the room still occludes him; translucent effects left out):
# which pixels of the frame are his, and how dark their texel is
MASK_JS = """() => {
  const his = [], others = [], hidden = []; boy.traverse(o => { if (o.isMesh && o.material) his.push(o); });
  scene.traverse(o => { if (o.isMesh && o.material && !his.includes(o)) {
    const m = [].concat(o.material)[0];
    if (m.transparent || m.blending !== THREE.NormalBlending || m.colorWrite === false || m.isShaderMaterial) { if (o.visible) { o.visible = false; hidden.push(o); } }
    else others.push([o, o.material]); } });
  const mat = new THREE.MeshBasicMaterial({map: his[0].material.map, toneMapped: false}), blue = new THREE.MeshBasicMaterial({color: 0x0000ff, toneMapped: false});
  const saved = his.map(o => o.material); his.forEach(o => { o.material = mat; }); others.forEach(([o]) => { o.material = blue; });
  const bg = scene.background, cc = new THREE.Color(); renderer.getClearColor(cc); const ca = renderer.getClearAlpha();
  scene.background = null; renderer.setRenderTarget(null); renderer.setClearColor(0x0000ff, 1); renderer.clear(); renderer.render(scene, camera);
  his.forEach((o, i) => { o.material = saved[i]; }); others.forEach(([o, m]) => { o.material = m; }); hidden.forEach(o => { o.visible = true; });
  scene.background = bg; renderer.setClearColor(cc, ca); mat.dispose(); blue.dispose();
  const r = renderer.domElement.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }"""
HUD_OFF = "#top,#side,#corner,#dock,#vignette,#away{display:none!important}"


CDN_HOSTS = ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com")


def cdn_router(cache_dir):
    """Serve the CDN files from a local cache (fetched once with urllib, which honours the sandbox's proxy and CA bundle):
    headless Chromium behind a TLS-inspecting proxy fails sporadically on them (ERR_TOO_MANY_RETRIES), and a cached CDN
    makes the runs repeatable and faster."""
    import hashlib
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    def handle(route):
        url = route.request.url
        key = hashlib.sha1(url.encode()).hexdigest()
        f = cache / key
        meta = cache / (key + ".type")
        if not f.exists():
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    f.write_bytes(r.read())
                    meta.write_text(r.headers.get("Content-Type", "application/octet-stream"))
            except Exception as e:  # noqa: BLE001
                route.abort()
                print("cdn fetch failed", url, e, flush=True)
                return
        route.fulfill(path=str(f), content_type=meta.read_text() if meta.exists() else "application/javascript")
    return handle


def wait_ready(base, proc, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError("server exited")
        try:
            urllib.request.urlopen(base + "/api/config", timeout=2).read()
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("server not ready")


class Run:
    """The demo server and a headless Chromium (software WebGL), with the page opened at an hour and him placed."""

    def __init__(self, port=8797, chromium=None, cdn_cache=None, post=None):
        self.port, self.post = port, post
        self.chromium = chromium or os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium")
        self.cdn_cache = cdn_cache or str(Path(tempfile.gettempdir()) / "sub01-cdn-cache")

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix="roomshots-")
        env = dict(os.environ, BROWSE="0", SUB01_SPIKING_LIVE="0", SUB01_WS_STATS_S="3600",
                   OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")   # as in the Dockerfile: a spinning BLAS starves the browser
        self.log = open(Path(self.tmp) / "server.log", "w")
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "live_server.py"), "--demo", "--port", str(self.port),
                                      "--host", "127.0.0.1", "--data-dir", self.tmp], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.port}"
        try:
            wait_ready(self.base, self.proc)
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(executable_path=self.chromium, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        for k in ("browser", "pw"):
            try:
                o = getattr(self, k, None)
                if o:
                    (o.close if k == "browser" else o.stop)()
            except Exception:
                pass
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except Exception:
            self.proc.kill()
        self.log.close()

    def page(self, w, h, hour, mobile):
        # ignore_https_errors: in a sandbox behind a TLS-inspecting proxy Chromium does not trust the proxy's CA for the CDNs
        ctx = self.browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=mobile, has_touch=mobile,
                                       ignore_https_errors=True)
        pg = ctx.new_page()
        if not os.environ.get("NO_INJECT"):
            pg.add_init_script(INJECT)
        for host in CDN_HOSTS:
            pg.route(f"https://{host}/**", cdn_router(self.cdn_cache))
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console.error: " + m.text) if m.type == "error" else None)
        pg.goto(f"{self.base}/?debug&nolive&hour={hour}" + (f"&post={self.post}" if self.post else ""), wait_until="load", timeout=120000)
        pg.wait_for_function("() => !!(window.room && window.boy && window.actions && window.actions.idle && window.actions.sleep)", timeout=240000, polling=1000)
        pg.wait_for_function("() => !window.post || window.post.active || Object.keys(window.post.info().failed).length > 0 || window.post.info().tier === 'low'", timeout=120000, polling=1000)
        pg.wait_for_timeout(1500)
        return ctx, pg, errors

    @staticmethod
    def settle(pg, hour, shot=None):
        act, stage, screen, shot0 = HOURS[hour]
        shot = shot or shot0
        h = int(str(hour).rstrip("s"))
        pg.evaluate(f"""() => {{ setHour({h}); setStage({json.dumps(stage)}); setScreen({json.dumps(screen)}); if (window.setShot) setShot({json.dumps(shot)});
          if (!{json.dumps(bool(os.environ.get("KEEP_MARKERS")))}) scene.traverse(o => {{ if (o.isMesh && o.geometry.type === "SphereGeometry" && o.material.color && o.material.color.getHex() === 0xff00ff) o.visible = false; }});   // ?debug's marker balls
          act({json.dumps(act)}); settle(); for (let i = 0; i < 40; i++) sim(0.05);
          if ({json.dumps(screen)} === "desk" && monitor) monitor.set(drawReading({{title: "Inokashira Park", host: "en.wikipedia.org", kind: "wiki",
            extract: "Inokashira Park is a park in Musashino and Mitaka, western Tokyo. It straddles the border between the two cities, and was opened in 1917. The park has a pond, a zoo, a shrine to Benzaiten, a boating area and many cherry trees."}}));
          settle(); updateCameraGoal();
          camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); controls.update(); sim(0.05); }}""")
        pg.wait_for_timeout(2500)
        pg.evaluate("window.FREEZE = true; post.render(0.1)")   # the frame the screenshot takes is drawn from the placed camera (software GL may not have drawn one yet)
        pg.evaluate("window.FREEZE = false")


def cloth_metric(pg, out, name):
    """The mean luminance of the lit frame over his dark texels (see the module docstring). Writes `name`_lit.png,
    `name`_mask.png (the cloth pixels tinted) next to the numbers it returns."""
    import numpy as np
    from PIL import Image
    pg.add_style_tag(content=HUD_OFF)
    pg.evaluate("window.FREEZE = true; post.render(0.1)")
    lit_p, mask_p = out / f"{name}_lit.png", out / f"{name}_mask.png"
    pg.screenshot(timeout=240000, path=str(lit_p), type="png")
    x, y, w, h = pg.evaluate(MASK_JS)
    pg.screenshot(timeout=240000, path=str(mask_p), type="png")
    pg.evaluate("post.render(0.1); window.FREEZE = false")
    lit = np.asarray(Image.open(lit_p).convert("RGB")).astype(np.float32)[y:y + h, x:x + w]
    msk = np.asarray(Image.open(mask_p).convert("RGB")).astype(np.int32)[y:y + h, x:x + w]
    him = ~((msk[..., 0] < 8) & (msk[..., 1] < 8) & (msk[..., 2] > 247))
    tex_lum = msk @ np.array([0.299, 0.587, 0.114])
    cloth = him & (tex_lum < CLOTH_TEXEL)
    lum = lit @ np.array([0.299, 0.587, 0.114])
    r = {"him_px": int(him.sum()), "cloth_px": int(cloth.sum()), "cloth_mean": round(float(lum[cloth].mean()), 1) if cloth.any() else None,
         "cloth_p90": round(float(np.percentile(lum[cloth], 90)), 1) if cloth.any() else None,
         "cloth_over_120": round(float((lum[cloth] > 120).mean()), 4) if cloth.any() else None,
         "skin_mean": round(float(lum[him & ~cloth].mean()), 1) if (him & ~cloth).any() else None}
    tint = np.asarray(Image.open(lit_p).convert("RGB")).copy()
    sub = tint[y:y + h, x:x + w]; sub[cloth] = (sub[cloth] * 0.4 + np.array([255, 0, 255]) * 0.6).astype(np.uint8); tint[y:y + h, x:x + w] = sub
    Image.fromarray(tint).save(mask_p)
    return r


def cloth_means(run, out, shots=CLOTH_SHOTS, width=1280, tag="cloth"):
    """The cloth metric of each (hour, shot) at `width` (desktop 1280 x 800, or the 390 phone): name -> numbers."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    res = {}
    for hour, shot in shots:
        mobile = width < 640
        ctx, pg, errors = run.page(width, 844 if mobile else 800, hour, mobile)
        run.settle(pg, hour, shot)
        name = f"{tag}_{width}_h{hour:02d}_{shot}"
        r = cloth_metric(pg, out, name)
        r["errors"] = errors[:5]
        r["post"] = pg.evaluate("window.post ? post.info().tier : null")
        res[name] = r
        print("cloth", name, json.dumps(r), flush=True)
        ctx.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--out", default="docs/design/room-render")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--chromium", default=os.environ.get("SUB01_CHROMIUM", "/opt/pw-browsers/chromium"))
    ap.add_argument("--hours", default="8,14,19,23,23s")
    ap.add_argument("--fps-s", type=float, default=6.0)
    ap.add_argument("--no-fps", action="store_true")
    ap.add_argument("--sizes", default="1280,390")
    ap.add_argument("--cdn-cache", default=str(Path(tempfile.gettempdir()) / "sub01-cdn-cache"))
    ap.add_argument("--post", default=None, help="pin the quality tier (?post=): headless software GL would detect 'low' and draw no post chain")
    ap.add_argument("--cloth", action="store_true", help="only the black-cloth metric (CLOTH_SHOTS at 1280) into --out/cloth")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    hours = [int(h) if h.isdigit() else h for h in args.hours.split(",")]
    sizes = [int(s) for s in args.sizes.split(",")]

    results = {"tag": args.tag, "software_webgl": True,
               "note": "headless Chromium with SwiftShader (software WebGL): FPS is a CPU rasteriser's, not a phone GPU's"}
    with Run(port=args.port, chromium=args.chromium, cdn_cache=args.cdn_cache, post=args.post) as run:
        if args.cloth:
            res = cloth_means(run, out / "cloth", width=sizes[0], tag=args.tag)
            (out / "cloth" / f"results_{args.tag}.json").write_text(json.dumps(res, indent=1))
            worst = max(r["cloth_mean"] or 0 for r in res.values())
            print(f"cloth: worst mean {worst} (budget {CLOTH_MAX})", "OK" if worst <= CLOTH_MAX else "OVER", flush=True)
            return
        for w in sizes:
            h, mobile, tag = (800 if w == 1280 else round(w * 0.625), False, str(w)) if w >= 640 else (844, True, str(w))
            for hour in hours:
                ctx, pg, errors = run.page(w, h, hour, mobile)
                run.settle(pg, hour)
                name = f"{args.tag}_{tag}_h{str(hour).zfill(2)}.jpg"
                pg.evaluate("window.FREEZE = true")            # ?debug: the loop stops; the screenshot takes the last frame (software GL is slow)
                pg.screenshot(timeout=240000, path=str(out / name), type="jpeg", quality=88)
                pg.evaluate("window.FREEZE = false")
                if os.environ.get("SHOTS_DEBUG"):
                    print("dbg", pg.evaluate("() => { const L = {}; scene.traverse(o => { if (o.isLight) L[o.type] = +o.intensity.toFixed(4); }); return {L, exp: renderer.toneMappingExposure, captured: scene.environment !== studioEnv, envI: scene.environmentIntensity, kind: CAM.kind, cam: camera.position.toArray(), tgt: controls.target.toArray()}; }"), flush=True)
                info = pg.evaluate("() => ({dpr: window.dpr, post: window.post ? window.post.info() : null, gl: renderer.capabilities.isWebGL2, shot: window.CAM ? window.CAM.kind : null, cam: camera.position.toArray().map(v => +v.toFixed(2))})")
                results[name] = {"errors": errors[:5], **info}
                print("shot", name, json.dumps(info)[:300], flush=True)
                ctx.close()

        if not args.no_fps:
            for w, h, mobile, tag, throttle in ((1280, 800, False, "1280", 1), (390, 844, True, "390", 1), (390, 844, True, "390x4", 4)):
                ctx, pg, errors = run.page(w, h, 19, mobile)
                run.settle(pg, 19)
                cdp = ctx.new_cdp_session(pg)
                cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
                tiers = pg.evaluate("() => window.post ? window.post.tiers() : [null]")
                fps = {}
                for tier in tiers:
                    if tier:
                        pg.evaluate(f"post.setTier({json.dumps(tier)}, true)")
                        pg.wait_for_timeout(1500)
                    f = pg.evaluate(f"__fps({int(args.fps_s * 1000)})")
                    js = pg.evaluate(f"window.__frameMs ? __frameMs({int(args.fps_s * 1000)}) : null")
                    fps[tier or "direct"] = {"fps": round(f, 1), "js": js, "dpr": pg.evaluate("window.dpr"),
                                             "post": pg.evaluate("window.post ? post.info() : null")}
                    print(f"fps {tag} tier={tier}: {f:.1f} js={js}", flush=True)
                results[f"fps_{tag}"] = {"cpu_throttle": throttle, "errors": errors[:5], **fps}
                ctx.close()
    (out / f"results_{args.tag}.json").write_text(json.dumps(results, indent=1))
    print("written", out / f"results_{args.tag}.json")


if __name__ == "__main__":
    main()
