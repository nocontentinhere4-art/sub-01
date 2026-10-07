// node standing_selfcontact.mjs <character.glb> <clips dir> <out.json> [Clip ...] : his own body against itself over
// every frame of each baked clip (<clips dir>/<Clip>.glb, standing_rebake.sh's), on the character played through
// char_mixamo.js (rig/autorig/qa.html, QA.selfContact): hands in thighs, each arm in the torso, leg in leg, hand in
// hand; a vertex is inside when it is behind the nearest vertex of the other part by more than 5 mm (its normal). The
// same pairs in the T-pose rest and with the arms down are the mesh's own baseline (the baggy sleeves on the hoodie).
import fs from "node:fs"; import http from "node:http"; import path from "node:path";
import { chromium } from "playwright-core";
const [CHAR, CLIPS, OUT, ...names] = process.argv.slice(2);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const CL = names.length ? names : Object.keys(JSON.parse(fs.readFileSync(path.join(HERE, "standing_clips.json"))).clips);
const ROOT = path.resolve(HERE, "../..");
const files = {"/char.glb": path.resolve(CHAR)}; for (const c of CL) files[`/clips/${c}.glb`] = path.resolve(CLIPS, `${c}.glb`);
const TYPES = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".glb": "model/gltf-binary", ".wasm": "application/wasm", ".json": "application/json"};
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split("?")[0]); const f = files[u] || path.join(ROOT, u);
  if (!f.startsWith(ROOT) && !files[u]) { r.writeHead(403); return r.end(); }
  fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); return r.end(); } r.writeHead(200, {"content-type": TYPES[path.extname(f)] || "application/octet-stream"}); r.end(b); }); });
await new Promise(ok => srv.listen(0, ok)); const port = srv.address().port;
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const p = await b.newPage(); p.on("console", m => { if (m.type() === "error") console.log("page:", m.text()); });
await p.goto(`http://localhost:${port}/room_build/rig/autorig/qa.html`); await p.waitForFunction(() => window.QA_READY, null, {timeout: 60000});
await p.evaluate(c => QA.load("/char.glb", Object.fromEntries(c.map(k => [k, `/clips/${k}.glb`]))), CL);
const res = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT)) : {};
for (const c of CL) { const t0 = Date.now(); res[c] = await p.evaluate(k => QA.selfContact(k), c);
  console.log(c, `${((Date.now() - t0) / 1000).toFixed(0)} s`, JSON.stringify(res[c].inside)); fs.writeFileSync(OUT, JSON.stringify(res, null, 1)); }
await b.close(); srv.close();
