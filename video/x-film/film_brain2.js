// Renders brain takes with brain_film.html, frame by frame, from recorded live-model activity (data/act_*.json).
// usage: node film_brain2.js <take> ...   (takes defined in TAKES below)
const fs = require('fs'), path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const FPS = 30;
const ease = x => { x = Math.min(1, Math.max(0, x)); return x < .5 ? 4*x*x*x : 1 - Math.pow(-2*x+2, 3)/2; };
const STAGE = { AWAKE: [1, 0, 0], NREM: [0, 1, 0], REM: [0, 0, 1] };
// stage timeline: [[t, stage], ...]; the mix eases to each stage over 0.6 s (the page: 2.5 s; faster for the edit)
const TAKES = {
  hook:  { size: [1080, 1350], secs: 2.4, stages: [[0, 'AWAKE']], cam: t => ({ az: -2.6 + 0.10 * t, el: 0.32, dist: 150 + 260 * ease(t / 2.2), boost: 0.6 * (1 - t / 2.4) }) },
  main:  { size: [1080, 540], secs: 15.0, stages: [[0, 'AWAKE'], [11.6, 'NREM'], [13.2, 'REM']], cam: t => ({ az: -2.4 + 0.09 * t, el: 0.30, dist: 215 }) },
  tl:    { size: [600, 600], secs: 4.6, stages: [[0, 'AWAKE'], [3.4, 'NREM']], cam: t => ({ az: -1.0 + 0.25 * t, el: 0.35, dist: 255 }) },
  end:   { size: [1080, 540], secs: 6.0, stages: [[0, 'REM']], cam: t => ({ az: -0.2 + 0.06 * t, el: 0.25, dist: 230 - 30 * ease(t / 6) }) },
};
function loadAct(file) {
  const rows = JSON.parse(fs.readFileSync(path.join(__dirname, 'data', file)));
  const n = rows[0].act.length, base = new Array(n).fill(0);
  rows.forEach(r => r.act.forEach((a, i) => base[i] += a / rows.length));
  return rows.map(r => {
    const raw = r.act.map((a, i) => a / Math.max(base[i], 0.02));
    const gm = Math.max(1e-3, raw.reduce((x, y) => x + y, 0) / raw.length);
    return { stage: r.stage, v: raw.map(x => Math.min(255, Math.round(x / gm / 3 * 255))) };
  });
}
(async () => {
  const awake = loadAct('act_awake.json');
  const night = fs.existsSync(path.join(__dirname, 'data/act_night.json')) ? loadAct('act_night.json') : awake;
  const pool = { AWAKE: awake.filter(r => r.stage === 'AWAKE'), NREM: night.filter(r => r.stage === 'NREM'), REM: night.filter(r => r.stage === 'REM') };
  for (const k of Object.keys(pool)) if (!pool[k].length) { console.log('no recorded', k, 'ticks: using awake'); pool[k] = awake; }
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(2)) {
    const T = TAKES[name], out = path.join(__dirname, 'takes', 'brain_' + name);
    fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out, { recursive: true });
    const p = await b.newPage({ viewport: { width: T.size[0], height: T.size[1] } });
    p.on('pageerror', e => console.log('E', e.message));
    await p.goto('http://127.0.0.1:8899/video/x-film/brain_film.html');
    console.log(name, await p.evaluate(() => window.ready));
    const n = Math.round(T.secs * FPS), t0 = Date.now();
    let mix = STAGE[T.stages[0][1]].slice(), idx = { AWAKE: 0, NREM: 0, REM: 0 };
    for (let f = 0; f < n; f++) {
      const t = f / FPS;
      const st = T.stages.filter(s => s[0] <= t).pop()[1];
      const k = 1 - Math.exp(-(1 / FPS) / 0.25);
      mix = mix.map((m, i) => m + (STAGE[st][i] - m) * k);
      // the model ticks at 10 Hz: 3 frames per tick, blended between ticks
      const pl = pool[st], i0 = Math.floor(f / 3) % pl.length, i1 = (i0 + 1) % pl.length, w = (f % 3) / 3;
      const act = pl[i0].v.map((a, j) => Math.round(a + (pl[i1].v[j] - a) * w));
      const spec = Object.assign({ t, mix, act }, T.cam(t));
      const d = await p.evaluate(s => window.renderAt(s), spec);
      fs.writeFileSync(path.join(out, String(f).padStart(5, '0') + '.jpg'), Buffer.from(d.split(',')[1], 'base64'));
      if (f % 60 === 0) console.log(`${name} ${f}/${n} ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
    await p.close();
  }
  await b.close();
})();
