// node sweep_idles.mjs <port> [seed=63] : his skinned vertices in the bed, the desk chair, the desk top and the walls
// (the page's penetration(2)) while he does each idle variant, and through long runs of each activity.
//   1. every action and fidget of every context, made to play (the page's variant()), checked every 0.1 s;
//   2. each activity for minutes, the variants as they come, checked every 0.25 s.
import { chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";
const [port, seed = "63"] = process.argv.slice(2);
const browser = await chromium.launch({executablePath:process.env.SUB01_CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args:["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const page = await browser.newPage({viewport:{width:640, height:400}});
fs.mkdirSync("cdn", {recursive:true});
await page.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => { const u = r.request().url(), f = "cdn/" + u.replace(/[^a-z0-9.]+/gi, "_");
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`); await r.fulfill({status:200, contentType:"application/javascript", body:fs.readFileSync(f)}); });
page.on("pageerror", e => console.log("pageerror", e.message));
await page.goto(`http://localhost:${port}/room.html?debug&nolive&hour=${process.env.HOUR || 14}`);
await page.waitForFunction(() => window.boy && window.actions && window.actions.sleep && window.motion && window.motion.ready, null, {timeout:180000});
await page.evaluate(s => { window.FREEZE = true; setSeed(+s); }, seed);
const WHERE = {seat:"research", sill:"window", edge:"phone", lie:"sleep+phone", stand:"get_delivery"};
const run = (js, arg) => page.evaluate(js, arg);
const fmt = r => `bed ${r.bed} chair ${r.chair} desk ${r.desk} wall ${r.wall}`;
const worst = {bed:0, chair:0, desk:0, wall:0}, lines = [];
const keep = (what, r) => { for (const k in worst) worst[k] = Math.max(worst[k], r[k] || 0); lines.push(`${what}: ${fmt(r)}${r.at ? " " + r.at : ""}`); console.log(lines[lines.length - 1]); };
// 1. each variant, made to play
const LISTS = await run(() => ({ACTS, FIDGETS}));
const music = {...LISTS.ACTS, lie_music:[["hands", 14], ["rub", 3.5], ["scratch", 3]]};
for (const [ctx, list] of Object.entries(music)) {
  if (!WHERE[ctx] && ctx !== "lie_music") continue;
  for (const [n, d] of list.concat(ctx === "lie_music" ? [] : LISTS.FIDGETS[ctx] || [])) {
    const r = await run(([a, n, d]) => {
      const [x, sub] = a.split("+"); act(x); if (sub) live(sub); for (let i = 0; i < 60; i++) animate_(0.05);
      variant(n, d); const m = {bed:0, chair:0, desk:0, wall:0};
      for (let t = 0; t < d; t += 0.1) { animate_(0.05); animate_(0.05); const q = penetration(2); for (const k in m) m[k] = Math.max(m[k], q[k]); }
      return {...m, at:pose().at};
    }, [ctx === "lie_music" ? "listen_music" : WHERE[ctx], n, d]);
    keep(`${ctx} ${n}`, r);
  }
}
// 2. long runs
for (const [a, secs] of [["research", 600], ["chat", 240], ["window", 240], ["phone", 240], ["sleep+phone", 240], ["listen_music", 240], ["eat", 120]]) {
  const r = await run(([a, secs]) => {
    const [x, sub] = a.split("+"); act(x, x === "eat" ? {food:1} : {}); if (sub) live(sub);
    const m = {bed:0, chair:0, desk:0, wall:0}, seen = new Set();
    for (let t = 0; t < secs; t += 0.25) { for (let i = 0; i < 5; i++) animate_(0.05); if (IV.cur) seen.add(IV.cur.n);
      const q = penetration(2); for (const k in m) m[k] = Math.max(m[k], q[k]); }
    return {...m, at:pose().at + " " + [...seen].join(",")};
  }, [a, secs]);
  keep(`${a} ${secs} s`, r);
}
await browser.close();
console.log(`worst: ${fmt(worst)}`);
