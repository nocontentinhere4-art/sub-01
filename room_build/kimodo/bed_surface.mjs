// node bed_surface.mjs <port> <out.json> : the bed's rest surface (the room's "sheet" mesh: the mattress top and the pillow,
// undeformed) as a height map in the room's frame, from the page served with ?debug. Input to kimodo_g12/bed_clip.py.
import {chromium} from "playwright-core"; import fs from "fs"; import {execSync} from "child_process"; import path from "path";
const [port, out] = process.argv.slice(2);
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const p = await b.newPage({viewport: {width: 320, height: 240}});
const cdn = path.join(process.env.CDN_CACHE || "/tmp", "cdn_cache"); fs.mkdirSync(cdn, {recursive: true});
await p.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => { const u = r.request().url(), f = path.join(cdn, u.replace(/[^a-z0-9.]+/gi, "_"));
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`); await r.fulfill({status: 200, contentType: "application/javascript", body: fs.readFileSync(f)}); });
await p.goto(`http://localhost:${port}/room.html?debug&nolive&hour=15`);
await p.waitForFunction(() => window.room && window.roomDbg, null, {timeout: 300000});
const r = await p.evaluate(() => { let sheet = null; room.traverse(o => { if (o.isMesh && o.material && o.material.name === "sheet" && !sheet) sheet = o; });
  sheet.updateMatrixWorld(true); const rc = new THREE.Raycaster(), DN = new THREE.Vector3(0, -1, 0), G = {x0: -1.92, z0: 0.22, c: 0.01, nx: 200, nz: 132, h: []};
  for (let i = 0; i < G.nx; i++) for (let k = 0; k < G.nz; k++) { rc.set(new THREE.Vector3(G.x0 + (i + 0.5) * G.c, 2, G.z0 + (k + 0.5) * G.c), DN);
    const h = rc.intersectObject(sheet, false)[0]; G.h.push(h ? +h.point.y.toFixed(4) : -1); }
  return G; });
r.page = {bedTop: 0.805, quiltTop: 0.834, mattressEnd: 0.05, box: [-1.90, 0.05, 0.25, 1.50]};   // (boy_mh.js BED.top / env.quiltTop: where the page puts his lowest skin)
fs.writeFileSync(out, JSON.stringify(r)); console.log("bed surface", r.nx, "x", r.nz, "max", Math.max(...r.h)); await b.close();
