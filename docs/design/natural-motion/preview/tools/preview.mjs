// node preview.mjs <port> <view: default|close> <outdir> : the frames of tools/timeline.json for one view, 1280 x 720
// framing rendered at half resolution (640 x 360), 30 fps, by stepping the page's own clock (?debug&nolive, its rAF loop
// frozen; animate(1/30) per frame, the motion layer included). Every idle is made to play in turn with the page's
// variant(); the page's own scheduler is held off so nothing else starts in between. A variant a page doesn't have (main)
// plays nothing: what main does then is what it shows. START=n resumes a run: the page is stepped to frame n (the same
// simulation; rendering changes nothing in it) and drawn from there.
import { chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";
const [port, view, out] = process.argv.slice(2);
const START = +(process.env.START || 0);              // resume: the frames before this one are already on disk
const TL = JSON.parse(fs.readFileSync(new URL("./timeline.json", import.meta.url)));
fs.mkdirSync(out, {recursive:true});
const browser = await chromium.launch({executablePath:process.env.SUB01_CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args:["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport:{width:1280, height:720}});
fs.mkdirSync("cdn", {recursive:true});
await page.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => { const u = r.request().url(), f = "cdn/" + u.replace(/[^a-z0-9.]+/gi, "_");
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`); await r.fulfill({status:200, contentType:"application/javascript", body:fs.readFileSync(f)}); });
page.on("pageerror", e => console.log("pageerror", e.message));
await page.goto(`http://localhost:${port}/room.html?debug&nolive&hour=${process.env.HOUR || 14}`, {timeout:300000});
await page.waitForFunction(() => window.boy && window.actions && window.actions.sleep && window.motion && window.motion.ready, null, {timeout:300000});
await page.evaluate(() => { window.FREEZE = true; document.querySelectorAll("#top,#side,#corner,#dock,#vignette,#away").forEach(e => e.style.display = "none"); settle();
  scene.traverse(o => { if (o.isMesh && o.geometry.type === "SphereGeometry" && o.material.color && o.material.color.getHex() === 0xff00ff) o.visible = false; });
  setSeed(63); renderer.setPixelRatio(0.5); renderer.setSize(1280, 720); window._home = [camera.position.clone(), controls.target.clone()]; });
let place = null, n = 0;
for (const [where, label, variant, secs] of TL.segments) {
  if (where !== place) {                                // a new place: set it up and let him settle there (not recorded)
    place = where; const P = TL.places[where];
    await page.evaluate(([setup, settle, cam]) => { eval(setup);
      for (let i = 0; i < settle * 30; i++) { IV.next = 1e9; if ("big" in IV) IV.big = 1e9; animate_(1 / 30); }
      if (cam) { camera.position.set(...cam.pos); controls.target.set(...cam.target); } else { camera.position.copy(_home[0]); controls.target.copy(_home[1]); }
      controls.update(); }, [P.setup, P.settle, view === "close" ? P.close : null]);
  }
  const frames = Math.round(secs * TL.fps);
  await page.evaluate(([v, d]) => { if (v) { variant(v, d); IV.cur.s = 0.5; } }, [variant, secs]);
  for (let i = 0; i < frames; i++, n++) {
    if (n < START) { await page.evaluate(() => { IV.next = 1e9; if ("big" in IV) IV.big = 1e9; animate_(1 / 30); }); continue; }   // (resuming: stepped, not drawn)
    const url = await page.evaluate(() => {
      IV.next = 1e9; if ("big" in IV) IV.big = 1e9;
      sim(1 / 30); return renderer.domElement.toDataURL("image/jpeg", 0.9);   // (one step of him, the light, the shadows, a render)
    });
    fs.writeFileSync(`${out}/f${String(n).padStart(5, "0")}.jpg`, Buffer.from(url.split(",")[1], "base64"));
  }
  await page.evaluate(() => { if (IV.cur) IV.cur.t = IV.cur.d; });   // ends on the next frame, the page's own way (the bottle put back)
  console.log(`${where} ${label || "-"} ${variant || ""}: ${frames} frames (${n} total)`);
}
await browser.close();
