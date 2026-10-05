// node render.mjs <cfg.json> <out_dir> [--qa-only] [--fps 30]
// Renders one clip in the room from the cfg's two cameras (headless Chromium, software WebGL) into <out>/<name>.mp4
// (the two views side by side) and runs the penetration QA into <out>/<name>_qa.json.
import fs from "node:fs"; import path from "node:path"; import http from "node:http"; import { execFileSync } from "node:child_process";
import { chromium } from "playwright-core";
const [,, CFG, OUT, ...rest] = process.argv;
const cfg = JSON.parse(fs.readFileSync(CFG)); const qaOnly = rest.includes("--qa-only"), noQa = rest.includes("--no-qa");
const fps = +(rest[rest.indexOf("--fps") + 1] || 0) || 30;
const SITE = new URL("./scene/", import.meta.url).pathname;
const types = {".html": "text/html", ".js": "text/javascript", ".glb": "model/gltf-binary", ".json": "application/json", ".webp": "image/webp", ".png": "image/png"};
const srv = http.createServer((q, r) => { const p = path.join(SITE, decodeURIComponent(q.url.split("?")[0])); fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, {"Content-Type": types[path.extname(p)] || "application/octet-stream"}); r.end(d); }); }).listen(0);
const port = srv.address().port;
const W = cfg.w || 800, H = cfg.h || 450;
// software WebGL by default (the sandbox); on a GPU pod CHROME names the browser and GPU_ARGS the flags that put WebGL on the
// NVIDIA card (tools/gpu_preview_job.sh's probe: "--use-gl=angle,--use-angle=gl-egl" on RunPod)
const GPU = process.env.GPU_ARGS ? process.env.GPU_ARGS.split(",").filter(Boolean) : null;
const browser = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: GPU ? ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--disable-gpu-vsync", ...GPU] : ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport: {width: W, height: H}});
page.on("console", m => { if (m.type() === "error" || m.type() === "warning") console.log("page:", m.text().slice(0, 200)); });
page.on("pageerror", e => console.log("pageerror:", e.message));
await page.goto(`http://127.0.0.1:${port}/scene.html?w=${W}&h=${H}`); await page.waitForFunction(() => window.ready);
if (rest.includes("--probe")) { console.log("renderer:", await page.evaluate(() => { const g = document.createElement("canvas").getContext("webgl2"); const e = g.getExtension("WEBGL_debug_renderer_info"); return g.getParameter(e ? e.UNMASKED_RENDERER_WEBGL : g.RENDERER); })); await browser.close(); srv.close(); process.exit(0); }
const {dur} = await page.evaluate(c => window.setup(c), cfg);
fs.mkdirSync(OUT, {recursive: true});
const name = cfg.name;
if (!qaOnly) {
  const tmp = fs.mkdtempSync(path.join(OUT, ".fr_"));
  const n = Math.floor(dur * fps) + 1;
  for (let i = 0; i < n; i++) {
    const t = Math.min(i / fps, dur);
    await page.evaluate(t => window.pose(t), t);
    for (let c = 0; c < cfg.cams.length; c++) {
      await page.evaluate(cam => window.shot(cam), cfg.cams[c]);
      await page.screenshot({path: path.join(tmp, `c${c}_${String(i).padStart(5, "0")}.jpg`), type: "jpeg", quality: 88});
    }
    if (i % 60 === 0) console.log(`${name}: frame ${i}/${n}`);
  }
  const ins = cfg.cams.flatMap((_, c) => ["-framerate", String(fps), "-i", path.join(tmp, `c${c}_%05d.jpg`)]);
  const filt = cfg.cams.length > 1 ? ["-filter_complex", `hstack=inputs=${cfg.cams.length}`] : [];
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...ins, ...filt, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium", "-movflags", "+faststart", path.join(OUT, `${name}.mp4`)]);
  // a contact sheet: 6 frames of camera 0 and 1
  const pick = [0, 0.2, 0.4, 0.6, 0.8, 1].map(u => Math.min(n - 1, Math.round(u * (n - 1))));
  const sh = []; for (const c of cfg.cams.keys()) for (const i of pick) sh.push("-i", path.join(tmp, `c${c}_${String(i).padStart(5, "0")}.jpg`));
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...sh, "-filter_complex", `xstack=inputs=${pick.length * cfg.cams.length}:layout=${cfg.cams.flatMap((_, r) => pick.map((_, c) => `${c ? Array(c).fill("w0").join("+") : "0"}_${r ? Array(r).fill("h0").join("+") : "0"}`)).join("|")},scale=iw/2:-2`, "-q:v", "4", path.join(OUT, `${name}_sheet.jpg`)]);
  fs.rmSync(tmp, {recursive: true});
  console.log(`${name}: ${n} frames -> ${name}.mp4`);
}
if (!noQa) {
  const qa = await page.evaluate(() => window.qa(0.1));
  fs.writeFileSync(path.join(OUT, `${name}_qa.json`), JSON.stringify(qa));
  console.log(`${name} QA:`, JSON.stringify(qa.summary));
}
await browser.close(); srv.close();
