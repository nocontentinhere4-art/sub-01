// Renders preview.html headless (software GL is enough) and writes hair_sheet.png, hair_mh.glb and the textures
// (hair_atlas.png, hair_data.png, hair_scalp.png; all also embedded in the GLB).
//   (cd dir-with-playwright-core && node .../render.mjs <head.json> <three package dir> <out dir> [chromium executable])
// head.json comes from extract_head.py; three must be 0.169.0, as room.html uses.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const { chromium } = createRequire(path.join(process.cwd(), "x.js"))("playwright-core");   // installed where it is run from
const here = path.dirname(new URL(import.meta.url).pathname);
const [headJson, threeDir, outDir, exe = process.env.CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"] = process.argv.slice(2);
const TYPES = {".html": "text/html", ".js": "text/javascript", ".json": "application/json"};
const server = http.createServer((q, r) => {
  const u = decodeURIComponent(q.url.split("?")[0]);
  const f = u === "/head.json" ? headJson : u.startsWith("/three/") ? path.join(threeDir, u.slice(7)) : path.join(here, u);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; }
    r.writeHead(200, {"content-type": TYPES[path.extname(f)] || "application/octet-stream"}); r.end(d); });
}).listen(0);
const port = server.address().port;
const browser = await chromium.launch({executablePath: exe, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage();
page.on("console", m => console.log("[page]", m.text()));
page.on("pageerror", e => { console.log("[error]", e.message); process.exit(1); });
await page.goto(`http://127.0.0.1:${port}/preview.html`, {waitUntil: "commit"});
await page.waitForFunction(() => window.OUT, null, {timeout: 600000, polling: 1000});
const out = await page.evaluate(() => window.OUT);
fs.mkdirSync(outDir, {recursive: true});
fs.writeFileSync(path.join(outDir, "hair_sheet.png"), Buffer.from(out.sheet, "base64"));
fs.writeFileSync(path.join(outDir, "hair_mh.glb"), Buffer.from(out.glb, "base64"));
fs.writeFileSync(path.join(outDir, "hair_atlas.png"), Buffer.from(out.atlas, "base64"));
fs.writeFileSync(path.join(outDir, "hair_data.png"), Buffer.from(out.data, "base64"));
fs.writeFileSync(path.join(outDir, "hair_scalp.png"), Buffer.from(out.scalp, "base64"));
console.log(JSON.stringify(out.stats));
await browser.close(); server.close();
