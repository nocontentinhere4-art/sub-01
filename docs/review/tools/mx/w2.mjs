// node w2.mjs <worktree> [outdir]: torso vertices dragged by the arms, poses by absolute arm directions; shots if outdir
import fs from "node:fs"; import http from "node:http"; import path from "node:path";
import { chromium } from "/home/user/sub-01/room_build/node_modules/playwright-core/index.mjs";
const [ROOT, OUT] = process.argv.slice(2); const HERE = path.dirname(new URL(import.meta.url).pathname);
const T = {".html": "text/html", ".js": "text/javascript", ".glb": "model/gltf-binary"};
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split("?")[0]); const f = u.startsWith("/__rv/") ? path.join(HERE, u.slice(6)) : path.join(ROOT, u);
  fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); return r.end(); } r.writeHead(200, {"content-type": T[path.extname(f)] || "application/octet-stream"}); r.end(b); }); });
await new Promise(ok => srv.listen(0, ok));
const b = await chromium.launch({executablePath: "/opt/pw-browsers/chromium", args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]});
const p = await b.newPage({viewport: {width: 500, height: 500}}); await p.goto(`http://localhost:${srv.address().port}/__rv/mx.html`); await p.waitForFunction(() => window.READY);
await p.evaluate(() => MX.load("/web/room/char_mixamo.glb"));
const res = await p.evaluate(() => { MX.pose("down"); const ref = MX.torso(); const o = {};
  for (const k of ["side", "typing", "T", "up"]) { MX.pose(k); o[k] = MX.moved(ref); } return o; });
console.log(JSON.stringify(res));
if (OUT) { fs.mkdirSync(OUT, {recursive: true});
  const shot = async (name, focus, dir, r) => { const d = await p.evaluate(a => MX.shot(...a), [focus, dir, r]); fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(d.split(",")[1], "base64")); };
  for (const k of ["down", "side", "typing", "T", "up"]) { await p.evaluate(k => MX.pose(k), k);
    await shot(`${k}_front`, null, [0, 0.1, 1], 2.6); await shot(`${k}_waist`, "Spine02", [0, 0, 1], 1.0); await shot(`${k}_waist34`, "Spine02", [0.7, 0, 0.7], 1.0);
    await shot(`${k}_Larmpit`, "LeftArm", [0.8, -0.5, 0.4], 0.45); await shot(`${k}_Rarmpit`, "RightArm", [-0.8, -0.5, 0.4], 0.45); } }
await b.close(); srv.close();
