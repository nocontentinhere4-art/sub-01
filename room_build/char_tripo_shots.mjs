// node char_tripo_shots.mjs <glb> <outdir> <jobs.json> : headless Chromium stills of the Tripo character (QA). jobs: [{name, pos, tgt, fov, w, h, clip?, t?, follow?}]
import {chromium} from 'playwright-core';
import http from 'http'; import fs from 'fs'; import path from 'path';
const [glb, out, jobsFile] = process.argv.slice(2);
const root = path.dirname(new URL(import.meta.url).pathname);
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  const f = u === '/model.glb' ? glb : path.join(root, u);
  if (!fs.existsSync(f)) { s.writeHead(404); return s.end(); }
  const ext = path.extname(f);
  s.writeHead(200, {'Content-Type': {'.html':'text/html','.js':'text/javascript','.glb':'model/gltf-binary'}[ext]||'application/octet-stream'});
  fs.createReadStream(f).pipe(s);
}).listen(0);
const port = srv.address().port;
const jobs = JSON.parse(fs.readFileSync(jobsFile));
const b = await chromium.launch({executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']});
fs.mkdirSync(out, {recursive: true});
const groups = {};
for (const j of jobs) { const k = `${j.w||800}x${j.h||1000}`; (groups[k] ||= []).push(j); }
for (const [k, js] of Object.entries(groups)) {
  const [w, h] = k.split('x').map(Number);
  const p = await b.newPage({viewport: {width: w, height: h}});
  p.on('console', m => { if (m.type() === 'error') console.error(m.text()); });
  p.on('pageerror', e => console.error(e));
  await p.goto(`http://localhost:${port}/char_tripo_view.html?glb=/model.glb&w=${w}&h=${h}`);
  await p.waitForFunction('window.ready', null, {timeout: 600000});
  if (!fs.existsSync(path.join(out, 'info.json'))) fs.writeFileSync(path.join(out, 'info.json'), JSON.stringify(await p.evaluate('window.info'), null, 1));
  for (const j of js) {
    await p.evaluate(j => shot(j.pos, j.tgt, j.fov || 30, j.clip ?? null, j.t || 0, j.follow || null), j);
    await p.locator('canvas').screenshot({path: path.join(out, j.name + '.png')});
    console.log(j.name);
  }
  await p.close();
}
await b.close(); srv.close();
