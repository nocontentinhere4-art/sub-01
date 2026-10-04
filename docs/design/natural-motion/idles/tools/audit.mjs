// node audit.mjs <port> [secs=180] [seed=63] : how static each activity reads from the default camera at 1280 x 720.
// For every activity he is placed (the page's own act()) and stepped by the page's animate (motion layer included) for
// <secs> s; at 10 Hz his head, both hands and chest are projected through the default camera. Per activity:
//   move   mean on-screen speed of those four points (px/s);
//   still  the share of 2 s windows in which none of them moves more than 3 px (he reads as a statue);
//   acts   visible actions per minute: episodes in which a hand or the head is more than 30 px from where it usually
//          is (its median over the run) for at least 1 s (typing, the mouse, breathing and glances stay under that);
//   away   the share of the time he is in such an action.
import { chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";
const [port, secs = "180", seed = "63"] = process.argv.slice(2);
const browser = await chromium.launch({executablePath:process.env.SUB01_CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args:["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport:{width:1280, height:720}, ignoreHTTPSErrors:true});
fs.mkdirSync("cdn", {recursive:true});
await page.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => {
  const u = r.request().url(), f = "cdn/" + u.replace(/[^a-z0-9.]+/gi, "_");
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`);
  await r.fulfill({status:200, contentType:u.endsWith(".css") ? "text/css" : "application/javascript", body:fs.readFileSync(f)});
});
page.on("pageerror", e => console.log("pageerror", e.message));
await page.goto(`http://localhost:${port}/room.html?debug&nolive&hour=${process.env.HOUR || 14}`);
await page.waitForFunction(() => window.boy && window.actions && window.actions.sleep && window.motion && window.motion.ready, null, {timeout:180000});
await page.evaluate(() => { window.FREEZE = true; settle(); });
const CASES = [["research"], ["chat"], ["chart"], ["watch_video"], ["play_chess"], ["eat", {food:1}], ["eat", {bread:2}], ["window"],
  ["phone"], ["order_food"], ["sleep+phone"], ["listen_music"], ["sleep"]];
const rows = [];
for (const [name, x] of CASES) {
  const r = await page.evaluate(([name, x, secs, seed]) => {
    if (window.setSeed) setSeed(seed);
    const [a, sub] = name.split("+"); act(a, x || {}); if (sub) live(sub, x || {});
    sim(0.05, 40);                                                  // settle into the pose (and the camera onto him)
    const W = 1280, H = 720, P = new THREE.Vector3(), names = ["Head", "LeftHand", "RightHand", "Spine02"], tr = names.map(() => []);
    const B = {}; boy.traverse(o => { if (o.isBone && names.includes(o.name)) B[o.name] = o; });
    const n = Math.round(secs * 10);
    for (let i = 0; i < n; i++) { animate_(0.05); animate_(0.05); boy.updateMatrixWorld(true);
      names.forEach((k, j) => { B[k].getWorldPosition(P).project(camera); tr[j].push([(P.x + 1) * W / 2, (1 - P.y) * H / 2]); }); }
    let dist = 0, still = 0, win = 0;
    for (const t of tr) for (let i = 1; i < t.length; i++) dist += Math.hypot(t[i][0] - t[i - 1][0], t[i][1] - t[i - 1][1]);
    for (let s = 0; s + 20 <= n; s += 20) { win++;
      const ext = tr.map(t => { const w = t.slice(s, s + 20), xs = w.map(p => p[0]), ys = w.map(p => p[1]);
        return Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)); });
      if (Math.max(...ext) < 3) still++; }
    const med = a => a.slice().sort((x, y) => x - y)[a.length >> 1];
    const rest = tr.slice(0, 3).map(t => [med(t.map(p => p[0])), med(t.map(p => p[1]))]);
    let acts = 0, away = 0, run = 0;
    for (let i = 0; i < n; i++) {
      const off = tr.slice(0, 3).some((t, j) => Math.hypot(t[i][0] - rest[j][0], t[i][1] - rest[j][1]) > 30);
      if (off) { run++; away++; if (run === 10) acts++; } else run = 0;
    }
    const pen = penetration(4);
    return {move:+(dist / 4 / secs).toFixed(1), still:+(still / win).toFixed(2), acts:+(acts / (secs / 60)).toFixed(1), away:+(away / n).toFixed(2), bed:pen.bed, chair:pen.chair};
  }, [name, x, +secs, +seed]);
  rows.push({name:name + (x ? " " + JSON.stringify(x) : ""), ...r}); console.log(JSON.stringify(rows[rows.length - 1]));
}
await browser.close();
