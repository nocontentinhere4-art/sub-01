// node standing_sheet.mjs <port> <out.jpg> [Clip ...] : G22's render sheet. For each clip (standing_clips.json), the
// page as room.html?debug&char=mixamo&clip=<Clip> serves it (room/standing_preview.js: the Mixamo-rigged character in
// the room, where the preview puts him), three moments (10 %, 50 %, 90 % of the clip) from the front and the side
// (standing_preview.js SP.view: the camera kept inside the room). Needs the page served from web/ on <port>.
import {chromium} from "playwright-core"; import fs from "fs"; import {execSync} from "child_process"; import path from "path"; import sharp from "sharp";
const [port, OUT, ...names] = process.argv.slice(2);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const CL = names.length ? names : Object.keys(JSON.parse(fs.readFileSync(path.join(HERE, "standing_clips.json"))).clips);
const W = 260, H = 330, LB = 24;
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const cdn = path.join(process.env.CDN_CACHE || "/tmp", "cdn_cache"); fs.mkdirSync(cdn, {recursive: true});
const label = txt => Buffer.from(`<svg width="${W}" height="${LB}"><rect width="100%" height="100%" fill="#1d1d22"/><text x="7" y="17" font-family="sans-serif" font-size="13" fill="#eee">${txt}</text></svg>`);
const rows = [];
for (const clip of CL) {
  const p = await b.newPage({viewport: {width: 640, height: 480}});
  await p.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => { const u = r.request().url(), f = path.join(cdn, u.replace(/[^a-z0-9.]+/gi, "_"));
    if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`); await r.fulfill({status: 200, contentType: u.endsWith(".css") ? "text/css" : "application/javascript", body: fs.readFileSync(f)}); });
  p.on("pageerror", e => console.log(clip, "pageerror", e.message));
  await p.goto(`http://localhost:${port}/room.html?debug&nolive&hour=15&char=mixamo&clip=${clip}`);
  await p.waitForFunction(() => window.SP && window.SP.ready, null, {timeout: 300000});
  const dur = await p.evaluate(() => { window.FREEZE = true; settle(); return SP.duration; });
  const tiles = [];
  for (const fr of [0.1, 0.5, 0.9]) for (const view of ["front", "side"]) {
    const t = +(dur * fr).toFixed(2);
    const url = await p.evaluate(([t, view, W, H]) => {
      SP.setTime(t); const v = SP.view(view);
      renderer.setPixelRatio(1); renderer.setSize(W, H, false); camera.aspect = W / H; camera.fov = 52; camera.updateProjectionMatrix();
      camera.position.copy(v.pos); controls.target.copy(v.target); camera.lookAt(v.target);
      sim(0); renderer.render(scene, camera); return renderer.domElement.toDataURL("image/jpeg", 0.9);
    }, [t, view, W, H]);
    tiles.push(await sharp({create: {width: W, height: H + LB, channels: 3, background: "#1d1d22"}})
      .composite([{input: label(`${clip} ${t}s ${view}`), top: 0, left: 0}, {input: Buffer.from(url.split(",")[1], "base64"), top: LB, left: 0}]).jpeg().toBuffer());
  }
  rows.push(tiles); console.log(clip, `${dur.toFixed(2)} s`); await p.close();
}
const sheet = await sharp({create: {width: W * 6, height: (H + LB) * rows.length, channels: 3, background: "#1d1d22"}})
  .composite(rows.flatMap((r, i) => r.map((buf, j) => ({input: buf, top: i * (H + LB), left: j * W})))).jpeg({quality: 80}).toBuffer();
fs.writeFileSync(OUT, sheet); await b.close(); console.log(OUT, `${(sheet.length / 1024).toFixed(0)} KB`);
