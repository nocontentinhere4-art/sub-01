#!/usr/bin/env node
// SUB-01 "the construct" - headless end-to-end screenshot check.
//
// For every scenario: start `live_server.py --demo` on a free port with a temporary data dir, open the page in
// headless Chromium (software WebGL), wait for window.__sub01.ready, drive the scenario, capture a screenshot and run
// checks (no console errors, canvas is not blank/uniform, honesty line visible, scenario-specific assertions).
//
//   node tests/e2e/screenshots.mjs [--only=home,walk,...] [--out=docs/real-world/screenshots] [--gif]
//                                  [--allow-stubs] [--python=/path/to/python] [--format=png|jpg] [--timeout=150]
//
// Scenarios: home, walk, chat, dump, night, rem, orbit, mobile.
// Output: <out>/<scenario>.png, <out>/report.json, and with --gif <out>/walk.gif (~60 frames of the walk).
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
const playwright = tryRequire("playwright", ["/home/user/wt/_tools", ROOT]);
const pngjs = tryRequire("pngjs");
const gifenc = tryRequire("gifenc");

// ---------------------------------------------------------------- args
const argv = process.argv.slice(2);
const opt = (k, d) => { const a = argv.find(x => x.startsWith(`--${k}=`)); return a ? a.slice(k.length + 3) : d; };
const flag = k => argv.includes(`--${k}`);
const OUT = path.resolve(ROOT, opt("out", "docs/real-world/screenshots"));
const PY = opt("python", process.env.E2E_PYTHON || (existsSync("/home/user/sub-01/.venv/bin/python") ? "/home/user/sub-01/.venv/bin/python" : "python3"));
const CHROME = opt("chrome", process.env.E2E_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome");
const FORMAT = opt("format", "png") === "jpg" ? "jpeg" : "png";
const EXT = FORMAT === "jpeg" ? "jpg" : "png";
const SCENARIO_TIMEOUT_MS = +opt("timeout", 150) * 1000;
const WANT_GIF = flag("gif");
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

async function startServer(args) {
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
const canvasRect = page => page.evaluate(() => { const r = (document.querySelector("#scene canvas") || document.querySelector("canvas"))?.getBoundingClientRect(); return r ? [r.left, r.top, r.right, r.bottom] : [0, 0, 100, 100]; });

/** Construct modules still carrying the "STUB" header (their stream has not been merged into this checkout yet). */
function stubModules() {
  const out = [];
  for (const m of ["city", "fx", "travel"]) {
    try { if (/^\s*\/\/\s*STUB\b/.test(readFileSync(path.join(ROOT, "web/construct", m + ".js"), "utf8").slice(0, 200))) out.push(m); } catch { out.push(m + " (missing)"); }
  }
  return out;
}

// ---------------------------------------------------------------- scenarios
// live_server.py only honours --start together with --time-scale != 1; 1.001 keeps the clock effectively real-time.
const at = (hhmm, ...rest) => ["--start", hhmm, "--time-scale", "1.001", ...rest];
// serverArgs: extra live_server.py flags. url: page path. run(ctx): drive the page, return extra checks.
const SCENARIOS = {
  home: {
    needs: ["city"],
    desc: "home district, default-network city around the window (daylight)",
    serverArgs: at("10:00", "--life-activity", "window"),
    async run(c) {
      await c.waitFor(() => c.life && c.life.place === "window" && !(c.life.progress > 0), 60000, "reach the window");
      await c.settle(1500);
      return { place: c.life.place, clock: c.clock };
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
      await c.waitFor(() => c.life && c.life.route && c.life.route.length > 1, 15000, "a walk to start");
      if (c.life.progress > 0.6) throw Object.assign(new Error("page was ready too late (progress already " + c.life.progress + ")"), { retry: true });
      // capture frames for the gif while walking; keep the frame closest to the middle of the walk as the screenshot
      const frames = [];
      let best = null, firstBuf = null, lastBuf = null;
      while (c.life && c.life.route && c.life.route.length > 1 && c.life.progress < 0.97 && frames.length < 60 && Date.now() - t0 < 60000) {
        const p = c.life.progress;
        const buf = await c.page.screenshot({ type: "png" });
        if (WANT_GIF) frames.push(buf);
        firstBuf ||= buf; lastBuf = buf;
        if (p >= 0.3 && p <= 0.7 && (!best || Math.abs(p - 0.5) < Math.abs(best.p - 0.5))) best = { p, buf, route: c.life.route, place: c.life.place };
        await sleep(WANT_GIF ? 150 : 400);
      }
      if (!best) throw Object.assign(new Error("never captured a frame with life.progress in 0.3..0.7 (saw up to " + (c.life?.progress ?? "n/a") + ")"), { retry: true });
      c.overrideShot = best.buf;
      c.walkMoved = firstBuf && lastBuf && firstBuf !== lastBuf ? diffShare(firstBuf, lastBuf, await canvasRect(c.page)) : 0;
      c.gifFrames = frames;
      return { walkProgress: best.p, route: best.route.join(">"), placeAtShot: best.place,
        routeHasStreet: best.route.some(p => /street/.test(p)), gifFrames: frames.length, viewChangedShare: c.walkMoved };
    },
    check(r, ck) {
      ck("first-person view changes while walking (first vs last frame)", r.viewChangedShare > 0.05, `changed pixel share=${r.viewChangedShare}`);
    },
  },
  chat: {
    needs: ["city", "fx"],
    desc: "chat message falls as orange rain made of its words and lands on the districts it stimulates",
    serverArgs: at("10:00", "--life-activity", "window"),
    async run(c) {
      await c.settle(1500);
      const before = c.chatCount;
      const shotBefore = await c.page.screenshot({ type: "png" });
      await c.page.fill("#chat input", "fresh bread and a happy morning in the park");
      await c.page.keyboard.press("Enter");
      await c.waitFor(() => c.chatCount > before, 10000, "the chat message to come back");
      await c.settle(1000);                 // rain is falling / landing
      const sceneChanged = diffShare(shotBefore, await c.page.screenshot({ type: "png" }), await canvasRect(c.page));
      const flashed = await c.page.evaluate(() => window.__sub01 && window.__sub01.lastChatRegions);
      return { chatEchoed: true, regionsFlashed: flashed ?? null, sceneChangedShare: sceneChanged, fxText: await c.page.evaluate(() => (document.getElementById("fx")?.innerText || "").slice(0, 120)) };
    },
    check(r, ck) { 
      ck("chat stimulated at least one district", r.regionsFlashed > 0, `regions=${r.regionsFlashed}`);
      ck("the message visibly changes the scene (rain / flash)", r.sceneChangedShare > 0.01, `changed pixel share=${r.sceneChangedShare}`);
    },
  },
  dump: {
    needs: ["city", "fx"],
    desc: "market dump: glitches / distortion weather",
    serverArgs: at("10:00", "--life-activity", "window", "--force-market", "dump"),
    async run(c) {
      await c.waitFor(() => c.market === "dumping", 40000, "market=dumping");
      await c.settle(1800);
      return { market: c.market };
    },
  },
  night: {
    needs: ["city"],
    desc: "night in the construct: darker sky, lit roads",
    serverArgs: at("22:30"),
    async run(c) { await c.settle(2500); return { clock: c.clock, stage: c.stage }; },
    check(r, ck) { ck("night clock (started 22:30)", /^22:/.test(r.clock || ""), r.clock); },
  },
  rem: {
    needs: ["city", "fx"],
    desc: "REM: world warps and replays the day's messages",
    serverArgs: at("03:10", "--force-stage", "REM"),
    async run(c) {
      await c.waitFor(() => c.stage === "REM", 20000, "stage=REM");
      // a replay needs a memory of the day; chat is limited to 1 message / 10 s, so send one stimulus, then wait (4-8 s)
      const before = c.chatCount;
      await c.page.fill("#chat input", "fresh bread from the bakery and a happy walk in the park");
      await c.page.keyboard.press("Enter");
      await c.waitFor(() => c.chatCount > before, 10000, "the chat message to come back");
      await c.waitFor(() => c.replays > 0, 30000, "a replay event (déjà vu)");
      await c.settle(1000);
      return { stage: c.stage, replays: c.replays };
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
    check(r, ck) { ck("no horizontal page scroll", r.scrollWidth <= r.clientWidth + 1, `${r.scrollWidth} vs ${r.clientWidth}`); },
  },
};

// ---------------------------------------------------------------- one scenario run
async function runOnce(name, sc, browser) {
  const checks = [];
  const ck = (what, ok, detail = "") => checks.push({ what, ok: !!ok, detail: String(detail) });
  const server = await startServer(sc.serverArgs || []);
  let ctx = null;
  try {
    const mobile = !!sc.mobile;
    ctx = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
      deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
    const page = await ctx.newPage();
    const errors = [];
    page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", e => errors.push("pageerror: " + e.message));
    const c = { page, life: null, market: null, stage: null, clock: null, replays: 0, chatCount: 0, overrideShot: null, gifFrames: null };
    page.on("websocket", ws => ws.on("framereceived", f => {
      let m; try { m = JSON.parse(typeof f.payload === "string" ? f.payload : f.payload.toString()); } catch { return; }
      if (m.type === "tick") {
        if (m.life) c.life = m.life;
        if (m.market != null) c.market = m.market;
        if (m.sleep) { c.stage = m.sleep.stage; c.clock = m.sleep.clock; }
        for (const ev of m.events || []) if (ev.type === "replay" && ev.text) c.replays++;
      } else if (m.type === "chat") c.chatCount++;
    }));
    c.settle = ms => page.waitForTimeout(ms);
    c.waitFor = async (fn, ms, what) => {
      const t0 = Date.now();
      while (!fn()) { if (Date.now() - t0 > ms) throw new Error(`timed out after ${ms / 1000}s waiting for: ${what}`); await sleep(100); }
    };

    await page.goto(`http://127.0.0.1:${server.port}${sc.path || "/"}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__sub01 && window.__sub01.ready === true, null, { timeout: 90000 })
      .catch(() => { throw new Error("window.__sub01.ready never became true within 90 s"); });
    ck("page ready (window.__sub01.ready)", true);

    const extra = await sc.run(c);
    const png = c.overrideShot || await page.screenshot({ type: "png" });

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
    const rect = await page.evaluate(() => { const r = (document.querySelector("#scene canvas") || document.querySelector("canvas"))?.getBoundingClientRect(); return r ? [r.left, r.top, r.right, r.bottom] : null; });
    let px = null;
    if (!rect) ck("3D canvas present", false, "no canvas element");
    else {
      px = pixelStats(decode(png), rect);
      ck("canvas is not blank / uniform", px.std > 4 && px.colours >= 8, `std=${px.std} colours=${px.colours} mean=${px.mean}`);
      ck("canvas is not almost black", px.mean > 2 || px.brightShare > 0.002, `mean=${px.mean} brightShare=${px.brightShare}`);
    }
    ck("no console errors", errors.length === 0, errors.slice(0, 3).join(" || "));
    ck("websocket connected", sub && sub.connected === true, `connected=${sub?.connected}`);
    if (sc.check) sc.check(extra, ck);
    if (!flag("allow-stubs")) {
      const stubs = stubModules().filter(m => (sc.needs || []).includes(m.split(" ")[0]));
      ck("scenario modules are real implementations (not STUB files)", stubs.length === 0,
        `still a STUB in this checkout: ${stubs.join(", ")} (merge that stream, or pass --allow-stubs)`);
    }

    mkdirSync(OUT, { recursive: true });
    const file = path.join(OUT, `${name}.${EXT}`);
    if (FORMAT === "jpeg") {
      // re-encode via the browser-free path is not available: take a fresh JPEG only for non-walk shots
      writeFileSync(file, c.overrideShot ? png : await page.screenshot({ type: "jpeg", quality: 82 }));
    } else writeFileSync(file, png);

    if (name === "walk" && WANT_GIF && c.gifFrames?.length) await writeGif(c.gifFrames, path.join(OUT, "walk.gif"), ck);
    return { extra, checks, metrics: { fps: sub?.fps ?? null, drawCalls: sub?.drawCalls ?? null, triangles: sub?.triangles ?? null,
      quality: sub?.quality ?? null, view: sub?.view ?? null, districts: sub?.districts ?? null, fibres: sub?.fibres ?? null, pixels: px },
      screenshot: path.relative(ROOT, file), consoleErrors: errors };
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
  for (const buf of frames) {
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
    enc.writeFrame(applyPalette(rgba, palette), w, h, { palette, delay: 120 });
  }
  enc.finish();
  writeFileSync(file, Buffer.from(enc.bytes()));
  ck("walk.gif written", true, `${frames.length} frames, ${W}x${H}, ${(enc.bytes().length / 1e6).toFixed(1)} MB`);
}

async function runScenario(name, browser) {
  const sc = SCENARIOS[name];
  const t0 = Date.now();
  const tries = sc.retries || 1;
  let res = null, err = null;
  for (let a = 1; a <= tries; a++) {
    err = null;
    let timer;
    try {
      res = await Promise.race([runOnce(name, sc, browser),
        new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(`scenario timeout ${SCENARIO_TIMEOUT_MS / 1000}s`)), SCENARIO_TIMEOUT_MS); })]);
      break;
    } catch (e) { err = e; if (!e.retry) break; log(`  [${name}] attempt ${a}/${tries}: ${e.message} - retrying with a fresh server`); }
    finally { clearTimeout(timer); }
  }
  const secs = +((Date.now() - t0) / 1000).toFixed(1);
  if (err || !res) {
    return { scenario: name, description: sc.desc, pass: false, seconds: secs, error: String(err?.message || err), checks: [] };
  }
  return { scenario: name, description: sc.desc, pass: res.checks.every(c => c.ok), seconds: secs, ...res };
}

// ---------------------------------------------------------------- main
async function main() {
  if (!playwright) { console.error("playwright not found: install it in tests/e2e (npm i playwright) or use /home/user/wt/_tools"); process.exit(2); }
  if (!pngjs) { console.error("pngjs not found: cd tests/e2e && npm install"); process.exit(2); }
  const only = opt("only", "").split(",").filter(Boolean);
  const names = only.length ? only : Object.keys(SCENARIOS);
  for (const n of names) if (!SCENARIOS[n]) { console.error(`unknown scenario '${n}' (have: ${Object.keys(SCENARIOS).join(", ")})`); process.exit(2); }
  mkdirSync(OUT, { recursive: true });
  const browser = await playwright.chromium.launch({ executablePath: CHROME,
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
