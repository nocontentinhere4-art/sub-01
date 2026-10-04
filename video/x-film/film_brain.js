// Films the live /brain page (real model activity from the demo server) frame by frame with Playwright's fake clock:
// each frame advances the page's clock by 1/fps, so the autorotation and pulses are smooth whatever the render speed.
// usage: node film_brain.js <outdir> <seconds> <WxH> [query] [fps]
const fs = require('fs'), path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const [out, secs = '2', size = '1080x1080', query = 'mini', fpsArg = '30'] = process.argv.slice(2);
const [W, H] = size.split('x').map(Number), FPS = +fpsArg;
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: W, height: H }, ignoreHTTPSErrors: true });
  const p = await ctx.newPage();
  await p.route('**/three.min.js', r => r.fulfill({ path: path.join(__dirname, 'cdn/three.min.js'), contentType: 'text/javascript' }));
  await p.route('**/OrbitControls.js', r => r.fulfill({ path: path.join(__dirname, 'cdn/OrbitControls.js'), contentType: 'text/javascript' }));
  await p.route(/spotify|youtube|tiktok/, r => r.abort());
  p.on('pageerror', e => console.log('E', e.message));
  await p.addInitScript(() => {             // keep the drawn frame readable after the (faked) animation frame ends
    const g = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (t, o) { if (/webgl/.test(t)) o = Object.assign({}, o, { preserveDrawingBuffer: true }); return g.call(this, t, o); };
  });
  await p.clock.install();
  await p.clock.resume();
  await p.goto('http://localhost:8765/brain?' + query, { waitUntil: 'domcontentloaded', timeout: 180000 });
  await p.waitForFunction(() => typeof THREE !== 'undefined' && document.querySelector('#scene canvas'), null, { timeout: 180000 });
  await p.waitForTimeout(25000);                          // fibres, cortex and the first ticks
  await p.addStyleTag({ content: '#vignette{display:none!important}' + (process.env.HUD_OFF ? '#top,#cards,#dock,#ticker,#honest,#anat,#anatcap,#layers,#n3cap{display:none!important}' : '') });
  await p.clock.pauseAt(Date.now() + 1000);
  const n = Math.round(+secs * FPS), t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await p.clock.runFor(Math.round(1000 / FPS));
    const d = await p.evaluate(() => document.querySelector('#scene canvas').toDataURL('image/jpeg', 0.92));
    fs.writeFileSync(path.join(out, String(i).padStart(5, '0') + '.jpg'), Buffer.from(d.split(',')[1], 'base64'));
    if (i % 30 === 0) console.log(`${out} frame ${i}/${n} ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
  await b.close();
})();
