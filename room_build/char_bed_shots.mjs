// node char_bed_shots.mjs char.glb clip.glb outdir hide(1|0) : the character in a clip's end pose (room_bed_lie) on a stand-in mattress, from the foot end and a low side (slides hidden with hide=1). DBG=1 / PICK / REL: debug helpers
import {chromium} from 'playwright-core'; import http from 'http'; import fs from 'fs'; import path from 'path';
const [glb, clipf, out, hide] = process.argv.slice(2); const root = path.dirname(new URL(import.meta.url).pathname);
const srv = http.createServer((q, s) => { const u = decodeURIComponent(q.url.split('?')[0]);
  const f = u === '/model.glb' ? glb : u === '/clip.glb' ? clipf : path.join(root, u);
  if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); }
  s.writeHead(200, {'Content-Type': {'.html':'text/html','.js':'text/javascript'}[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(s); }).listen(0);
const b = await chromium.launch({executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']});
fs.mkdirSync(out, {recursive: true});
const p = await b.newPage({viewport: {width: 800, height: 560}});
p.on('console', m => { if (m.type() === 'error') console.error(m.text()); }); p.on('pageerror', e => console.error(e));
await p.goto(`http://localhost:${srv.address().port}/char_bed_view.html?hide=${hide}`);
await p.waitForFunction('window.ready', null, {timeout: 600000});
if (process.env.DBG) console.log(JSON.stringify(await p.evaluate('dbg2()')));
fs.writeFileSync(path.join(out, 'info.json'), JSON.stringify(await p.evaluate('window.info'), null, 1));
for (const n of ['foot_end', 'foot_end_close', 'low_side', 'low_side_close']) { await p.evaluate(n => shot(n), n); await p.locator('canvas').screenshot({path: path.join(out, n + '.png')}); }
if (process.env.PICK) for (const [n, x, y] of JSON.parse(process.env.PICK)) console.log(x, y, JSON.stringify(await p.evaluate(a => pick(...a), [n, x, y])));
if (process.env.REL) for (const [n, ...a] of JSON.parse(process.env.REL)) { await p.evaluate(a => shotRel(...a), a); await p.locator('canvas').screenshot({path: path.join(out, n + '.png')}); }
await b.close(); srv.close();
