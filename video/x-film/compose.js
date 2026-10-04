// Composes the X film from the takes (GPU room footage, brain renders) with compose.html, one screenshot per frame.
// usage: node compose.js   -> frames/ then encode with soundtrack (see build.sh)
const fs = require('fs'), path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const FPS = 30, D = __dirname, TK = path.join(D, 'takes');
const room = JSON.parse(fs.readFileSync(path.join(D, '../../data/xfilm/room.json')));
const bedPath = path.join(D, '../../data/xfilm/bed/room.json');
const bed = fs.existsSync(bedPath) ? JSON.parse(fs.readFileSync(bedPath)) : null;
// a room shot's frame: by label, from the bed re-render when it has that label
function shot(label, i) {
  const b = bed && bed.segments.find(s => s.label === label);
  const seg = b || room.segments.find(s => s.label === label);
  const k = seg.first + Math.min(seg.frames - 1, Math.max(0, i));
  return `takes/${b ? 'bed' : 'room'}/${String(k).padStart(5, '0')}.jpg`;
}
const take = (name, i, n) => `takes/brain_${name}/${String(Math.min(n - 1, Math.max(0, i))).padStart(5, '0')}.jpg`;
const cnt = name => { try { return fs.readdirSync(path.join(TK, 'brain_' + name)).length; } catch (e) { return 1; } };
const ease = x => { x = Math.min(1, Math.max(0, x)); return 1 - Math.pow(1 - x, 3); };
// a word-by-word pop: each word scales from 1.25 and fades in, 0.07 s apart, from t0
function pop(text, t, t0, cls = '') {
  return text.split(' ').map((w, i) => {
    const u = ease((t - t0 - i * 0.07) / 0.18);
    return `<span style="display:inline-block;opacity:${u};transform:scale(${1.25 - 0.25 * u});transform-origin:50% 80%;margin-right:.22em" class="${cls}">${w}</span>`;
  }).join('');
}
const STC = { AWAKE: 'var(--awake)', NREM: 'var(--nrem)', REM: 'var(--rem)' }, STT = { AWAKE: 'AWAKE', NREM: 'DEEP SLEEP', REM: 'REM' };
const SPLIT = [
  { label: 'wake', d: 2.4, clock: '07:54', cap: 'its sleep circuit wakes him up' },
  { label: 'desk', d: 2.6, clock: '14:02', cap: 'reads the web. its brain model votes on every click' },
  { label: 'eat', d: 2.2, clock: '19:10', cap: 'orders ramen' },
  { label: 'window', d: 2.4, clock: '19:41', cap: 'stares at Tokyo' },
  { label: 'phone-night', d: 2.4, clock: '23:18', cap: 'doomscrolls in bed' },
  { label: 'sleep', d: 3.0, clock: '23:56', cap: 'falls asleep. no timer: a sleep–wake circuit' },
];
const TL = ['tl-06', 'tl-09', 'tl-12', 'tl-15', 'tl-18', 'tl-20', 'tl-22', 'tl-01'];
const A = 2.4, B = 5.0, C = 20.0, Dd = 24.4, E = 29.6;
const flashAt = (t, cuts) => { for (const c of cuts) if (t >= c && t < c + 0.1) return 0.5 * (1 - (t - c) / 0.1); return 0; };

function spec(t, f, N) {
  const s = { flash: flashAt(t, [A, B, C, Dd]) };
  if (t < A) {                                                     // A: the brain, then the hook
    s.full = take('hook', f, N.hook);
    s.html = `<div class="grad-top"></div><div class="t hook" style="top:110px">We turned a real human MRI</div>
              <div class="t hook" style="top:300px">${pop('into a brain model.', t, 0.8, 'acc')}</div>`;
  } else if (t < B) {                                              // B: the body
    const u = t - A;
    s.full = shot('hook-desk', Math.round(u * FPS));
    s.html = `<div class="grad-top"></div><div class="grad-bot"></div>
              <div class="t hook" style="top:110px">${pop('Then we gave it a body.', u, 0.05)}</div>
              <div class="t sub" style="bottom:120px">${pop('A fictional guy in a tiny room in Tokyo.', u, 1.0)}</div>`;
  } else if (t < C) {                                              // C: split screen, a day
    const u = t - B;
    let acc = 0, sh = SPLIT[0], v = 0;
    for (const x of SPLIT) { if (u < acc + x.d) { sh = x; v = u - acc; break; } acc += x.d; }
    if (u >= 15) { sh = SPLIT[5]; v = u - 12; }
    const bt = Math.max(0, u - 0.5);                               // brain take time (its NREM starts at 11.6 s)
    const st = bt < 11.6 ? 'AWAKE' : bt < 13.2 ? 'NREM' : 'REM';
    let clock = sh.clock, cap = sh.cap;
    if (sh.label === 'sleep' && st === 'REM') { clock = '04:12'; cap = 'REM sleep: it replays what it read today'; }
    s.top = shot(sh.label, Math.round(v * FPS));
    s.bot = take('main', Math.round(bt * FPS), N.main);
    s.flash = Math.max(s.flash, v < 0.1 && u > 0.1 ? 0.3 * (1 - v / 0.1) : 0);
    const capKey = sh.label + (cap === sh.cap ? '' : 'R'), cv = cap === sh.cap ? v : bt - 13.2;
    s.html = `<div class="grad-cap"></div><div id="cap">${pop(cap, cv, 0.05)}</div>
      <div id="bar"><span class="clock">${clock}</span><span class="chip" style="background:${STC[st]}">${STT[st]}</span></div>
      <div id="brainlbl">his brain model, live · built from a real MRI</div>`;
  } else if (t < Dd) {                                             // D: the time-lapse
    const u = t - C, per = 0.5, i = Math.min(TL.length - 1, Math.floor(u / per)), w = u - i * per;
    s.full = shot(TL[i], Math.round(w * FPS));
    if (i < TL.length - 1 && w > per - 0.15) { s.full2 = shot(TL[i + 1], 0); s.full2a = (w - (per - 0.15)) / 0.15; }
    const h = 6 + 19 * Math.min(1, u / 4.0), hh = Math.floor(h) % 24, mm = Math.floor((h % 1) * 60);
    const st = u < 3.4 ? 'AWAKE' : 'NREM';
    s.pip = take('tl', Math.round(u * FPS), N.tl); s.pipColor = STC[st];
    s.html = `<div class="grad-top"></div><div class="grad-bot"></div>
      <div id="bigclock">${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}</div>
      <div class="t sub" style="bottom:110px;right:400px">${pop('Every day. 24/7. Nobody controls him.', u, 0.1)}</div>`;
  } else {                                                         // E: the honest end
    const u = t - Dd;
    s.full = shot('end-sleep', Math.round(u * FPS));
    s.shade = 0.25 + 0.35 * ease((u - 2.4) / 0.8);
    s.pip = take('end', Math.round(u * FPS), N.end); s.pipColor = STC.REM;
    const logo = ease((u - 2.6) / 0.5);
    s.html = `<div class="grad-top"></div>
      <div class="t hook" style="top:110px">${pop("It's a model.", u, 0.1)}</div>
      <div class="t hook" style="top:205px;color:#c26bff">${pop('Not a mind.', u, 0.9)}</div>
      <div id="logo" style="opacity:${logo};transform:translateY(${(1 - logo) * 30}px)"><div class="n">SUB–01</div><div class="s">watch him live · soon</div></div>`;
    if (u > 2.4) s.pip = null;
  }
  return s;
}

(async () => {
  const N = { hook: cnt('hook'), main: cnt('main'), tl: cnt('tl'), end: cnt('end') };
  const out = path.join(D, 'frames'); fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out);
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, ignoreHTTPSErrors: true });
  await p.goto('http://127.0.0.1:8899/video/x-film/compose.html');
  await p.evaluate(() => document.fonts.ready);
  const n = Math.round(E * FPS), only = process.env.ONLY ? process.env.ONLY.split(',').map(Number) : null;
  for (let f = 0; f < n; f++) {
    if (only && !only.includes(f)) continue;
    const t = f / FPS, s = spec(t, f, N);
    await p.evaluate(s => window.frame(s), s);
    await p.screenshot({ path: path.join(out, String(f).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 93 });
    if (f % 150 === 0) console.log('compose', f, '/', n);
  }
  await b.close();
})();
