"""Screenshots and frame timings of the room page (#98 G6, rendering). Run by hand (no `test_` prefix: pytest does not
collect it):

    python tests/room_render_shots.py --tag before --out docs/design/room-render
    python tests/room_render_shots.py --tag after  --out docs/design/room-render

Starts `live_server.py --demo` (BROWSE=0) and opens `/?debug&nolive&hour=H` in headless Chromium at 1280 x 800 and at
390 x 844 (mobile), for the hours 8, 14, 19 and 23, with him placed in the same spot each time (desk in the morning,
the window sill in the afternoon, the desk with the lamp in the evening, the phone on the bed at night). After the
screenshots it measures, on the 1280 and the 390 page:
  - the frames per second of the page's own loop over --fps-s seconds, and the JS main-thread ms per frame;
  - the same under a mid-phone profile (390 px, devtools CPU throttle x4);
  - with room_post.js present (the "after" build): each quality tier in turn (post.setTier), and the post module's info.
Headless Chromium here draws WebGL in software (SwiftShader): the FPS numbers are those of a CPU rasteriser, not of a
phone GPU, and results.json says so. The JS ms per frame under throttle is the number that transfers to a phone.
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
INJECT = """
(() => {
  window.__fps = (ms) => new Promise(res => { let n = 0; const t0 = performance.now();
    const f = () => { n++; if (performance.now() - t0 < ms) requestAnimationFrame(f); else res(n * 1000 / (performance.now() - t0)); };
    requestAnimationFrame(f); });
  // main-thread ms per frame of the page's own loop: time between a frame's start and the next rAF callback's start
  // cannot be read from outside a module script, so the page exposes __frameMs under ?debug (room.html, loop block)
})();
"""


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
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    hours = [int(h) if h.isdigit() else h for h in args.hours.split(",")]
    sizes = [int(s) for s in args.sizes.split(",")]

    tmp = tempfile.mkdtemp(prefix="roomshots-")
    env = dict(os.environ, BROWSE="0", SUB01_SPIKING_LIVE="0", SUB01_WS_STATS_S="3600",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")   # as in the Dockerfile: a spinning BLAS starves the browser
    log = open(Path(tmp) / "server.log", "w")
    proc = subprocess.Popen([sys.executable, str(ROOT / "live_server.py"), "--demo", "--port", str(args.port),
                             "--host", "127.0.0.1", "--data-dir", tmp], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{args.port}"
    results = {"tag": args.tag, "software_webgl": True,
               "note": "headless Chromium with SwiftShader (software WebGL): FPS is a CPU rasteriser's, not a phone GPU's"}
    try:
        wait_ready(base, proc)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=["--use-gl=angle", "--use-angle=swiftshader",
                                                                             "--enable-unsafe-swiftshader"])

            def page_for(w, h, hour, mobile):
                # ignore_https_errors: in a sandbox behind a TLS-inspecting proxy Chromium does not trust the proxy's CA for the CDNs
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=mobile, has_touch=mobile,
                                          ignore_https_errors=True)
                pg = ctx.new_page()
                if not os.environ.get("NO_INJECT"):
                    pg.add_init_script(INJECT)
                for h in CDN_HOSTS:
                    pg.route(f"https://{h}/**", cdn_router(args.cdn_cache))
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.on("console", lambda m: errors.append("console.error: " + m.text) if m.type == "error" else None)
                pg.goto(f"{base}/?debug&nolive&hour={hour}" + (f"&post={args.post}" if args.post else ""), wait_until="load")
                pg.wait_for_function("() => !!(window.room && window.boy && window.actions && window.actions.idle && window.actions.sleep)", timeout=240000, polling=1000)
                pg.wait_for_function("() => !window.post || window.post.active || Object.keys(window.post.info().failed).length > 0 || window.post.info().tier === 'low'", timeout=120000, polling=1000)
                pg.wait_for_timeout(1500)
                return ctx, pg, errors

            def settle(pg, hour):
                act, stage, screen, shot = HOURS[hour]
                h = int(str(hour).rstrip("s"))
                pg.evaluate(f"""() => {{ setHour({h}); setStage({json.dumps(stage)}); setScreen({json.dumps(screen)}); if (window.setShot) setShot({json.dumps(shot)});
                  if (!{json.dumps(bool(os.environ.get("KEEP_MARKERS")))}) scene.traverse(o => {{ if (o.isMesh && o.geometry.type === "SphereGeometry" && o.material.color && o.material.color.getHex() === 0xff00ff) o.visible = false; }});   // ?debug's marker balls
                  act({json.dumps(act)}); settle(); for (let i = 0; i < 40; i++) sim(0.05);
                  if ({json.dumps(screen)} === "desk" && monitor) monitor.set(drawReading({{title: "Inokashira Park", host: "en.wikipedia.org", kind: "wiki",
                    extract: "Inokashira Park is a park in Musashino and Mitaka, western Tokyo. It straddles the border between the two cities, and was opened in 1917. The park has a pond, a zoo, a shrine to Benzaiten, a boating area and many cherry trees."}}));
                  settle(); updateCameraGoal();
                  camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); controls.update(); }}""")
                pg.wait_for_timeout(2500)

            for w in sizes:
                h, mobile, tag = (800 if w == 1280 else round(w * 0.625), False, str(w)) if w >= 640 else (844, True, str(w))
                for hour in hours:
                    ctx, pg, errors = page_for(w, h, hour, mobile)
                    settle(pg, hour)
                    name = f"{args.tag}_{tag}_h{str(hour).zfill(2)}.jpg"
                    pg.evaluate("window.FREEZE = true")            # ?debug: the loop stops; the screenshot takes the last frame (software GL is slow)
                    pg.screenshot(timeout=240000, path=str(out / name), type="jpeg", quality=88)
                    pg.evaluate("window.FREEZE = false")
                    if os.environ.get("SHOTS_DEBUG"):
                        print("dbg", pg.evaluate("() => { const L = {}; scene.traverse(o => { if (o.isLight) L[o.type] = +o.intensity.toFixed(4); }); return {L, exp: renderer.toneMappingExposure, captured: scene.environment !== studioEnv, envI: scene.environmentIntensity, hour: typeof hour, stage: null, kind: CAM.kind, cam: camera.position.toArray(), tgt: controls.target.toArray()}; }"), flush=True)
                        print("dbg_env", pg.evaluate("""() => { const f16 = h => { const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, m = h & 0x3ff; return e === 0 ? s * m * 2 ** -24 : e === 31 ? (m ? NaN : s * Infinity) : s * (1 + m / 1024) * 2 ** (e - 15); };
                          const out = {captures: roomEnv.captures, key: roomEnv.key, envIsCapture: scene.environment === roomEnv.texture, envI: scene.environmentIntensity};
                          const rt = roomEnv._env; if (rt) { const w = rt.width, h = rt.height, buf = new Uint16Array(w * h * 4); renderer.readRenderTargetPixels(rt, 0, 0, w, h, buf);
                            let nan = 0, inf = 0, max = 0, sum = 0, n = 0; for (let i = 0; i < buf.length; i++) { if ((i & 3) === 3) continue; const v = f16(buf[i]); if (Number.isNaN(v)) nan++; else if (!Number.isFinite(v)) inf++; else { max = Math.max(max, v); sum += v; n++; } }
                            out.pmrem = {w, h, nan, inf, max, mean: sum / n}; }
                          const cube = roomEnv.rt; out.faces = []; for (let f = 0; f < 6; f++) { const w = cube.width, buf = new Uint16Array(w * w * 4); renderer.readRenderTargetPixels(cube, 0, 0, w, w, buf, f);
                            let nan = 0, max = 0, sum = 0, n = 0; for (let i = 0; i < buf.length; i++) { if ((i & 3) === 3) continue; const v = f16(buf[i]); if (Number.isNaN(v)) nan++; else { max = Math.max(max, v); sum += v; n++; } } out.faces.push({nan, max: +max.toFixed(4), mean: +(sum / n).toFixed(5)}); }
                          return out; }"""), flush=True)
                        for pre in ("setEnv(studioEnv); scene.environmentIntensity = 0.001; roomEnv.key = null; sim(0.05);", "roomEnv.key = null; sim(0.05);", "scene.traverse(o => { if (o.isRectAreaLight) o.intensity = 0; }); setEnv(studioEnv); roomEnv.key = null; roomEnv.update('x', [boy, phone]); setEnv(roomEnv.texture);"):
                            print("dbg_env2", pre[:40], pg.evaluate("""(pre) => { eval(pre); const f16 = h => { const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, m = h & 0x3ff; return e === 0 ? s * m * 2 ** -24 : e === 31 ? (m ? NaN : s * Infinity) : s * (1 + m / 1024) * 2 ** (e - 15); };
                              const cube = roomEnv.rt, faces = []; for (let f = 0; f < 6; f++) { const w = cube.width, buf = new Uint16Array(w * w * 4); renderer.readRenderTargetPixels(cube, 0, 0, w, w, buf, f);
                                let nan = 0; for (let i = 0; i < buf.length; i++) { if ((i & 3) === 3) continue; if (Number.isNaN(f16(buf[i]))) nan++; } faces.push(nan); } return {captures: roomEnv.captures, faces}; }""", pre), flush=True)
                        for tag2, js in (("low", "post.setTier('low', true)"), ("medium", "post.setTier('medium', true)"), ("noenv", "scene.environmentIntensity = 0; scene.traverse(o => { if (o.isMesh && o.material && o.material.envMapIntensity !== undefined) o.material.envMapIntensity = 0; })"),
                                         ("nolights", "scene.traverse(o => { if (o.isLight) o.intensity = 0; })"), ("hemi1", "scene.traverse(o => { if (o.isHemisphereLight) o.intensity = 1; })")):
                            pg.evaluate("window.FREEZE = true; " + js + "; controls.update(); post.render(0.1)"); pg.screenshot(timeout=240000, path=str(out / (f"dbg_{tag2}_" + name)), type="jpeg", quality=88)
                            print("dbg2", tag2, pg.evaluate("() => { const L = {}; scene.traverse(o => { if (o.isLight) L[o.type] = +o.intensity.toFixed(4); }); return {L, chain: post.info().chain, rt: post.composer && [post.composer.renderTarget1.width, post.composer.renderTarget1.samples, post.composer.renderTarget1.texture.type]}; }"), flush=True)
                        pg.evaluate("window.FREEZE = false")
                    info = pg.evaluate("() => ({dpr: window.dpr, post: window.post ? window.post.info() : null, gl: renderer.capabilities.isWebGL2, shot: window.CAM ? window.CAM.kind : null, cam: camera.position.toArray().map(v => +v.toFixed(2))})")
                    results[name] = {"errors": errors[:5], **info}
                    print("shot", name, json.dumps(info)[:300], flush=True)
                    ctx.close()

            if not args.no_fps:
                for w, h, mobile, tag, throttle in ((1280, 800, False, "1280", 1), (390, 844, True, "390", 1), (390, 844, True, "390x4", 4)):
                    ctx, pg, errors = page_for(w, h, 19, mobile)
                    settle(pg, 19)
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
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    (out / f"results_{args.tag}.json").write_text(json.dumps(results, indent=1))
    print("written", out / f"results_{args.tag}.json")


if __name__ == "__main__":
    main()
