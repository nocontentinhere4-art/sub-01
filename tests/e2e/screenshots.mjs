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
// --selftest: runs the checks against a page whose 3D canvas is hidden and expects the "canvas is not blank" check to FAIL
// (proves the pixel check cannot be satisfied by the DOM overlays alone). Writes nothing.
// Env: E2E_CHROME (Chromium path; default: Playwright's own browser), E2E_PYTHON, E2E_TOOLS (extra dir with node_modules).
//
// Scenarios: home, walk, chat, dump, night, rem, orbit, mobile.
// Output: <out>/<scenario>.png|jpg (+ chat-falling), <out>/report.json, and with --gif <out>/walk.gif (<= 60 frames of the
// walk, played back at the real capture rate).
// Assertions are state-based where the page exposes state (life ticks, window.__sub01.fx) and otherwise compare against
// an idle baseline (the scene is never static: activity animation + camera sway); the canvas pixels are measured on the
// 3D canvas alone (all DOM overlays hidden for that capture).
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
async function canvasOnly(page, hide = false) {
  const rect = await page.evaluate(MAIN_CANVAS_JS);
  if (!rect || rect[2] - rect[0] < 4 || rect[3] - rect[1] < 4) return null;
  await page.evaluate(h => {
    const st = document.createElement("style"); st.id = "e2e-clean";
    st.textContent = "body *{visibility:hidden !important}[data-e2e-main]{visibility:visible !important}";
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

/** Construct modules still carrying the "STUB" header (their stream has not been merged into this checkout yet). */
function stubModules() {
  const out = [];
  for (const m of ["city", "fx", "travel"]) {
    try { if (/^\s*\/\/\s*STUB\b/.test(readFileSync(path.join(ROOT, "web/construct", m + ".js"), "utf8").slice(0, 200))) out.push(m); } catch { out.push(m + " (missing)"); }
  }
  return out;
}

// values shared between scenarios of one run (home runs first)
const REF = { idleShare: null, homeMean: null };
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
      // idle baseline: how much the (never static) scene changes by itself over 2.5 s; other scenarios must clearly exceed it
      const rect = await canvasRect(c.page);
      const a = await c.page.screenshot({ type: "png" });
      await c.settle(2500);
      const b = await c.page.screenshot({ type: "png" });
      REF.idleShare = diffShare(a, b, rect);
      return { place: c.life.place, clock: c.clock, idleChangedShare: REF.idleShare };
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
      // capture frames for the gif while walking; keep the frame closest to the middle of the walk as the screenshot
      const frames = [], samples = [];
      let best = null, firstBuf = null, lastBuf = null;
      while (c.life && c.life.route && c.life.route.join(">") === routeKey && c.life.progress < 0.97 && frames.length < 60 && Date.now() - t0 < 60000) {
        c.checkAbort();
        const p = c.life.progress;
        const buf = await c.page.screenshot({ type: "png" });
        const ts = Date.now();
        if (WANT_GIF) frames.push({ buf, ts });
        samples.push(p);
        firstBuf ||= buf; lastBuf = buf;
        if (p >= 0.3 && p <= 0.7 && (!best || Math.abs(p - 0.5) < Math.abs(best.p - 0.5)))
          best = { p, buf: FORMAT === "png" ? buf : await c.page.screenshot(jpgOpts()) };       // the saved frame is encoded in the requested format
        await sleep(WANT_GIF ? 150 : 400);
      }
      if (!best) throw Object.assign(new Error("never captured a frame with life.progress in 0.3..0.7 (saw up to " + (c.life?.progress ?? "n/a") + ")"), { retry: true });
      c.overrideShot = best.buf;
      const rect = await canvasRect(c.page);
      const moved = firstBuf && lastBuf && firstBuf !== lastBuf ? diffShare(firstBuf, lastBuf, rect) : 0;
      c.gifFrames = frames;
      const need = Math.min(0.85, Math.max(0.4, 2 * (REF.idleShare ?? 0.3)));
      return { walkProgress: best.p, route: routeKey, view: viewAtStart, progressStart: samples[0], progressEnd: samples[samples.length - 1],
        progressMonotone: samples.every((v, i) => i === 0 || v >= samples[i - 1] - 1e-6), gifFrames: frames.length,
        routeHasStreet: r0.some(p => /street/.test(p)), viewChangedShare: moved, viewChangeNeeded: +need.toFixed(3) };
    },
    check(r, ck) {
      const r0 = r.route.split(">");
      ck("outbound walk: route starts at a home place", HOME_PLACES.has(r0[0]), r.route);
      ck("outbound walk: route ends at the reward district (bakery)", REWARD_PLACES.has(r0[r0.length - 1]), r.route);
      ck("first-person view (window.__sub01.view == 'first')", r.view === "first", r.view);
      ck("life.progress advances along the route", r.progressMonotone && r.progressEnd - r.progressStart > 0.25, `${r.progressStart} -> ${r.progressEnd}`);
      ck("camera view changes clearly more than the idle baseline (first vs last frame)", r.viewChangedShare > r.viewChangeNeeded,
        `changed pixel share=${r.viewChangedShare}, needed > ${r.viewChangeNeeded} (2x idle baseline, clamped to 0.4..0.85)`);
    },
  },
  chat: {
    needs: ["city", "fx"],
    desc: "chat message falls as orange rain made of its words and lands on the districts it stimulates",
    serverArgs: at("10:00", "--life-activity", "window"),
    async run(c) {
      await c.settle(1500);
      const rect = await canvasRect(c.page);
      const shotBefore = await c.page.screenshot({ type: "png" });
      await c.settle(2500);
      const idleShare = diffShare(shotBefore, await c.page.screenshot({ type: "png" }), rect);      // baseline over the same 2.5 s
      const fx0 = await c.fx();
      const before = c.chatCount, shotSend = await c.page.screenshot({ type: "png" });
      await c.page.fill("#chat input[aria-label=message]", "fresh bread and a happy morning in the park");
      await c.page.keyboard.press("Enter");
      await c.waitFor(() => c.chatCount > before, 10000, "the chat message to come back");
      let rainSeen = null, rainStartMs = null, fxMin = fx0 ? fx0.free : null;
      if (fx0) {
        // words are "in flight" while the pool has fewer free slots than at rest (or the message is still queued)
        const t0 = Date.now();
        while (Date.now() - t0 < 6000) {
          c.checkAbort();
          const f = await c.fx();
          if (f && (f.queued > 0 || f.free < fx0.free)) { rainSeen = f; rainStartMs = Date.now(); break; }
          await sleep(80);
        }
      }
      if (rainStartMs) {
        // each word falls 2.4-3.3 s (fx.js dropMessage): ~1 s in it is falling, ~3 s in the first words have landed and splashed
        await sleep(Math.max(0, rainStartMs + 1000 - Date.now()));
        c.extraShots["chat-falling"] = await c.page.screenshot(jpgOpts());
        await sleep(Math.max(0, rainStartMs + 3000 - Date.now()));
      } else await c.settle(3000);
      c.overrideShot = await c.page.screenshot(jpgOpts());
      const fxEnd = await c.fx();
      const after = await c.page.screenshot({ type: "png" });
      const flashed = await c.page.evaluate(() => window.__sub01 && window.__sub01.lastChatRegions);
      return { chatEchoed: true, regionsFlashed: flashed ?? null, fxExposed: !!fx0, rainSeen: !!rainSeen, rainQueuedAtStart: rainSeen?.queued ?? null,
        poolFreeAtRest: fx0?.free ?? null, poolFreeAtCapture: fxEnd?.free ?? null, idleChangedShare: idleShare,
        sceneChangedShare: diffShare(shotSend, after, rect) };
    },
    check(r, ck, c) {
      ck("chat stimulated at least one district", r.regionsFlashed > 0, `regions=${r.regionsFlashed}`);
      if (needFx(ck, r.fxExposed ? {} : null, "rain")) {
        ck("rain started: the message words are in flight (fx pool / queue)", r.rainSeen, `free at rest=${r.poolFreeAtRest}, at capture=${r.poolFreeAtCapture}`);
        ck("rain still in the air at the landing capture (~3 s after it started)", r.poolFreeAtCapture != null && r.poolFreeAtCapture < r.poolFreeAtRest,
          `free at rest=${r.poolFreeAtRest}, at capture=${r.poolFreeAtCapture}`);
      } else ck("the message changes the scene clearly more than idle (pixel fallback without fx state)", r.sceneChangedShare > 2 * r.idleChangedShare,
        `changed=${r.sceneChangedShare}, idle=${r.idleChangedShare}`);
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
      else ck("darker than daylight (needs the home scenario in the same run)", false, "run `home` together with `night` (no --only, or --only=home,night)");
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
      await c.page.fill("#chat input[aria-label=message]", msg);
      await c.page.keyboard.press("Enter");
      await c.waitFor(() => c.chatCount > before, 10000, "the chat message to come back");
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
  // --selftest only: the 3D canvas is hidden, so the canvas pixel checks MUST fail (they must not be satisfied by overlays)
  selftest: {
    hidden: true, noOutput: true, hideCanvas: true,
    expectFail: ["canvas is not blank / uniform"],
    needs: [],
    desc: "self-test: with the 3D canvas hidden the blank-canvas check must fail",
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
    ctx = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
      deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
    abort.stops.push(() => ctx.close().catch(() => {}));
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
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
    }));
    c.checkAbort = () => { if (abort.aborted) throw new Aborted(); };
    c.settle = async ms => { c.checkAbort(); await page.waitForTimeout(ms); c.checkAbort(); };
    c.fx = () => page.evaluate(() => { const f = window.__sub01 && window.__sub01.fx; return f ? JSON.parse(JSON.stringify(f)) : null; });
    c.waitFor = async (fn, ms, what, retry = false) => {
      const t0 = Date.now();
      while (!fn()) {
        c.checkAbort();
        if (Date.now() - t0 > ms) throw Object.assign(new Error(`timed out after ${ms / 1000}s waiting for: ${what}`), { retry });
        await sleep(100);
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
      return { found: true, text: el.textContent.trim(), visible: cs.display !== "none" && cs.visibility !== "hidden" && +cs.opacity > 0.3
        && r.width > 50 && r.height > 8 && r.bottom > 0 && r.top < innerHeight, exact: el.textContent.replace(/\s+/g, " ").includes(line) };
    }, HONESTY);
    ck("honesty line present and visible", honesty.found && honesty.visible && honesty.exact,
      honesty.found ? `visible=${honesty.visible} exactText=${honesty.exact}` : "no #honesty element");
    // pixel checks on the 3D canvas ALONE (overlays hidden), so HUD / labels / mini brain cannot mask a broken scene
    const co = await canvasOnly(page, !!sc.hideCanvas);
    const px = co ? co.stats : null;
    if (!co) ck("3D canvas present", false, "no canvas element");
    else {
      c.canvasMean = px.mean;
      if (name === "home") REF.homeMean = px.mean;
      ck("canvas is not blank / uniform", px.std > 4 && px.colours >= 8, `std=${px.std} colours=${px.colours} mean=${px.mean}`);
      ck("canvas is not almost black", px.mean > 2 || px.brightShare > 0.002, `mean=${px.mean} brightShare=${px.brightShare}`);
    }
    ck("no console errors", errors.length === 0, errors.slice(0, 3).join(" || "));
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

    let file = null;
    if (!sc.noOutput) {
      c.checkAbort();                                        // a timed-out attempt must never write files
      mkdirSync(OUT, { recursive: true });
      file = path.join(OUT, `${name}.${EXT}`);
      writeFileSync(file, deliverable);
      for (const [n, buf] of Object.entries(c.extraShots)) writeFileSync(path.join(OUT, `${n}.${EXT}`), buf);
      if (name === "walk" && WANT_GIF && c.gifFrames?.length) await writeGif(c.gifFrames, path.join(OUT, "walk.gif"), ck);
    }
    if (sc.expectFail) for (const k of checks) if (sc.expectFail.includes(k.what)) { k.what += " [self-test: must FAIL]"; k.ok = !k.ok; }
    return { extra, checks, metrics: { fps: sub?.fps ?? null, drawCalls: sub?.drawCalls ?? null, triangles: sub?.triangles ?? null,
      quality: sub?.quality ?? null, view: sub?.view ?? null, districts: sub?.districts ?? null, fibres: sub?.fibres ?? null, pixels: px },
      screenshot: file ? path.relative(ROOT, file) : null, consoleErrors: errors };
  } finally {
    try { await ctx?.close(); } catch { /* ignore */ }
    server.stop();
  }
}

async function writeGif(frames, file, ck) {
  if (!gifenc || !pngjs) { ck("gif written", false, "gifenc/pngjs not installed (cd tests/e2e && npm install)"); return; }
  const { GIFEncoder, quantize, applyPalette } = gifenc;
  const W = 640;
  const enc = GIFEncoder();
  let H = 0;
  frames.forEach(({ buf }, fi) => {
    const p = decode(buf);
    const w = W, h = Math.round(p.height * (W / p.width));
    H = h;
    const rgba = new Uint8Array(w * h * 4);
    for (let y = 0; y < h; y++) {
      const sy = Math.min(p.height - 1, Math.floor(y * p.height / h));
      for (let x = 0; x < w; x++) {
        const sx = Math.min(p.width - 1, Math.floor(x * p.width / w));
        const si = (sy * p.width + sx) * 4, di = (y * w + x) * 4;
        rgba[di] = p.data[si]; rgba[di + 1] = p.data[si + 1]; rgba[di + 2] = p.data[si + 2]; rgba[di + 3] = 255;
      }
    }
    const palette = quantize(rgba, 128);
    // real-time playback: the delay is the time until the next captured frame (screenshot cost included)
    const delay = fi + 1 < frames.length ? Math.min(1000, Math.max(40, frames[fi + 1].ts - frames[fi].ts)) : 500;
    enc.writeFrame(applyPalette(rgba, palette), w, h, { palette, delay });
  });
  enc.finish();
  writeFileSync(file, Buffer.from(enc.bytes()));
  const secs = (frames[frames.length - 1].ts - frames[0].ts) / 1000;
  ck("walk.gif written", true, `${frames.length} frames over ${secs.toFixed(0)} s (real-time playback), ${W}x${H}, ${(enc.bytes().length / 1e6).toFixed(1)} MB`);
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
  const names = SELFTEST ? ["selftest"] : only.length ? only : Object.keys(SCENARIOS).filter(k => !SCENARIOS[k].hidden);
  for (const n of names) if (!SCENARIOS[n]) { console.error(`unknown scenario '${n}' (have: ${Object.keys(SCENARIOS).join(", ")})`); process.exit(2); }
  if (!SELFTEST) mkdirSync(OUT, { recursive: true });
  try { REF.homeMean = JSON.parse(readFileSync(path.join(OUT, "report.json"), "utf8")).scenarios?.home?.pixels?.mean ?? null; } catch { /* no earlier report */ }
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
    log(`\nself-test ${results[0].pass ? "PASSED (the blank-canvas checks fail when the 3D canvas is hidden)" : "FAILED (the canvas pixel checks can be satisfied without the 3D canvas)"}`);
    process.exit(results[0].pass ? 0 : 1);
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
