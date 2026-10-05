// node room_shots.mjs <outdir> <tag> [boy.glb]  — the real room page (web/room.html, ?debug&nolive) in headless Chromium at
// 1280x800 and 390x844, day (hour=14) and night (hour=21), with the given boy.glb served in place of web/room/boy.glb.
// Software WebGL (SwiftShader): the frames take seconds each; the page is given time to settle before each shot.
import { chromium } from "playwright";
import http from "http"; import fs from "fs"; import path from "path";
const [outDir, tag, boyGlb] = process.argv.slice(2);
const WEB = path.resolve(process.cwd(), "../../../web");
const types = {".html": "text/html", ".js": "text/javascript", ".glb": "model/gltf-binary", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml"};
const srv = http.createServer((req, res) => {
  let u = decodeURIComponent(req.url.split("?")[0]); if (u === "/") u = "/room.html";
  if (u.startsWith("/api/")) { res.writeHead(200, {"content-type": "application/json"}); return res.end("{}"); }
  let f = path.join(WEB, u); if (u === "/room/boy.glb" && boyGlb) f = path.resolve(boyGlb);
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, {"content-type": types[path.extname(f)] || "application/octet-stream", "cache-control": "no-cache"}); fs.createReadStream(f).pipe(res);
});
await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
fs.mkdirSync(outDir, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROME_BIN || "/opt/pw-browsers/chromium", args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
for (const [w, h, label] of [[1280, 800, "1280"], [390, 844, "390"]]) for (const [hour, when] of [[14, "day"], [21, "night"]]) {
  const page = await browser.newPage({viewport: {width: w, height: h}, deviceScaleFactor: 1});
  // the page's three.js comes from a CDN; headless Chromium here cannot verify the sandbox proxy's certificate, so serve the same version locally
  await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, route => route.abort());
  // Leaflet (the map card) comes from unpkg: a local copy in vendor/ (curl it once: leaflet@1.9.4/dist/leaflet.js and .css)
  await page.route(/unpkg\.com\/leaflet@1\.9\.4\/dist\/(leaflet\.(js|css))$/, route => { const f = path.resolve("vendor", route.request().url().match(/(leaflet\.(js|css))$/)[1]);
    if (!fs.existsSync(f)) return route.abort(); route.fulfill({path: f, contentType: f.endsWith(".css") ? "text/css" : "text/javascript"}); });
await page.route(/cdn\.jsdelivr\.net\/npm\/three@0\.169\.0\/(.*)$/, route => { const rel = route.request().url().match(/three@0\.169\.0\/(.*)$/)[1].split("?")[0];
    const f = path.join(path.resolve("node_modules/three"), rel); if (!fs.existsSync(f)) return route.abort(); route.fulfill({path: f, contentType: "text/javascript"}); });
    page.on("pageerror", e => console.log("PAGEERROR", e.message));
  await page.goto(`http://127.0.0.1:${port}/room.html?debug&nolive&hour=${hour}`, {waitUntil: "load"});
  await page.waitForFunction(() => window.boy && window.room && Object.keys(window.actions || {}).length >= 5, null, {timeout: 180000}).catch(() => console.log("timeout waiting for the room"));
  // let the lighting settle and the character get into his idle, then one more frame
  await page.evaluate(() => { try { window.settle && window.settle(); for (let i = 0; i < 40; i++) window.sim && window.sim(0.1); } catch (e) { console.log(String(e)); } });
  await page.waitForTimeout(2500);
  const out = path.join(outDir, `room_${label}_${when}_${tag}.png`); await page.screenshot({path: out, timeout: 240000}); console.log("wrote", out); await page.close();
}
await browser.close(); srv.close();
