// node idles.mjs <port> <outdir> <mode> [W H]
//   mode strip:<activity>:<secs>:<every>[:cam]  a frame every <every> s of <secs> s of <activity> (cam: default | desk | win | bed)
//   mode each:<activity>:<secs>[:cam]            one frame in the middle of each idle variant he does (the first of each kind)
// Headless Chromium (SwiftShader WebGL); the page in ?debug&nolive, its rAF loop frozen and stepped with the page's own
// animate (the motion layer included). Each frame is labelled with the time and the idle variant playing (IV.cur).
import { chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";

const [port, out, mode, W = "1280", H = "720"] = process.argv.slice(2);
const [kind, activity, secs, every, camName = "default"] = mode.split(":");
fs.mkdirSync(out, {recursive:true});
const browser = await chromium.launch({executablePath:process.env.SUB01_CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args:["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport:{width:+W, height:+H}, ignoreHTTPSErrors:true});
fs.mkdirSync("cdn", {recursive:true});
await page.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => {
  const u = r.request().url(), f = "cdn/" + u.replace(/[^a-z0-9.]+/gi, "_");
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`);
  await r.fulfill({status:200, contentType:u.endsWith(".css") ? "text/css" : "application/javascript", body:fs.readFileSync(f)});
});
page.on("pageerror", e => console.log("pageerror", e.message));
await page.goto(`http://localhost:${port}/room.html?debug&nolive&hour=${process.env.HOUR || 14}`);
await page.waitForFunction(() => window.boy && window.room && window.actions && window.actions.sleep && window.motion && window.motion.ready, null, {timeout:180000});
const CAM = {desk:{pos:[0.45, 1.55, 0.8], target:[-1.1, 0.9, -0.75]}, win:{pos:[-0.35, 1.7, 1.65], target:[-1.6, 1.15, -0.05]},
  bed:{pos:[0.35, 1.55, -0.55], target:[-0.55, 0.95, 0.55]}};
await page.evaluate(([a, cam]) => { window.FREEZE = true; document.querySelectorAll("#top,#side,#corner,#dock,#vignette,#away").forEach(e => e.style.display = "none"); settle();
  scene.traverse(o => { if (o.isMesh && o.geometry.type === "SphereGeometry" && o.material.color && o.material.color.getHex() === 0xff00ff) o.visible = false; });   // ?debug's markers
  if (window.setSeed) setSeed(+(new URLSearchParams(location.search).get("seed") || 63));
  const [name, sub] = a.split("+"); act(name); if (sub) live(sub);
  if (cam) { camera.position.set(...cam.pos); controls.target.set(...cam.target); controls.update(); } sim(0.0001); }, [activity, CAM[camName]]);
const step = s => page.evaluate(s => { let t = 0; while (t < s - 1e-6) { animate_(0.05); t += 0.05; }
  const q = penetration(4), p = pose(); return {bed:q.bed, chair:q.chair, at:p.at, iv:IV.cur ? IV.cur.n : "", u:IV.cur ? IV.cur.t / IV.cur.d : 0}; }, s);
// CLIP=x,y,w,h: a part of the 1280 x 720 frame (the default camera's view of him, cropped; nothing is zoomed)
const CLIP = process.env.CLIP && (([x, y, width, height]) => ({x, y, width, height}))(process.env.CLIP.split(",").map(Number));
const shot = async f => { await page.evaluate(() => { sim(0.0001); return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); });
  await page.screenshot({path:f, timeout:120000, ...(CLIP ? {clip:CLIP} : {})}); };
const frames = [], trace = [];
if (kind === "strip") {
  for (let t = 0, i = 0; t <= +secs + 1e-6; t += +every, i++) {
    const r = i ? await step(+every) : await step(0.05), f = `${out}/f${String(i).padStart(4, "0")}.png`;
    await shot(f); frames.push([f, `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")} ${r.iv || "-"}`]);
    trace.push(`${t.toFixed(0)} ${r.iv || "-"} bed ${r.bed} chair ${r.chair} ${r.at}`);
  }
} else {
  const seen = new Set();
  for (let t = 0; t < +secs; t += 0.25) {
    const r = await step(0.25); trace.push(`${t.toFixed(2)} ${r.iv || "-"} bed ${r.bed} chair ${r.chair} ${r.at}`);
    if (r.iv && !seen.has(r.iv) && r.u > (+process.env.AT || 0.45) && r.u < (+process.env.AT || 0.45) + 0.15) { seen.add(r.iv); const f = `${out}/v_${r.iv}.png`; await shot(f); frames.push([f, `${r.iv} (${t.toFixed(0)} s)`]); }
  }
}
await browser.close();
fs.writeFileSync(`${out}/trace.txt`, trace.join("\n") + "\n");
const lab = frames.map(([f, l]) => `-label '${l}' ${f}`).join(" ");
execSync(`montage ${lab} -tile ${kind === "strip" ? 8 : 4}x -geometry 480x270+3+3 -pointsize 18 -fill '#eee' -background '#111' ${out}/strip.jpg`);
console.log(`${frames.length} frames; max bed ${Math.max(...trace.map(l => +l.split(" bed ")[1].split(" ")[0]))}, chair ${Math.max(...trace.map(l => +l.split(" chair ")[1].split(" ")[0]))}`);
