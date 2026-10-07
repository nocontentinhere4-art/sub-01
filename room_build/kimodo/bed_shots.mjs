// node bed_shots.mjs <port> <activity> <out.png> [times s, comma] [views: page,side,head,foot]
// The room (room.html?debug) with him doing <activity> (sleep / listen_music), settled on the bed, then one row per time:
// the page's own camera (pagez: from where it stands, zoomed onto the bed) and fixed cameras beside the bed (side: from the room, level with him; head: by the pillow; foot:
// from the foot end), tiled into one PNG (rows = times, columns = views). LIFE noDuvet: 1 hides the duvet (to see him under it); turn: 1 starts the turn onto his side (t 0 = its first frame). LIFE='{"music":{...}}' as in contact_pass.mjs.
import {chromium} from "playwright-core"; import fs from "fs"; import {execSync} from "child_process"; import path from "path";
const [port, activity = "sleep", out = "bed.png", times = "0,1,2", views = "page,side,head"] = process.argv.slice(2);
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const W = +(process.env.W || 560), H = +(process.env.H || 400);
const p = await b.newPage({viewport: {width: W, height: H}});
const cdn = path.join(process.env.CDN_CACHE || "/tmp", "cdn_cache"); fs.mkdirSync(cdn, {recursive: true});
await p.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => { const u = r.request().url(), f = path.join(cdn, u.replace(/[^a-z0-9.]+/gi, "_"));
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`); await r.fulfill({status: 200, contentType: u.endsWith(".css") ? "text/css" : "application/javascript", body: fs.readFileSync(f)}); });
p.on("pageerror", e => console.log("pageerror", e.message));
const hour = process.env.HOUR || (activity === "sleep" ? 23 : 15);
await p.goto(`http://localhost:${port}/room.html?debug&nolive${process.env.QS || ""}&hour=${hour}`);
await p.waitForFunction(() => window.boy && window.mh && window.mh.ready && window.roomDbg, null, {timeout: 300000});
await p.evaluate(([a, X]) => { window.FREEZE = true; window.NODUVET = !!X.noDuvet; settle(); live(a, {activity: a, ...X});
  let t = 0, still = 0; while (t < 120 && still < 1) { animate_(1 / 30); t += 1 / 30; still = pose().step || pose().at !== "bedlie" ? 0 : still + 1 / 30; }
  for (let i = 0; i < 90; i++) animate_(1 / 30);
  if (X.turn) { mh.sleepTurn(); for (let i = 0; i < 90 && !mh.turning; i++) animate_(1 / 30); }   // (the turn starts at the loop's wrap)
  window._t0 = 0; }, [activity, JSON.parse(process.env.LIFE || "{}")]);
const T = times.split(",").map(Number), VS = views.split(","), shots = [];
const CAM = {side: [[-0.85, 1.75, -0.35], [-0.95, 0.80, 0.85]], head: [[-1.55, 1.35, 0.05], [-1.25, 0.82, 0.88]], foot: [[0.75, 1.25, 0.90], [-0.9, 0.85, 0.88]],
  close: [[-1.05, 1.10, 0.20], [-1.50, 0.86, 0.86]], level: [[-0.95, 0.90, -0.30], [-0.95, 0.86, 0.88]], hands: [[-0.75, 1.30, 0.55], [-1.05, 0.90, 0.90]], face: [[-1.25, 1.15, 0.45], [-1.50, 0.95, 0.90]], face2: [[-1.25, 1.15, 1.35], [-1.50, 0.95, 0.90]], profile: [[-0.95, 0.95, -7.0], [-0.95, 0.95, 0.88]], top: [[-0.95, 2.6, 0.89], [-0.95, 0.8, 0.88]]};
let now = 0;
for (const t of T) {
  await p.evaluate(n => { for (let i = 0; i < n; i++) animate_(1 / 30); }, Math.round((t - now) * 30)); now = t;
  for (const v of VS) {
    const png = await p.evaluate(([v, C]) => { const cam = camera, keep = [cam.position.clone(), controls.target.clone(), cam.fov];
      if (v === "pagez") { cam.fov = keep[2] / 3.2; controls.target.set(-0.95, 0.85, 0.85); cam.updateProjectionMatrix(); cam.lookAt(controls.target); window.NOCLEAR = true; }
      else if (v === "profile") {                                  // straight from the side, nearly flat (fov 9), what stands between hidden
        cam.position.set(...C[v][0]); controls.target.set(...C[v][1]); cam.fov = 9; cam.updateProjectionMatrix(); cam.lookAt(controls.target); window.NOCLEAR = true;
        window._hid = []; const bb = new THREE.Box3(); scene.traverse(o => { if (o.isMesh && o.visible && !boy.getObjectById(o.id)) { bb.setFromObject(o); if (bb.max.z < 0.30 || (bb.min.z < 0.2 && bb.max.y > 1.6)) { o.visible = false; window._hid.push(o); } } }); }
      else if (v !== "page") { cam.position.set(...C[v][0]); controls.target.set(...C[v][1]); cam.fov = 50; cam.updateProjectionMatrix(); cam.lookAt(controls.target); window.NOCLEAR = true; }
      sim(0, 0); if (window.NODUVET) scene.traverse(o => { if (o.name === "duvet_over" || (o.material && o.material.name === "duvet")) o.visible = false; }); cam.lookAt(controls.target); renderer.render(scene, cam); const u = renderer.domElement.toDataURL("image/png"); (window._hid || []).forEach(o => { o.visible = true; }); window._hid = null;
      cam.position.copy(keep[0]); controls.target.copy(keep[1]); cam.fov = keep[2]; cam.updateProjectionMatrix(); window.NOCLEAR = false; return u; }, [v, CAM]);
    const f = `${out}.${t}.${v}.png`; fs.writeFileSync(f, Buffer.from(png.split(",")[1], "base64")); shots.push([t, v, f]); } }
fs.writeFileSync(out + ".json", JSON.stringify(shots));
console.log(JSON.stringify(await p.evaluate(() => pose()))); await b.close();
