// node probe.mjs <cfg.json> <js expression evaluated in the page after setup>
import fs from "node:fs"; import path from "node:path"; import http from "node:http"; import { chromium } from "playwright-core";
const cfg = JSON.parse(fs.readFileSync(process.argv[2])); const expr = process.argv[3];
const SITE = new URL("./site/", import.meta.url).pathname;
const srv = http.createServer((q, r) => { const p = path.join(SITE, decodeURIComponent(q.url.split("?")[0])); fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, {"Content-Type": p.endsWith(".html") ? "text/html" : p.endsWith(".js") ? "text/javascript" : "application/octet-stream"}); r.end(d); }); }).listen(0);
const b = await chromium.launch({executablePath: process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]});
const pg = await b.newPage({viewport: {width: 320, height: 180}}); pg.on("console", m => { if (m.type() === "error") console.error(m.text()); });
await pg.goto(`http://127.0.0.1:${srv.address().port}/scene.html?w=320&h=180`); await pg.waitForFunction(() => window.ready);
await pg.evaluate(c => window.setup(c), cfg); console.log(JSON.stringify(await pg.evaluate(e => eval(e), expr)));
await b.close(); srv.close();
