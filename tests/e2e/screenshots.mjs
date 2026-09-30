#!/usr/bin/env node
// SUB-01 "the construct" - headless end-to-end screenshot check.
//
// For every scenario: start `live_server.py --demo` on a free port with a temporary data dir, open the page in
// headless Chromium (software WebGL), wait for window.__sub01.ready, drive the scenario, capture a screenshot and run
// checks (no console errors, canvas is not blank/uniform, honesty line visible, scenario-specific assertions).
//
//   node tests/e2e/screenshots.mjs [--only=home,walk,...] [--out=docs/real-world/screenshots] [--gif]
//                                  [--allow-stubs] [--python=/path/to/python] [--format=png|jpg] [--timeout=150]
//                                  [--selftest]
// --selftest: runs the checks against a page whose 3D canvas is hidden (over a black page) and expects both the
// "canvas is not blank / uniform" and the "canvas is not almost black" check to FAIL: the pixel checks cannot be satisfied
// by the DOM overlays alone. Writes nothing.
// Env: E2E_CHROME (Chromium path; default: Playwright's own browser), E2E_PYTHON, E2E_TOOLS (extra dir with node_modules).
//
// Scenarios: home, walk, chat, dump, night, rem, orbit, mobile.
// Output: <out>/<scenario>.png|jpg (+ chat-falling), <out>/report.json, and with --gif <out>/walk.gif (<= 60 frames of the
// walk, captured by the extra scenario "walk-gif", played back at the real speed). A FAILING scenario writes <name>.FAILED.<ext>
// instead, so a bad run never replaces good screenshots.
// Assertions are state-based: life ticks, window.__sub01.fx, and the camera position (CAMERA_HOOK reads the viewMatrix uniform uploads
// of the main canvas); the chat rain is also measured in the pixels of the 3D canvas alone (all DOM overlays hidden for that capture).
// fps / drawCalls / triangles in report.json are measured with SOFTWARE rendering (SwiftShader): they are only
// useful to compare scenarios with each other, NOT as real device performance.
// A scenario also fails while a construct module it needs (city/fx/travel) is still a STUB file, unless --allow-stubs.
// Exit code 0 when every selected scenario passes, 1 otherwise. A failing scenario is reported, never faked.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync, openSync, closeSync } from "node:fs";
import { tmpdir } from "node:os";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../..");
const require = createRequire(import.meta.url);

// ---------------------------------------------------------------- dependencies (playwright, gifenc, pngjs)
function tryRequire(name, extra = []) {
  for (const base of [HERE, ...extra]) {
    try { return createRequire(path.join(base, "noop.js"))(name); } catch { /* next */ }
  }
  try { return require(name); } catch { return null; }
}
const playwright = tryRequire("playwright", [process.env.E2E_TOOLS, ROOT].filter(Boolean));
const pngjs = tryRequire("pngjs");
const gifenc = tryRequire("gifenc");

// ---------------------------------------------------------------- args
const argv = process.argv.slice(2);
const opt = (k, d) => { const a = argv.find(x => x.startsWith(`--${k}=`)); return a ? a.slice(k.length + 3) : d; };
const flag = k => argv.includes(`--${k}`);
const OUT = path.resolve(ROOT, opt("out", "docs/real-world/screenshots"));
const PY = opt("python", process.env.E2E_PYTHON || (existsSync(path.join(ROOT, ".venv/bin/python")) ? path.join(ROOT, ".venv/bin/python") : "python3"));
const CHROME_OPT = opt("chrome", process.env.E2E_CHROME || "");
const CHROME = CHROME_OPT && existsSync(CHROME_OPT) ? CHROME_OPT : undefined;   // undefined: Playwright's bundled Chromium
const FORMAT = opt("format", "png") === "jpg" ? "jpeg" : "png";
const EXT = FORMAT === "jpeg" ? "jpg" : "png";
const SCENARIO_TIMEOUT_MS = +opt("timeout", 150) * 1000;
const WANT_GIF = flag("gif");
const SELFTEST = flag("selftest");
const HONESTY = "Simulated brain activity built from one real person's public MRI. Messages are stimuli, not conversation. It is not a mind and it is not the person.";
const log = (...a) => console.log(...a);

// ---------------------------------------------------------------- server management (always cleaned up)
const servers = new Set();
const tmpDirs = new Set();
function killAll() {
  for (const s of servers) { try { s.kill("SIGKILL"); } catch { /* gone */ } }
  servers.clear();
  for (const d of tmpDirs) { try { rmSync(d, { recursive: true, force: true }); } catch { /* ignore */ } }
  tmpDirs.clear();
}
process.on("exit", killAll);
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => { killAll(); process.exit(130); });
process.on("uncaughtException", e => { console.error("uncaught:", e); killAll(); process.exit(1); });

function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer();
    s.on("error", rej);
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); });
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function startServer(args, abort = { aborted: false }) {
  const port = await freePort();
  const dir = mkdtempSync(path.join(tmpdir(), "sub01-e2e-"));
  tmpDirs.add(dir);
  const logPath = path.join(dir, "server.log");
  const fd = openSync(logPath, "w");
  const env = { ...process.env, PYTHONUNBUFFERED: "1", PYTHONDONTWRITEBYTECODE: "1" };
  delete env.SITE_PASSWORD;             // the password gate must not block the headless check (never read or printed)
  delete env.REPLICATE_API_TOKEN;       // no outbound model calls from a test run
  const child = spawn(PY, ["live_server.py", "--demo", "--port", String(port), "--data-dir", path.join(dir, "data"), "--no-llm", ...args],
    { cwd: ROOT, env, stdio: ["ignore", fd, fd] });
  closeSync(fd);
  servers.add(child);
  let exited = null;
  child.on("exit", c => { exited = c; });
  const t0 = Date.now();
  for (;;) {
    if (abort.aborted) { child.kill("SIGKILL"); servers.delete(child); throw new Aborted(); }
    if (exited !== null) throw new Error(`server exited early (code ${exited}): ${tail(logPath)}`);
    try { const r = await fetch(`http://127.0.0.1:${port}/`); if (r.status < 500) break; } catch { /* not up yet */ }
    if (Date.now() - t0 > 40000) { child.kill("SIGKILL"); throw new Error("server did not start in 40 s: " + tail(logPath)); }
    await sleep(200);
  }
  return { port, child, logPath, stop() { try { child.kill("SIGKILL"); } catch { /* gone */ } servers.delete(child); } };
}
function tail(p) { try { return readFileSync(p, "utf8").split("\n").slice(-8).join(" | "); } catch { return ""; } }

// ---------------------------------------------------------------- pixel checks
function decode(buf) { return pngjs.PNG.sync.read(buf); }
/** Luminance stats over a grid of samples inside [x0,y0,x1,y1]: std-dev, distinct quantised colours, bright share. */
function pixelStats(png, rect) {
  const { width: W, height: H, data } = png;
  const [x0, y0, x1, y1] = rect.map(Math.round);
  const step = 6, cols = new Set();
  let n = 0, sum = 0, sum2 = 0, bright = 0, sumR = 0, sumG = 0, sumB = 0;
  for (let y = Math.max(0, y0); y < Math.min(H, y1); y += step) {
    for (let x = Math.max(0, x0); x < Math.min(W, x1); x += step) {
      const i = (y * W + x) * 4, r = data[i], g = data[i + 1], b = data[i + 2];
      const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      n++; sum += l; sum2 += l * l; sumR += r; sumG += g; sumB += b;
      if (l > 60) bright++;
      cols.add(((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4));
    }
  }
  const mean = sum / Math.max(1, n);
  return { samples: n, mean: +mean.toFixed(1), std: +Math.sqrt(Math.max(0, sum2 / Math.max(1, n) - mean * mean)).toFixed(2),
    colours: cols.size, brightShare: +(bright / Math.max(1, n)).toFixed(4),
    rgb: [sumR, sumG, sumB].map(v => Math.round(v / Math.max(1, n))) };
}

/** Share of sampled pixels (inside rect) whose luminance differs by more than `thr` between two PNG buffers. */
function diffShare(bufA, bufB, rect, thr = 24) {
  const a = decode(bufA), b = decode(bufB);
  if (a.width !== b.width || a.height !== b.height) return 1;
  const [x0, y0, x1, y1] = rect.map(Math.round);
  let n = 0, d = 0;
  for (let y = Math.max(0, y0); y < Math.min(a.height, y1); y += 4) {
    for (let x = Math.max(0, x0); x < Math.min(a.width, x1); x += 4) {
      const i = (y * a.width + x) * 4;
      const la = 0.2126 * a.data[i] + 0.7152 * a.data[i + 1] + 0.0722 * a.data[i + 2];
      const lb = 0.2126 * b.data[i] + 0.7152 * b.data[i + 1] + 0.0722 * b.data[i + 2];
      n++; if (Math.abs(la - lb) > thr) d++;
    }
  }
  return +(d / Math.max(1, n)).toFixed(4);
}

/** Bright warm (amber / orange) glyph-coloured pixels of a canvas PNG, as a 1-byte-per-pixel mask. */
function warmMask(png) {
  const { width: W, height: H, data } = png, m = new Uint8Array(W * H);
  for (let i = 0, k = 0; k < W * H; i += 4, k++) { const r = data[i], g = data[i + 1], b = data[i + 2]; if (r > 190 && g > 110 && g < r && b < g * 0.8 && b < 150) m[k] = 1; }
  return m;
}
/** Mask of pixels whose luminance differs by more than `thr` between two PNGs. */
function changedMask(a, b, thr = 28) {
  const { width: W, height: H } = a, m = new Uint8Array(W * H);
  for (let i = 0, k = 0; k < W * H; i += 4, k++) {
    const la = 0.2126 * a.data[i] + 0.7152 * a.data[i + 1] + 0.0722 * a.data[i + 2], lb = 0.2126 * b.data[i] + 0.7152 * b.data[i + 1] + 0.0722 * b.data[i + 2];
    if (Math.abs(la - lb) > thr) m[k] = 1;
  }
  return m;
}
/** Dilates a W x H mask by `rad` pixels (separable box). */
function dilate(m, W, H, rad) {
  const tmp = new Uint8Array(W * H), out = new Uint8Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (m[y * W + x]) for (let d = Math.max(0, x - rad); d <= Math.min(W - 1, x + rad); d++) tmp[y * W + d] = 1;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (tmp[y * W + x]) for (let d = Math.max(0, y - rad); d <= Math.min(H - 1, y + rad); d++) out[d * W + x] = 1;
  return out;
}
/** Two idle frames A and B of a still camera (?nofollow=1) define where the scene flickers by itself: "idle zone" = every pixel that
 *  was warm-and-glyph-coloured in A or B, or that changed between them, dilated by 5 px. The rain words are the glyph-coloured
 *  pixels of a later frame that fall OUTSIDE that zone. The same count on a third idle frame is the noise floor. */
function idleZone(bufA, bufB) {
  const a = decode(bufA), b = decode(bufB), { width: W, height: H } = a;
  const m = warmMask(a), mb = warmMask(b), ch = changedMask(a, b);
  for (let k = 0; k < m.length; k++) m[k] = m[k] | mb[k] | ch[k];
  return { zone: dilate(m, W, H, 5), W, H };
}
function glyphPixelsOutside(buf, z) {
  const p = decode(buf);
  if (p.width !== z.W || p.height !== z.H) return 1e9;
  const m = warmMask(p);
  let n = 0;
  for (let k = 0; k < m.length; k++) if (m[k] && !z.zone[k]) n++;
  return n;
}

/** In-page: tag the main 3D canvas (the largest canvas; the mini brain PiP is a second, smaller one) and return its rect. */
const MAIN_CANVAS_JS = () => {
  let best = null, area = 0;
  for (const cv of document.querySelectorAll("canvas")) { const r = cv.getBoundingClientRect(), a = r.width * r.height; if (a > area) { area = a; best = cv; } }
  document.querySelectorAll("[data-e2e-main]").forEach(e => e.removeAttribute("data-e2e-main"));
  if (!best) return null;
  best.setAttribute("data-e2e-main", "1");
  const r = best.getBoundingClientRect();
  return [Math.max(0, r.left), Math.max(0, r.top), Math.min(innerWidth, r.right), Math.min(innerHeight, r.bottom)];
};
const canvasRect = async page => (await page.evaluate(MAIN_CANVAS_JS)) || [0, 0, 100, 100];

/** Screenshot of the main 3D canvas ALONE: every other DOM element (HUD, labels, mini brain, chat...) is hidden for the shot,
 *  so a broken / black scene cannot be hidden behind overlay pixels. Returns {png, stats} or null when there is no canvas. */
async function canvasOnly(page, hide = false) {           // hide: false | true (self-test) | "black" (self-test, black page)
  const rect = await page.evaluate(MAIN_CANVAS_JS);
  if (!rect || rect[2] - rect[0] < 4 || rect[3] - rect[1] < 4) return null;
  await page.evaluate(h => {
    const st = document.createElement("style"); st.id = "e2e-clean";
    st.textContent = "body *{visibility:hidden !important}[data-e2e-main]{visibility:visible !important}" +
      (h === "black" ? "html,body{background:#000 !important;background-image:none !important}html::before,html::after,body::before,body::after{display:none !important}" : "");           // self-test: a hidden canvas over a black page
    document.head.appendChild(st);
    if (h) document.querySelector("[data-e2e-main]").style.setProperty("visibility", "hidden", "important");   // self-test
  }, hide);
  try {
    const png = await page.screenshot({ type: "png", clip: { x: rect[0], y: rect[1], width: rect[2] - rect[0], height: rect[3] - rect[1] } });
    const dec = decode(png);
    return { png, stats: pixelStats(dec, [0, 0, dec.width, dec.height]) };
  } finally {
    await page.evaluate(() => { document.getElementById("e2e-clean")?.remove(); const c = document.querySelector("[data-e2e-main]"); if (c) c.style.removeProperty("visibility"); }).catch(() => {});
  }
}

/** Init script (every page): records the main canvas' camera position from the three.js `viewMatrix` uniform uploads, so the e2e can
 *  assert on camera STATE (window.__e2eCamera() -> [x,y,z] or null) without any debug field in the page. The mini-brain PiP has its
 *  own (smaller) canvas; the camera of the largest canvas wins. A page that exposes window.__sub01.camera is read directly instead. */
const CAMERA_HOOK = () => {
  const cams = new Map(), tagged = new WeakSet();
  for (const C of [window.WebGL2RenderingContext, window.WebGLRenderingContext]) {
    if (!C) continue;
    const gul = C.prototype.getUniformLocation, um = C.prototype.uniformMatrix4fv;
    C.prototype.getUniformLocation = function (prog, name) { const loc = gul.call(this, prog, name); if (loc && name === "viewMatrix") tagged.add(loc); return loc; };
    C.prototype.uniformMatrix4fv = function (loc, transpose, v, ...rest) {
      if (loc && tagged.has(loc) && v && v.length >= 16 && !transpose) {
        const t0 = v[12], t1 = v[13], t2 = v[14];                           // camera position = -R^T t  (column-major view matrix)
        cams.set(this.canvas, [-(v[0] * t0 + v[1] * t1 + v[2] * t2), -(v[4] * t0 + v[5] * t1 + v[6] * t2), -(v[8] * t0 + v[9] * t1 + v[10] * t2)]);
      }
      return um.call(this, loc, transpose, v, ...rest);
    };
  }
  window.__e2eCamera = () => {
    const s = window.__sub01 || {}, d = s.camera || (s.travel && s.travel.position);
    if (d) return (Array.isArray(d) ? d.slice(0, 3) : [d.x, d.y, d.z]).map(Number);
    let best = null, area = 0;
    for (const [cv, p] of cams) { const a = cv.width * cv.height; if (a > area) { area = a; best = p; } }
    return best;
  };
};
const cameraPos = page => page.evaluate(() => (window.__e2eCamera ? window.__e2eCamera() : null)).catch(() => null);
const dist3 = (a, b) => (a && b ? Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) : null);

/** Construct modules still carrying the "STUB" header (their stream has not been merged into this checkout yet). */
function stubModules() {
  const out = [];
  for (const m of ["city", "fx", "travel"]) {
    try { if (/^\s*\/\/\s*STUB\b/.test(readFileSync(path.join(ROOT, "web/construct", m + ".js"), "utf8").slice(0, 200))) out.push(m); } catch { out.push(m + " (missing)"); }
  }
  return out;
}

// values shared between scenarios of one run (home runs first)
const REF = { idleDrift: null, homeMean: null };
const CAM_MIN_TRAVEL = 20, CAM_FACTOR = 5;       // walk "camera moved" thresholds, scene units (calibrated on the merged build)
const RAIN_MIN_PIXELS = 150, RAIN_FACTOR = 4;   // visible-rain thresholds (calibrated)
const IDLE_SPAN_MS = 12000;      // idle baseline span; the walk compares frames ~15-18 s apart
const HOME_PLACES = new Set(["bed", "window", "table", "desk", "door_in", "door_out", "street_home"]);       // life.py PLACES (apartment)
const REWARD_PLACES = new Set(["street_bakery", "bakery_door", "bakery_in", "counter"]);                      // life.py PLACES (bakery)
const jpgOpts = () => (FORMAT === "jpeg" ? { type: "jpeg", quality: 82 } : { type: "png" });

// ---------------------------------------------------------------- scenarios
// live_server.py only honours --start together with --time-scale != 1; 1.001 keeps the clock effectively real-time.
const at = (hhmm, ...rest) => ["--start", hhmm, "--time-scale", "1.001", ...rest];
const num = v => (typeof v === "number" && Number.isFinite(v) ? v : null);
/** fx stream state (window.__sub01.fx); null while fx is a stub. Fails the scenario unless --allow-stubs. */
function needFx(ck, fx, what) {
  if (fx) return true;
  ck(`fx state exposed (window.__sub01.fx) for: ${what}`, flag("allow-stubs"), flag("allow-stubs") ? "skipped: fx is a stub (--allow-stubs)" : "window.__sub01.fx is missing");
  return false;
}
// serverArgs: extra live_server.py flags. path: page path. run(c): drive the page, return details. check(details, ck, c): assertions.
const SCENARIOS = {
  home: {
    needs: ["city"],
    desc: "home district, default-network city around the window (daylight)",
    serverArgs: at("10:00", "--life-activity", "window"),
    async run(c) {
      await c.waitFor(() => c.life && c.life.place === "window" && !(c.life.progress > 0), 60000, "reach the window");
      await c.settle(1500);
      // idle baseline: how far the camera drifts by itself over IDLE_SPAN_MS while SUB-01 stays at the window (sway). The walk must
      // move the camera far more than this.
      const c0 = await cameraPos(c.page);
      await c.settle(IDLE_SPAN_MS);
      const c1 = await cameraPos(c.page);
      REF.idleDrift = dist3(c0, c1);
      return { place: c.life.place, clock: c.clock, idleSpanSeconds: IDLE_SPAN_MS / 1000, cameraCaptured: !!c0, idleCameraDrift: REF.idleDrift == null ? null : +REF.idleDrift.toFixed(3) };
    },
    check(r, ck) { ck("daytime clock (started 10:00)", /^10:/.test(r.clock || ""), r.clock); },
  },
  walk: {
    needs: ["city", "travel"],
    desc: "first-person walk along the real fibre road from home to the reward district",
    serverArgs: at("10:00", "--life-activity", "buy_bread"),
    retries: 3,                              // the walk starts with the server (~22 s long): retry if the page was too slow
    async run(c) {
      const t0 = Date.now();
      await c.waitFor(() => c.life && c.life.route && c.life.route.length > 1, 15000, "a walk to start", true);
      const r0 = c.life.route;
      if (!HOME_PLACES.has(r0[0]) || !REWARD_PLACES.has(r0[r0.length - 1]))
        throw Object.assign(new Error(`not the outbound walk home -> reward district (route ${r0.join(">")})`), { retry: true });
      if (c.life.progress > 0.35) throw Object.assign(new Error("page was ready too late (progress already " + c.life.progress + ")"), { retry: true });
      const viewAtStart = await c.page.evaluate(() => window.__sub01.view);
      const routeKey = r0.join(">");
      // state-based camera check: camera positions sampled along the walk (see CAMERA_HOOK), plus the progress from the life ticks
      const samples = [], cams = [];
      let best = null;
      while (c.life && c.life.route && c.life.route.join(">") === routeKey && c.life.progress < 0.96 && Date.now() - t0 < 60000) {
        c.checkAbort();
        const p = c.life.progress;
        samples.push(p);
        const cp = await cameraPos(c.page);
        if (cp) cams.push({ p, pos: cp, ts: Date.now() });
        // the saved frame: a full-page shot close to the middle of the walk (already encoded in the requested format)
        if (p >= 0.3 && p <= 0.7 && (!best || Math.abs(p - 0.5) < Math.abs(best.p - 0.5) - 0.02))
          best = { p, buf: await c.page.screenshot(jpgOpts()) };
        await sleep(250);
      }
      if (!best) throw Object.assign(new Error("never captured a frame with life.progress in 0.3..0.7 (saw up to " + (c.life?.progress ?? "n/a") + ")"), { retry: true });
      c.overrideShot = best.buf;
      const first = cams[0], last = cams[cams.length - 1];
      let path_ = 0;
      for (let i = 1; i < cams.length; i++) path_ += dist3(cams[i - 1].pos, cams[i].pos);
      const net = first && last ? dist3(first.pos, last.pos) : null;
      const round = v => (v == null ? null : +v.toFixed(2));
      return { walkProgress: best.p, route: routeKey, view: viewAtStart, progressStart: samples[0], progressEnd: samples[samples.length - 1],
        progressMonotone: samples.every((v, i) => i === 0 || v >= samples[i - 1] - 1e-6),
        routeHasStreet: r0.some(p => /street/.test(p)), cameraSamples: cams.length, cameraStart: first ? first.pos.map(round) : null,
        cameraEnd: last ? last.pos.map(round) : null, cameraNetTravel: round(net), cameraPathLength: round(path_),
        spanSeconds: first && last ? +((last.ts - first.ts) / 1000).toFixed(1) : null, idleCameraDrift: REF.idleDrift == null ? null : round(REF.idleDrift),
        idleSpanSeconds: IDLE_SPAN_MS / 1000 };
    },
    check(r, ck) {
      const r0 = r.route.split(">");
      ck("outbound walk: route starts at a home place", HOME_PLACES.has(r0[0]), r.route);
      ck("outbound walk: route ends at the reward district (bakery)", REWARD_PLACES.has(r0[r0.length - 1]), r.route);
      ck("page reports the first-person view (window.__sub01.view == 'first')", r.view === "first", r.view);
      ck("life.progress advances along the route", r.progressMonotone && r.progressEnd - r.progressStart > 0.25, `${r.progressStart} -> ${r.progressEnd}`);
      ck("camera position could be read (WebGL viewMatrix / window.__sub01.camera)", r.cameraSamples >= 10, `${r.cameraSamples} samples`);
      // the camera travels along the road: net displacement far above the camera's idle drift (home scenario, sway only). Without
      // the home baseline the absolute floor applies.
      const need = Math.max(CAM_MIN_TRAVEL, CAM_FACTOR * (r.idleCameraDrift ?? 0));
      ck("the camera moves along the road (net displacement start -> end of the walk)", r.cameraNetTravel != null && r.cameraNetTravel > need,
        `net=${r.cameraNetTravel} units, path=${r.cameraPathLength}, needed > ${need.toFixed(2)} = max(${CAM_MIN_TRAVEL}, ${CAM_FACTOR} x idle drift ${r.idleCameraDrift ?? "n/a (home did not run)"}); start ${JSON.stringify(r.cameraStart)} -> end ${JSON.stringify(r.cameraEnd)}, ${r.spanSeconds} s`);
    },
  },
  "walk-gif": {
    hidden: true, gifOnly: true,             // run by --gif right after `walk` (own server + fresh walk); writes walk.gif only
    needs: ["city", "travel"],
    desc: "the walk as a GIF: 3D canvas frames captured in-page (~3 fps under software rendering) over the whole walk, played back at real speed",
    serverArgs: at("10:00", "--life-activity", "buy_bread"),
    viewport: { width: 800, height: 500 },   // a full-size readback costs ~0.6 s per frame under software rendering, this one ~0.3 s
    retries: 3,
    async run(c) {
      const t0 = Date.now();
      await c.waitFor(() => c.life && c.life.route && c.life.route.length > 1, 15000, "a walk to start", true);
      const r0 = c.life.route;
      if (!HOME_PLACES.has(r0[0]) || !REWARD_PLACES.has(r0[r0.length - 1]))
        throw Object.assign(new Error(`not the outbound walk home -> reward district (route ${r0.join(">")})`), { retry: true });
      if (c.life.progress > 0.25) throw Object.assign(new Error("page was ready too late (progress already " + c.life.progress + ")"), { retry: true });
      const routeKey = r0.join(">");
      await canvasRect(c.page);                                                 // tags the main canvas
      await c.page.evaluate(() => {
        const src = document.querySelector("[data-e2e-main]"), W = 640, H = Math.round(W * src.height / src.width);
        const c2 = document.createElement("canvas"); c2.width = W; c2.height = H;
        const g = c2.getContext("2d"), cap = (window.__e2eCap = { frames: [], on: true });
        let last = 0;
        // registered after the app's own loop, so the WebGL drawing buffer still holds the frame that was just rendered
        const tick = t => {
          if (!cap.on) return;
          if (t - last >= 120) { last = t; g.drawImage(src, 0, 0, W, H); cap.frames.push({ ts: Date.now(), u: c2.toDataURL("image/png") }); }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      const samples = [];
      while (c.life && c.life.route && c.life.route.join(">") === routeKey && c.life.progress < 0.97 && Date.now() - t0 < 60000) {
        c.checkAbort(); samples.push(c.life.progress); await sleep(250);
      }
      const frames = await c.page.evaluate(() => { window.__e2eCap.on = false; return window.__e2eCap.frames; });
      c.gifFrames = frames.map(f => ({ buf: Buffer.from(f.u.split(",")[1], "base64"), ts: f.ts }));
      if (c.gifFrames.length < MIN_GIF_FRAMES && (c.life?.progress ?? 1) < 0.97) throw Object.assign(new Error("walk capture ended early"), { retry: true });
      return { route: routeKey, progressStart: samples[0], progressEnd: samples[samples.length - 1], gifFrames: c.gifFrames.length };
    },
    check(r, ck) { ck("captured the whole outbound walk (life.progress start < 0.25, end >= 0.9)", r.progressStart < 0.25 && r.progressEnd >= 0.9, `${r.progressStart} -> ${r.progressEnd}`); },
  },
  chat: {
    needs: ["city", "fx"],
    desc: "chat message falls as orange rain made of its words and lands on the districts it stimulates (orbit view, so the rain is in frame)",
    serverArgs: at("10:00", "--life-activity", "window"),
    path: "/?view=orbit&nofollow=1",        // fx drops the words from 260-440 units above the districts: invisible from street level
    async run(c) {
      await c.settle(1500);
      // idle reference (3D canvas only): warm glyph-coloured pixels in the upper canvas before the message (noise floor)
      const idleA = await canvasOnly(c.page);
      await c.settle(2500);
      const idleB = await canvasOnly(c.page);
      await c.settle(1500);
      const idleC = await canvasOnly(c.page);
      const zone = idleA && idleB ? idleZone(idleA.png, idleB.png) : null;
      const idleNoise = zone && idleC ? glyphPixelsOutside(idleC.png, zone) : null;
      const fx0 = await c.fx();
      await c.sendChat("fresh bread and a happy morning in the park");
      // fx time (not wall time): fx advances its own clock with dt clamped per frame, so slow software rendering stretches it
      let rainSeen = null, fxAtDrop = null, peakPending = 0, fxEnd = null;
      const waitFx = async (pred, ms) => {
        const t0 = Date.now();
        for (;;) {
          c.checkAbort();
          const f = await c.fx();
          if (f) { peakPending = Math.max(peakPending, f.pending || 0); if (pred(f)) return f; }
          if (Date.now() - t0 > ms) return null;
          await sleep(80);
        }
      };
      let falling = null, fallingNew = null, landed = null;
      if (fx0) {
        // the words are dropped once the queue is empty and the pool has fewer free slots than at rest
        rainSeen = await waitFx(f => f.queued === 0 && (f.free < fx0.free || f.pending > 0), 12000);
        fxAtDrop = rainSeen ? rainSeen.time : null;
        if (rainSeen) {
          // ~1 s of fx time into the fall: words are in the sky / falling
          await waitFx(f => f.time >= fxAtDrop + 1.0, 15000);
          c.extraShots["chat-falling"] = await c.page.screenshot(jpgOpts());
          falling = await canvasOnly(c.page);
          fallingNew = falling && zone ? glyphPixelsOutside(falling.png, zone) : null;
          // landing: a splash is pending no more (pending fell below its peak) or 3.4 fx seconds passed (words fall for 2.4-3.3 s)
          landed = await waitFx(f => f.pending < peakPending || f.time >= fxAtDrop + 3.4, 20000);
        }
      } else await c.settle(3000);
      c.overrideShot = await c.page.screenshot(jpgOpts());
      fxEnd = await c.fx();
      const flashed = await c.page.evaluate(() => window.__sub01 && window.__sub01.lastChatRegions);
      return { view: await c.page.evaluate(() => window.__sub01.view), chatEchoed: true, regionsFlashed: flashed ?? null, fxExposed: !!fx0, rainSeen: !!rainSeen,
        poolFreeAtRest: fx0?.free ?? null, poolFreeAtFalling: falling ? (await c.fx())?.free ?? null : null, poolFreeAtCapture: fxEnd?.free ?? null,
        fxTimeAtDrop: fxAtDrop, fxTimeAtCapture: fxEnd?.time ?? null, splashSeen: !!landed && landed.pending < peakPending, peakPending,
        idleGlyphNoise: idleNoise, fallingGlyphPixels: fallingNew };
    },
    check(r, ck, c) {
      ck("orbit view, so the rain is in frame", r.view === "orbit", r.view);
      ck("chat stimulated at least one district", r.regionsFlashed > 0, `regions=${r.regionsFlashed}`);
      if (needFx(ck, r.fxExposed ? {} : null, "rain")) {
        ck("rain started: the message words are in flight (fx pool / queue)", r.rainSeen, `free at rest=${r.poolFreeAtRest}`);
        ck("rain still in the air at the landing capture", r.poolFreeAtCapture != null && r.poolFreeAtCapture < r.poolFreeAtRest,
          `free at rest=${r.poolFreeAtRest}, at capture=${r.poolFreeAtCapture}`);
        ck("words landed (a splash was processed, fx pending fell below its peak)", r.splashSeen, `peak pending=${r.peakPending}, fx time at drop=${r.fxTimeAtDrop}, at capture=${r.fxTimeAtCapture}`);
        // visible in the pixels (3D canvas only, overlays hidden): new amber glyph pixels outside the scene's own flicker zone, far above the
        // same count on a third idle frame
        const need = Math.max(RAIN_MIN_PIXELS, RAIN_FACTOR * (r.idleGlyphNoise ?? 0));
        ck("the falling words are visible: new amber glyph pixels in the 3D canvas far above idle", r.fallingGlyphPixels != null && r.fallingGlyphPixels > need,
          `glyph pixels outside the idle flicker zone: falling=${r.fallingGlyphPixels}, idle frame=${r.idleGlyphNoise}, needed > ${need}`);
      }
    },
  },
  dump: {
    needs: ["city", "fx"],
    desc: "market dump: glitches / distortion weather",
    serverArgs: at("10:00", "--life-activity", "window", "--force-market", "dump"),
    path: "/?fxhold=1",                       // fx stream: holds a glitch burst on for screenshots (ignored otherwise)
    async run(c) {
      await c.waitFor(() => c.market === "dumping", 40000, "market=dumping");
      const t0 = Date.now();
      let fx = await c.fx();
      while (fx && !(fx.glitch > 0.3) && Date.now() - t0 < 12000) { c.checkAbort(); await sleep(150); fx = await c.fx(); }
      await c.settle(800);
      return { market: c.market, fx: await c.fx() };
    },
    check(r, ck) {
      ck("market is dumping", r.market === "dumping", r.market);
      if (needFx(ck, r.fx, "glitch")) {
        ck("glitch effect is active at capture (fx.glitch > 0.3, held burst)", r.fx.glitch > 0.3 && r.fx.hold === true, `glitch=${r.fx.glitch} hold=${r.fx.hold}`);
      }
    },
  },
  night: {
    needs: ["city"],
    desc: "night in the construct: darker sky, lit roads",
    serverArgs: at("22:30"),
    async run(c) { await c.settle(2500); return { clock: c.clock, stage: c.stage }; },
    check(r, ck, c) {
      ck("night clock (started 22:30)", /^22:/.test(r.clock || ""), r.clock);
      if (REF.homeMean != null) ck("the city is darker than at home in daylight (canvas mean luminance)", c.canvasMean < REF.homeMean * 0.9, `night=${c.canvasMean} home=${REF.homeMean}`);
      else ck("darker than daylight (needs the home scenario measured in THIS run)", false, "run `home` together with `night` (no --only, or --only=home,night); an earlier report.json is never used as the reference");
    },
  },
  rem: {
    needs: ["city", "fx"],
    desc: "REM: world warps and replays the day's messages",
    serverArgs: at("03:10", "--force-stage", "REM"),
    async run(c) {
      await c.waitFor(() => c.stage === "REM", 20000, "stage=REM");
      // a replay needs a memory of the day; chat is limited to 1 message / 10 s, so send one stimulus, then wait (4-8 s per replay)
      const msg = "fresh bread from the bakery and a happy walk in the park";
      const before = c.chatCount;
      await c.sendChat(msg);
      await c.waitFor(() => c.replays > 0, 30000, "a replay event (deja vu)");
      const t0 = Date.now();
      while (!c.replayTexts.some(t => t.includes("bread")) && Date.now() - t0 < 40000) { c.checkAbort(); await sleep(200); }   // day's message comes back
      await c.settle(800);
      const fx = await c.fx();
      return { stage: c.stage, replays: c.replays, replayTexts: c.replayTexts.slice(0, 4), replayedSentMessage: c.replayTexts.some(t => t.includes("bread")), fx };
    },
    check(r, ck) {
      ck("replay events arrive with text", r.replays > 0 && r.replayTexts.length > 0, `replays=${r.replays}`);
      ck("the day's message (sent during this scenario) is replayed", r.replayedSentMessage, JSON.stringify(r.replayTexts).slice(0, 160));
      if (needFx(ck, r.fx, "warp")) ck("the world warps (fx.warp > 0.05)", r.fx.warp > 0.05, `warp=${r.fx.warp}`);
    },
  },
  orbit: {
    needs: ["city", "travel"],
    desc: "orbit / overview of the whole city",
    serverArgs: at("10:00", "--life-activity", "window"),
    path: "/?view=orbit",
    async run(c) {
      await c.settle(2500);
      return { view: await c.page.evaluate(() => window.__sub01.view) };
    },
    check(r, ck) { ck("view is orbit", r.view === "orbit", r.view); },
  },
  mobile: {
    needs: ["city"],
    desc: "phone layout 390x844 (quality low)",
    serverArgs: at("10:00", "--life-activity", "window"),
    mobile: true,
    async run(c) {
      await c.settle(2500);
      const o = await c.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
        quality: window.__sub01.quality }));
      return { scrollWidth: o.sw, clientWidth: o.cw, quality: o.quality };
    },
    check(r, ck) {
      ck("no horizontal page scroll", r.scrollWidth <= r.clientWidth + 1, `${r.scrollWidth} vs ${r.clientWidth}`);
      ck("phones render at quality 'low'", r.quality === "low", r.quality);
    },
  },
  // --selftest only: the 3D canvas is hidden over a black page, so the canvas pixel checks MUST fail (they must not be satisfied by overlays)
  selftest: {
    hidden: true, noOutput: true, hideCanvas: "black",
    expectFail: ["canvas is not blank / uniform", "canvas is not almost black"],
    needs: [],
    desc: "self-test: with the 3D canvas hidden over a black page, 'canvas is not blank / uniform' and 'canvas is not almost black' must both fail",
    serverArgs: at("10:00", "--life-activity", "window"),
    async run(c) { await c.settle(1500); return {}; },
  },
};

// ---------------------------------------------------------------- one scenario run
class Aborted extends Error { constructor() { super("aborted"); } }

async function runOnce(name, sc, browser, abort) {
  const checks = [];
  const ck = (what, ok, detail = "") => checks.push({ what, ok: !!ok, detail: String(detail) });
  const server = await startServer(sc.serverArgs || [], abort);
  abort.stops.push(() => server.stop());
  let ctx = null;
  try {
    const mobile = !!sc.mobile;
    ctx = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : (sc.viewport || { width: 1440, height: 900 }),
      deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
    abort.stops.push(() => ctx.close().catch(() => {}));
    await ctx.addInitScript(CAMERA_HOOK);
    const page = await ctx.newPage();
    const errors = [];
    const glWarnings = [];                   // Chrome reports GL_INVALID_* / context loss as console "warning", not "error"
    page.on("console", m => {
      if (m.type() === "error") errors.push(m.text());
      else if (m.type() === "warning" && /GL_INVALID_|GL_OUT_OF_MEMORY|CONTEXT_LOST|context (was )?lost|WebGL: INVALID_/i.test(m.text())) glWarnings.push(m.text().slice(0, 200));
    });
    page.on("pageerror", e => errors.push("pageerror: " + e.message));
    const c = { page, life: null, market: null, stage: null, clock: null, replays: 0, replayTexts: [], chatCount: 0, overrideShot: null,
      gifFrames: null, extraShots: {}, canvasMean: null };
    page.on("websocket", ws => ws.on("framereceived", f => {
      let m; try { m = JSON.parse(typeof f.payload === "string" ? f.payload : f.payload.toString()); } catch { return; }
      if (m.type === "tick") {
        if (m.life) c.life = m.life;
        if (m.market != null) c.market = m.market;
        if (m.sleep) { c.stage = m.sleep.stage; c.clock = m.sleep.clock; }
        for (const ev of m.events || []) if (ev.type === "replay" && ev.text) { c.replays++; c.replayTexts.push(String(ev.text).toLowerCase()); }
      } else if (m.type === "chat") c.chatCount++;
      else if (m.type !== "mind" && m.type !== "speech") c.lastMsg = JSON.stringify(m).slice(0, 160);
    }));
    c.checkAbort = () => { if (abort.aborted) throw new Aborted(); };
    c.settle = async ms => { c.checkAbort(); await page.waitForTimeout(ms); c.checkAbort(); };
    c.fx = () => page.evaluate(() => { const f = window.__sub01 && window.__sub01.fx; return f ? JSON.parse(JSON.stringify(f)) : null; });
    c.waitFor = async (fn, ms, what, retry = false) => {
      const t0 = Date.now();
      while (!fn()) {
        c.checkAbort();
        if (Date.now() - t0 > ms) throw Object.assign(new Error(`timed out after ${ms / 1000}s waiting for: ${what} (last non-tick message: ${c.lastMsg || "none"})`), { retry });
        await sleep(100);
      }
    };

    // send through the page's own chat form; retry when the websocket was (re)connecting and the page refused ("not connected")
    // (the server allows 1 message / 10 s, so a retry only happens when nothing came back at all)
    c.sendChat = async text => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        const n = c.chatCount;
        await page.fill("#chat input[aria-label=message]", text);
        await page.keyboard.press("Enter");
        const t0 = Date.now(), limit = attempt < 3 ? 8000 : 25000;
        for (;;) {
          c.checkAbort();
          if (c.chatCount > n) return;
          const ack = await page.evaluate(() => (document.getElementById("chat-ack") || {}).textContent || "").catch(() => "");
          if (/not connected/i.test(ack) && attempt < 3) break;                 // the page refused at once: retry without waiting
          if (Date.now() - t0 > limit) { if (attempt === 3) throw new Error(`timed out waiting for the chat message to come back (ack: "${ack}", last non-tick message: ${c.lastMsg || "none"})`); break; }
          await sleep(100);
        }
        await sleep(500);
      }
    };

    await page.goto(`http://127.0.0.1:${server.port}${sc.path || "/"}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__sub01 && window.__sub01.ready === true, null, { timeout: 90000 })
      .catch(() => { c.checkAbort(); throw new Error("window.__sub01.ready never became true within 90 s"); });
    ck("page ready (window.__sub01.ready)", true);

    const extra = await sc.run(c);
    c.checkAbort();
    const deliverable = c.overrideShot || await page.screenshot(jpgOpts());      // what is saved: exactly the requested format

    // --- generic checks
    const sub = await page.evaluate(() => JSON.parse(JSON.stringify(window.__sub01 || null)));
    const honesty = await page.evaluate(line => {
      const el = document.getElementById("honesty");
      if (!el) return { found: false };
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      // not covered by another element: whatever is topmost at the line's centre must be the line itself (or inside it)
      const pe = el.style.pointerEvents; el.style.pointerEvents = "auto";
      const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), cy = Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2));
      const top = document.elementFromPoint(cx, cy);
      el.style.pointerEvents = pe;
      const uncovered = !!top && el.contains(top);
      return { found: true, uncovered, coveredBy: uncovered ? null : (top ? (top.id ? "#" + top.id : top.tagName) : "nothing"), text: el.textContent.trim(), visible: cs.display !== "none" && cs.visibility !== "hidden" && +cs.opacity > 0.3
        && r.width > 50 && r.height > 8 && r.bottom > 0 && r.top < innerHeight, exact: el.textContent.replace(/\s+/g, " ").includes(line) };
    }, HONESTY);
    ck("honesty line present and visible", honesty.found && honesty.visible && honesty.exact,
      honesty.found ? `visible=${honesty.visible} exactText=${honesty.exact}` : "no #honesty element");
    ck("honesty line is not covered by another element", honesty.found && honesty.uncovered, honesty.found ? `covered by ${honesty.coveredBy}` : "no #honesty element");
    // pixel checks on the 3D canvas ALONE (overlays hidden), so HUD / labels / mini brain cannot mask a broken scene
    const co = await canvasOnly(page, !!sc.hideCanvas);
    const px = co ? co.stats : null;
    if (!co) ck("3D canvas present", false, "no canvas element");
    else {
      c.canvasMean = px.mean;
      if (name === "home") REF.homeMean = px.mean;
      ck("canvas is not blank / uniform", px.std > 4 && px.colours >= 8, `std=${px.std} colours=${px.colours} mean=${px.mean}`);
      ck("canvas is not almost black", px.mean > 8 || px.brightShare > 0.01, `mean=${px.mean} brightShare=${px.brightShare}`);
    }
    ck("no console errors", errors.length === 0, errors.slice(0, 3).join(" || "));
    ck("no WebGL errors (GL_INVALID_*, context lost) in the console", glWarnings.length === 0, glWarnings.slice(0, 3).join(" || "));
    ck("websocket connected", sub && sub.connected === true, `connected=${sub?.connected}`);
    if (sc.check) sc.check(extra, ck, c);
    if (!flag("allow-stubs")) {
      const stubs = stubModules().filter(m => (sc.needs || []).includes(m.split(" ")[0]));
      ck("scenario modules are real implementations (not STUB files)", stubs.length === 0,
        `still a STUB in this checkout: ${stubs.join(", ")} (merge that stream, or pass --allow-stubs)`);
    }
    // the demo server must not have crashed / logged a Python traceback while the scenario ran
    let slog = ""; try { slog = readFileSync(server.logPath, "utf8"); } catch { /* no log */ }
    ck("no Python traceback in the server log", !/Traceback \(most recent call last\)/.test(slog),
      (slog.match(/Traceback[\s\S]{0,400}/) || [""])[0].replace(/\s+/g, " "));

    // GIF (walk only): encoded before any file is written so its check counts towards the scenario verdict
    let gif = null;
    if (sc.gifOnly) {
      const frames = c.gifFrames || [];
      if (!gifenc || !pngjs) ck("walk.gif written", false, "gifenc/pngjs not installed (cd tests/e2e && npm install)");
      else if (frames.length < MIN_GIF_FRAMES) ck("walk.gif written", false, `only ${frames.length} frames captured, need at least ${MIN_GIF_FRAMES}`);
      else {
        gif = encodeGif(frames);
        ck("walk.gif written", gif.frames >= MIN_GIF_FRAMES && gif.seconds >= 10,
          `${gif.frames} of ${gif.captured} captured frames over ${gif.seconds.toFixed(1)} s, real-time playback (frame delays = real gaps, no clamp), ${gif.w}x${gif.h}, ${(gif.bytes.length / 1e6).toFixed(1)} MB`);
      }
    }
    if (sc.expectFail) for (const k of checks) if (sc.expectFail.includes(k.what)) { k.what += " [self-test: must FAIL]"; k.ok = !k.ok; }
    let file = null;
    if (!sc.noOutput && (!sc.gifOnly || gif)) {
      c.checkAbort();                                        // a timed-out attempt must never write files
      mkdirSync(OUT, { recursive: true });
      // a failing scenario never replaces the committed screenshots: its captures get a ".FAILED" suffix instead
      const tag = checks.every(k => k.ok) ? "" : ".FAILED";
      const put = (n, ext, buf) => {
        const good = path.join(OUT, `${n}.${ext}`), bad = path.join(OUT, `${n}.FAILED.${ext}`);
        if (tag) { writeFileSync(bad, buf); return bad; }
        writeFileSync(good, buf); rmSync(bad, { force: true }); return good;
      };
      if (!sc.gifOnly) {
        file = put(name, EXT, deliverable);
        for (const [n, buf] of Object.entries(c.extraShots)) put(n, EXT, buf);
      }
      if (gif) file = put("walk", "gif", gif.bytes);
    }
    return { extra, checks, metrics: { fps: sub?.fps ?? null, drawCalls: sub?.drawCalls ?? null, triangles: sub?.triangles ?? null,
      quality: sub?.quality ?? null, view: sub?.view ?? null, districts: sub?.districts ?? null, fibres: sub?.fibres ?? null, pixels: px },
      screenshot: file ? path.relative(ROOT, file) : null, consoleErrors: errors };
  } finally {
    try { await ctx?.close(); } catch { /* ignore */ }
    server.stop();
  }
}

/** Encodes up to MAX_GIF_FRAMES evenly spaced captured frames ({buf: png, ts: ms}); each frame's delay is the real time until the next selected frame
 *  (so the GIF plays at real speed). Returns {bytes, frames, seconds, w, h} (checks are added by the caller). */
const MIN_GIF_FRAMES = 20, MAX_GIF_FRAMES = 60;
function encodeGif(all) {
  const { GIFEncoder, quantize, applyPalette } = gifenc;
  const n = Math.min(MAX_GIF_FRAMES, all.length);
  const frames = Array.from({ length: n }, (_, i) => all[Math.round(i * (all.length - 1) / Math.max(1, n - 1))]);
  const enc = GIFEncoder();
  let W = 0, H = 0;
  frames.forEach(({ buf }, fi) => {
    const p = decode(buf);
    W = p.width; H = p.height;
    const rgba = new Uint8Array(p.data.buffer, p.data.byteOffset, p.data.length);
    for (let i = 3; i < rgba.length; i += 4) rgba[i] = 255;
    const palette = quantize(rgba, 128);
    const gap = fi + 1 < frames.length ? frames[fi + 1].ts - frames[fi].ts : 200;
    enc.writeFrame(applyPalette(rgba, palette), W, H, { palette, delay: Math.max(20, Math.round(gap)) });     // real time (ms), no clamp
  });
  enc.finish();
  return { bytes: Buffer.from(enc.bytes()), frames: n, captured: all.length, seconds: n > 1 ? (frames[n - 1].ts - frames[0].ts) / 1000 : 0, w: W, h: H };
}

async function runScenario(name, browser) {
  const sc = SCENARIOS[name];
  const t0 = Date.now();
  const tries = sc.retries || 1;
  let res = null, err = null;
  for (let a = 1; a <= tries; a++) {
    err = null;
    const abort = { aborted: false, stops: [] };
    const stopAll = () => { abort.aborted = true; for (const f of abort.stops) { try { f(); } catch { /* ignore */ } } };
    // the timeout cancels THIS attempt (server + browser context closed, no files written) and we wait for it to unwind
    const timer = setTimeout(() => { abort.timedOut = true; stopAll(); }, SCENARIO_TIMEOUT_MS);
    try {
      res = await runOnce(name, sc, browser, abort);
      break;
    } catch (e) {
      err = abort.timedOut ? new Error(`scenario timeout ${SCENARIO_TIMEOUT_MS / 1000}s`) : e;
      if (abort.timedOut || !e.retry) break;
      log(`  [${name}] attempt ${a}/${tries}: ${e.message} - retrying with a fresh server`);
    } finally { clearTimeout(timer); stopAll(); }
  }
  const secs = +((Date.now() - t0) / 1000).toFixed(1);
  if (err || !res) {
    return { scenario: name, description: sc.desc, pass: false, seconds: secs, error: String(err?.message || err), checks: [] };
  }
  return { scenario: name, description: sc.desc, pass: res.checks.every(c => c.ok), seconds: secs, ...res };
}

// ---------------------------------------------------------------- main
async function main() {
  if (!playwright) { console.error("playwright not found: cd tests/e2e && npm install && npx playwright install chromium (or set E2E_TOOLS / E2E_CHROME)"); process.exit(2); }
  if (!pngjs) { console.error("pngjs not found: cd tests/e2e && npm install"); process.exit(2); }
  const only = opt("only", "").split(",").filter(Boolean);
  let names = SELFTEST ? ["selftest"] : only.length ? only : Object.keys(SCENARIOS).filter(k => !SCENARIOS[k].hidden);
  if (WANT_GIF && !SELFTEST && names.includes("walk") && !names.includes("walk-gif")) names.splice(names.indexOf("walk") + 1, 0, "walk-gif");   // --gif: the walk again, captured for the GIF
  for (const n of names) if (!SCENARIOS[n]) { console.error(`unknown scenario '${n}' (have: ${Object.keys(SCENARIOS).join(", ")})`); process.exit(2); }
  if (!SELFTEST) mkdirSync(OUT, { recursive: true });
  const browser = await playwright.chromium.launch({ ...(CHROME ? { executablePath: CHROME } : {}),
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"] });
  const results = [];
  try {
    for (const n of names) {
      log(`> ${n}: ${SCENARIOS[n].desc}`);
      const r = await runScenario(n, browser);
      results.push(r);
      for (const c of r.checks) log(`    ${c.ok ? "ok  " : "FAIL"} ${c.what}${c.detail && !c.ok ? " - " + c.detail : ""}`);
      if (r.error) log(`    FAIL ${r.error}`);
      log(`  ${r.pass ? "PASS" : "FAIL"} ${n} (${r.seconds}s)`);
    }
  } finally {
    await browser.close().catch(() => {});
    killAll();
  }
  if (SELFTEST) {
    const ok = results.every(r => r.pass);
    log(`\nself-test ${ok ? "PASSED (with the 3D canvas hidden: 'canvas is not blank / uniform' fails, and so does 'canvas is not almost black' over a black page)" : "FAILED (a canvas pixel check can be satisfied without the 3D canvas)"}`);
    process.exit(ok ? 0 : 1);
  }
  const report = {
    generated: new Date().toISOString(),
    note: "fps, drawCalls and triangles are measured with SOFTWARE rendering (headless Chromium + SwiftShader, no GPU). " +
      "fps is NOT representative of a phone or desktop GPU; use it only to compare scenarios. Target on real devices: 30 fps phones, 60 fps desktop.",
    renderer: "software (SwiftShader)",
    stubModules: stubModules(),
    passed: results.filter(r => r.pass).map(r => r.scenario),
    failed: results.filter(r => !r.pass).map(r => r.scenario),
    scenarios: Object.fromEntries(results.map(r => [r.scenario, {
      pass: r.pass, seconds: r.seconds, description: r.description, error: r.error || null, screenshot: r.screenshot || null,
      fps_software_rendered: r.metrics?.fps ?? null, drawCalls: r.metrics?.drawCalls ?? null, triangles: r.metrics?.triangles ?? null,
      quality: r.metrics?.quality ?? null, view: r.metrics?.view ?? null, districts: r.metrics?.districts ?? null, fibres: r.metrics?.fibres ?? null,
      pixels: r.metrics?.pixels ?? null, details: r.extra ?? null, checks: r.checks, consoleErrors: r.consoleErrors ?? [] }])),
  };
  const repPath = path.join(OUT, "report.json");
  // a partial run (--only) merges into the existing report so earlier scenarios are not lost
  if (only.length && existsSync(repPath)) {
    try {
      const old = JSON.parse(readFileSync(repPath, "utf8"));
      report.scenarios = { ...old.scenarios, ...report.scenarios };
      report.passed = Object.keys(report.scenarios).filter(k => report.scenarios[k].pass);
      report.failed = Object.keys(report.scenarios).filter(k => !report.scenarios[k].pass);
    } catch { /* overwrite */ }
  }
  writeFileSync(repPath, JSON.stringify(report, null, 2) + "\n");
  log(`\n${results.filter(r => r.pass).length}/${results.length} scenarios passed` +
    (report.failed.length ? `; FAILED: ${results.filter(r => !r.pass).map(r => r.scenario).join(", ")}` : "") + `  -> ${path.relative(ROOT, repPath)}`);
  process.exit(results.every(r => r.pass) ? 0 : 1);
}
main().catch(e => { console.error(e); killAll(); process.exit(1); });
