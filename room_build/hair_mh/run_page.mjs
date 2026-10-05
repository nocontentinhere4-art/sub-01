// Runs one of this folder's pages headless (software GL is enough) and writes what it returns in window.OUT: each
// key ending in _png as <out dir>/<key>.png, the rest as <out dir>/<page>.json, printed too.
//   (cd dir-with-playwright-core && node .../run_page.mjs "bind_check.html?dt=0.25" <asset dir> <three package dir> <out dir>)
// <asset dir> holds the GLBs the page loads (boy_g2_dressed.glb, hair_mh.glb, the clips); three must be 0.169.0.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const { chromium } = createRequire(path.join(process.cwd(), "x.js"))("playwright-core");
const here = path.dirname(new URL(import.meta.url).pathname);
const [page, assetDir, threeDir, outDir, exe = process.env.CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"] = process.argv.slice(2);
const TYPES = {".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".glb": "model/gltf-binary"};
const server = http.createServer((q, r) => {
  const u = decodeURIComponent(q.url.split("?")[0]);
  let f = u.startsWith("/three/") ? path.join(threeDir, u.slice(7)) : path.join(assetDir, u);
  if (!u.startsWith("/three/") && !fs.existsSync(f)) f = path.join(here, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; }
    r.writeHead(200, {"content-type": TYPES[path.extname(f)] || "application/octet-stream"}); r.end(d); });
}).listen(0);
const browser = await chromium.launch({executablePath: exe, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const p = await browser.newPage();
p.on("console", m => console.log("[page]", m.text()));
p.on("pageerror", e => { console.log("[error]", e.message); process.exit(1); });
await p.goto(`http://127.0.0.1:${server.address().port}/${page}`, {waitUntil: "commit"});
await p.waitForFunction(() => window.OUT, null, {timeout: 3600000, polling: 1000});
const out = await p.evaluate(() => window.OUT);
fs.mkdirSync(outDir, {recursive: true});
for (const k of Object.keys(out)) if (k.endsWith("_png")){ fs.writeFileSync(path.join(outDir, k.slice(0, -4) + ".png"), Buffer.from(out[k], "base64")); delete out[k]; }
fs.writeFileSync(path.join(outDir, page.split("?")[0].replace(/\.html$/, "") + ".json"), JSON.stringify(out, null, 1));
console.log(JSON.stringify(out).slice(0, 2000));
await browser.close(); server.close();
