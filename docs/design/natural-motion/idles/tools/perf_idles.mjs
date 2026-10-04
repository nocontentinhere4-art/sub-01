// node perf_idles.mjs <port> : mid phone profile (390x844, DPR 2, CPU x4 via CDP). Per state, with an idle variant made to
// play: the script cost of one frame of him (the page's animate(), the motion layer included; no rendering), the median
// of 5 runs of 60 frames. The real frame rate can't be measured headless: SwiftShader draws WebGL on the CPU.
import { chromium } from "playwright";
import fs from "fs";
import { execSync } from "child_process";
const [port] = process.argv.slice(2);
const browser = await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args:["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]});
const ctx = await browser.newContext({viewport:{width:390, height:844}, deviceScaleFactor:2, isMobile:true, hasTouch:true, ignoreHTTPSErrors:true});
const page = await ctx.newPage();
await page.route(/^https:\/\/(cdn\.jsdelivr\.net|unpkg\.com)\//, async r => {
  const u = r.request().url(), f = "cdn/" + u.replace(/[^a-z0-9.]+/gi, "_");
  if (!fs.existsSync(f)) execSync(`curl -sSfL -o ${f} '${u}'`);
  await r.fulfill({status:200, contentType:u.endsWith(".css") ? "text/css" : "application/javascript", body:fs.readFileSync(f)});
});
await page.goto(`http://localhost:${port}/room.html?debug&nolive&hour=14`);
await page.waitForFunction(() => window.boy && window.room && window.actions && ["walk", "idle", "door", "eat", "sleep", "phone_sit", "phone_lie"].every(k => window.actions[k]), null, {timeout:120000});
const cdp = await ctx.newCDPSession(page);
await cdp.send("Emulation.setCPUThrottlingRate", {rate:4});
// each case: an activity, then (after "/") an idle variant made to play for the whole measurement
const CASES = ["research", "research/lean", "research/rub", "research/neck", "research/window", "research/drink", "research/stretch",
  "window", "window/chin", "phone", "phone/rest", "sleep+phone", "sleep+phone/rest", "listen_music/hands"];
for (const c of CASES) { const [a, v] = c.split("/"), prep = v ? `variant("${v}", 30); IV.cur.t = 3` : "";
  const r = await page.evaluate(async ([a, prep]) => {
    window.FREEZE = true; const [x, sub] = a.split("+"); act(x); if (sub) live(sub); sim(1 / 60, 60); if (prep) eval(prep); sim(1 / 60, 30);
    const ms = []; for (let k = 0; k < 5; k++) { const t0 = performance.now(); for (let i = 0; i < 60; i++) animate_(1 / 60); ms.push((performance.now() - t0) / 60); }
    ms.sort((p, q) => p - q); return {ms_per_frame:+ms[2].toFixed(2), worst_of_5:+ms[4].toFixed(2)};
  }, [a, prep]);
  console.log(c.padEnd(20), JSON.stringify(r));
}
await browser.close();
