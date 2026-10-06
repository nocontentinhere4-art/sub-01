// node stills.mjs <cfg.json> <out.png> <t1,t2,..> '<cams json>' [w h] [hideBody]: a grid of stills (rows = times, cols = cams)
import fs from "node:fs"; import path from "node:path"; import http from "node:http"; import { execFileSync } from "node:child_process"; import { chromium } from "playwright-core";
const [,, CFG, OUT, TS, CAMS, W0, H0] = process.argv; const cfg = JSON.parse(fs.readFileSync(CFG)); const ts = TS.split(",").map(Number), cams = JSON.parse(CAMS);
const W = +(W0 || 480), H = +(H0 || 360); const SITE = new URL("./site/", import.meta.url).pathname;
const srv = http.createServer((q, r) => { const p = path.join(SITE, decodeURIComponent(q.url.split("?")[0])); fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, {"Content-Type": p.endsWith(".html") ? "text/html" : p.endsWith(".js") ? "text/javascript" : "application/octet-stream"}); r.end(d); }); }).listen(0);
const GPU = process.env.GPU_ARGS ? process.env.GPU_ARGS.split(",") : null;
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args: GPU || ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]});
const pg = await b.newPage({viewport: {width: W, height: H}}); await pg.goto(`http://127.0.0.1:${srv.address().port}/scene.html?w=${W}&h=${H}`); await pg.waitForFunction(() => window.ready);
await pg.evaluate(c => window.setup(c), cfg); const tmp = fs.mkdtempSync(path.join(path.dirname(OUT), ".st_")); const files = [];
for (const t of ts) for (const c of cams) { await pg.evaluate(([t, c]) => { window.pose(t); window.shot(c); window.shot(c); }, [t, c]);
  const f = path.join(tmp, `${files.length}.png`); fs.writeFileSync(f, Buffer.from((await pg.evaluate(() => document.querySelector("canvas").toDataURL("image/png"))).split(",")[1], "base64")); files.push(f); }
await b.close(); srv.close();
const n = cams.length, lay = files.map((_, i) => `${(i % n) * W}_${Math.floor(i / n) * H}`).join("|");
execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...files.flatMap(f => ["-i", f]), "-filter_complex", files.length > 1 ? `xstack=inputs=${files.length}:layout=${lay}` : "null", "-frames:v", "1", OUT]);
fs.rmSync(tmp, {recursive: true});
