// node mx.mjs <worktree> <out>
import fs from "node:fs"; import http from "node:http"; import path from "node:path";
import { chromium } from "/home/user/sub-01/room_build/node_modules/playwright-core/index.mjs";
const [ROOT, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, {recursive: true});
const HERE = path.dirname(new URL(import.meta.url).pathname);
const T = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".glb": "model/gltf-binary", ".wasm": "application/wasm"};
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split("?")[0]); const f = u.startsWith("/__rv/") ? path.join(HERE, u.slice(6)) : path.join(ROOT, u);
  fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); return r.end(); } r.writeHead(200, {"content-type": T[path.extname(f)] || "application/octet-stream"}); r.end(b); }); });
await new Promise(ok => srv.listen(0, ok));
const b = await chromium.launch({executablePath: "/opt/pw-browsers/chromium", args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]});
const p = await b.newPage({viewport: {width: 500, height: 500}}); p.on("console", m => { if (m.type() === "error") console.log("page:", m.text()); });
await p.goto(`http://localhost:${srv.address().port}/__rv/mx.html`); await p.waitForFunction(() => window.READY);
const info = await p.evaluate(() => MX.load("/web/room/char_mixamo.glb")); console.log(JSON.stringify(info.meshes), info.names.slice(0,12).join(","));
const shot = async (name, focus, dir, r) => { const d = await p.evaluate(a => MX.shot(...a), [focus, dir, r]); fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(d.split(",")[1], "base64")); };
const POSES = {
  rest: [],
  armsdown: [["LeftArm", [0, 0, 1], -63], ["RightArm", [0, 0, 1], 63]],
  // typing: arms down ~50, forward 35, elbows bent 80 (forearm forward)
  typing: [["LeftArm", [0, 0, 1], -75], ["RightArm", [0, 0, 1], 75], ["LeftArm", [1, 0, 0], -25], ["RightArm", [1, 0, 0], -25], ["LeftForeArm", [1, 0, 0], -85], ["RightForeArm", [1, 0, 0], -85], ["LeftForeArm", [0, 1, 0], -35], ["RightForeArm", [0, 1, 0], 35]],
  armsup: [["LeftArm", [0, 0, 1], 40], ["RightArm", [0, 0, 1], -40]],
  seated: [["LeftArm", [0, 0, 1], -63], ["RightArm", [0, 0, 1], 63], ["LeftUpLeg", [1, 0, 0], -90], ["RightUpLeg", [1, 0, 0], -90], ["LeftLeg", [1, 0, 0], 90], ["RightLeg", [1, 0, 0], 90]],
};
const ax = n => { const m = {Neck: "neck"}; n = m[n] || n; return info.names.find(x => x.replace(/^mixamorig\d*:?/, "") === n) || n; };
for (const [k, ops] of Object.entries(POSES)) {
  await p.evaluate(() => MX.rest());
  for (const [n, a, d] of ops) await p.evaluate(x => MX.rot(...x), [ax(n), a, d]);
  await shot(`${k}_front`, null, [0, 0.1, 1], 2.6); await shot(`${k}_side`, null, [1, 0.1, 0], 2.6);
  for (const s of ["Left", "Right"]) { const sx = s === "Left" ? 1 : -1;
    await shot(`${k}_${s}armpit_front`, ax(`${s}Arm`), [0.3 * sx, -0.2, 1], 0.45);
    await shot(`${k}_${s}armpit_under`, ax(`${s}Arm`), [0.8 * sx, -0.6, 0.1], 0.45);
    await shot(`${k}_${s}elbow`, ax(`${s}ForeArm`), [1.0 * sx, 0.2, -0.3], 0.5); }
  await shot(`${k}_waist_front`, ax("Spine02"), [0, 0, 1], 1.0); await shot(`${k}_waist_34`, ax("Spine02"), [0.7, 0, 0.7], 1.0);
  await shot(`${k}_neck_back`, ax("Neck"), [0, 0.2, -1], 0.4); await shot(`${k}_feet`, ax("LeftFoot"), [-0.5, 0.3, 1], 0.7);
  if (k === "seated") { await shot(`${k}_knees`, ax("LeftLeg"), [0.6, 0.3, 1], 0.6); await shot(`${k}_hips_back`, ax("Hips"), [0.4, 0.1, -1], 0.8); }
}
await b.close(); srv.close(); console.log("done");
