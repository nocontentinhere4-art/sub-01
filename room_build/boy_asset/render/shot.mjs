// node shot.mjs out.png "query" [w h]  — renders view.html in headless Chromium (software WebGL)
import { chromium } from "playwright";
import http from "http"; import fs from "fs"; import path from "path";
const ROOT = path.resolve(process.cwd(), "../../../web"), THREE = path.resolve("/home/user/tools/pw/node_modules/three"), HERE = process.cwd();
const types = {".html":"text/html",".js":"text/javascript",".glb":"model/gltf-binary",".png":"image/png",".webp":"image/webp",".json":"application/json"};
const srv = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]);
  let f = u.startsWith("/three/") ? path.join(THREE, u.slice(7)) : u.startsWith("/local/") ? path.join(HERE, u.slice(7)) : u === "/view.html" ? path.join(HERE, "view.html") : path.join(ROOT, u);
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, {"content-type": types[path.extname(f)] || "application/octet-stream"}); fs.createReadStream(f).pipe(res);
});
await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));   // [{out, q, w, h}]
const browser = await chromium.launch({executablePath: process.env.CHROME_BIN || "/opt/pw-browsers/chromium", args:["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist"]});
for (const j of jobs) {
  const w = j.w || 800, h = j.h || 1000;
  const page = await browser.newPage({viewport:{width:w, height:h}});
  page.on("pageerror", e => console.log("PAGEERROR", e.message)); page.on("console", m => { if (m.type() === "error") console.log("CONSOLE", m.text()); });
  await page.goto(`http://127.0.0.1:${port}/view.html?w=${w}&h=${h}&${j.q}`);
  await page.waitForFunction(() => document.title === "ready", null, {timeout: 120000});
  await page.screenshot({path: j.out}); const info = await page.evaluate(() => window.__info); console.log(j.out, JSON.stringify(info)); await page.close();
}
await browser.close(); srv.close();
