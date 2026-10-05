// The 25 s mini documentary (EP.1): a real recorded browsing session of SUB-01 (screens + the brain model's votes),
// then the reveal (room + brain renders), then tomorrow's test. Frames from doc.html; encode with doc_build.sh.
const fs = require('fs'), path = require('path');
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const FPS = 30, D = __dirname, DUR = 25.0;
const room = JSON.parse(fs.readFileSync(path.join(D, '../../data/xfilm/room.json')));
const shot = (label, i) => { const s = room.segments.find(x => x.label === label); return `takes/room/${String(s.first + Math.min(s.frames - 1, Math.max(0, i))).padStart(5, '0')}.jpg`; };
const bt = (name, i, n) => `takes/brain_${name}/${String(Math.min(n - 1, Math.max(0, i))).padStart(5, '0')}.jpg`;
const W = f => `takes/web/${f}.jpg`;
const ease = x => { x = Math.min(1, Math.max(0, x)); return 1 - Math.pow(1 - x, 3); };
const pop = (text, t, t0, cls = '') => text.split(' ').map((w, i) => {
  const u = ease((t - t0 - i * 0.06) / 0.16);
  return `<span class="${cls}" style="display:inline-block;opacity:${u};transform:scale(${1.3 - 0.3 * u});transform-origin:50% 80%;margin-right:.22em">${w}</span>`; }).join('');
const typed = (q, t, t0, cps = 22) => q.slice(0, Math.max(0, Math.floor((t - t0) * cps)));
const search = (q, t, t0, top) => `<div class="search" style="top:${top}px"><span class="ic"></span>${typed(q, t, t0)}<span class="caret" style="opacity:${Math.floor(t * 4) % 2}"></span></div>`;
const chip = (clock, t, t0) => `<div style="position:absolute;left:50px;top:70px;opacity:${ease((t - t0) / 0.1)}"><span class="chip">${clock}</span></div>`;
// a decision as the brain model saw it: its options with their probability bars, the chosen one marked
function options(opts, chosen, t, t0, top, hi = 'CHOSEN') {
  return opts.map((o, i) => {
    const u = ease((t - t0 - 0.05 * i) / 0.35), sel = i === chosen, y = top + i * 112;
    return `<div class="opt" style="top:${y}px;height:100px;padding:16px 26px;${sel && t - t0 > 0.45 ? 'border-color:var(--green);background:rgba(10,40,25,.95)' : ''}">
      <div class="bar" style="width:${o[1] * 100 * u}%;${sel ? 'background:rgba(57,245,160,.32)' : ''}"></div>
      <div class="lbl" style="font-size:32px;line-height:68px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:760px">${o[0]}</div>
      <div class="pct" style="font-size:40px;bottom:24px">${Math.round(o[1] * 100 * u)}%</div></div>`; }).join('');
}
// the recorded decisions (data/decisions: the live run of 2026-10-04, demo mode with the real browser on the open web)
const DEC = {
  ad:    [[['Powered by Sellwild', .145], ['look up Just Ran', .221], ['look up Manthey Kit', .165], ['wander somewhere else', .34]], 0],
  shoes: [[['Sneaker Release Dates for 2026', .566], ['look up Nice Kicks', .372], ['look up Sneaker Freaker', .022], ['Sneaker News - Air Jordans', .021]], 1],
  mars:  [[['The Mars Rovers | NASA Space Place', .81], ['wander somewhere else', .058], ['search this site for porsche record', .04], ['NASA Says Mars Rover Discovered…', .035]], 0],
};
const CUTS = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 10.8, 12.6, 17.0, 21.0];
function spec(t, N) {
  const s = { flash: 0, rec: `<span style="color:#ff3b3b">●</span> REC ${String(Math.floor(t)).padStart(2, '0')}:${String(Math.floor((t % 1) * 30)).padStart(2, '0')}` };
  for (const c of CUTS) if (t >= c && t < c + 0.08) s.flash = 0.45 * (1 - (t - c) / 0.08);
  if (t < 3.0) {                                                    // HOOK
    s.img = W('desk_1791156965'); s.imgT = `scale(${1.55 + 0.25 * t / 3}) translate(${-60 + 20 * t}px, ${60 - 10 * t}px)`; s.imgP = '0% 0%'; s.scan = true;
    s.html = `<div class="grad-t"></div><div class="grad-b"></div>
      <div class="t h1" style="top:120px">Gli abbiamo dato internet.</div>
      <div class="t h2" style="bottom:300px">${pop('In 18 minuti è passato da una Porsche…', t, 0.5)}</div>
      <div class="t h1" style="bottom:150px">${pop('…ai rover su Marte.', t, 1.7, 'y')}</div>`;
  } else if (t < 4.0) {                                             // 09:31 the search
    const u = t - 3.0;
    s.img = W('desk_1791156965'); s.imgT = `scale(${1.2 + 0.08 * u})`; s.imgP = '0% 0%'; s.scan = true;
    s.html = `<div class="grad-t"></div>${chip('09:31 · CERCA', u, 0)}${search('Porsche 911 GT3', u, 0.05, 160)}`;
  } else if (t < 5.0) {                                             // 09:33 the article, 81 %
    const u = t - 4.0;
    s.img = W('desk_1791157001'); s.imgT = `scale(${1.35 + 0.1 * u})`; s.imgP = '0% 0%'; s.scan = true;
    s.html = `<div class="grad-b"></div>${chip('09:33', u, 0)}<div class="t h2" style="bottom:120px">${pop('Il suo cervello vota l’articolo:', u, 0.05)} <span class="g">${pop('81%', u, 0.4)}</span></div>`;
  } else if (t < 8.0) {                                             // 09:47 / 09:49 / 09:49: the drift, as the brain voted it
    const k = t < 6 ? 'ad' : t < 7 ? 'shoes' : 'mars', u = t - (t < 6 ? 5 : t < 7 ? 6 : 7);
    const clock = { ad: '09:47', shoes: '09:49', mars: '09:49' }[k];
    const cap = { ad: 'clicca… la scritta della pubblicità', shoes: 'poi le sneakers', mars: 'poi la NASA. Marte.' }[k];
    s.img = W(k === 'ad' ? 'desk_1791157055' : 'desk_1791157011'); s.imgF = 'blur(6px) brightness(.35)'; s.imgT = 'scale(1.3)';
    s.html = `${chip(clock + ' · OPZIONI', u, 0)}<div class="t h3 mono" style="top:150px;font-size:28px;color:rgba(255,255,255,.7)">il cervello simulato vota tra le opzioni della pagina</div>
      ${options(...DEC[k], t, t - u + 0.02, 230)}
      <div class="t h1" style="bottom:120px;font-size:72px">${pop(cap, u, 0.3, k === 'mars' ? 'y' : '')}</div>`;
  } else if (t < 10.0) {                                            // 09:59: THE FORK
    const u = t - 8.0, done = u > 1.15;
    const card = (top, tag, lbl, p, win) => `<div class="opt" style="top:${top}px;${done ? (win ? 'border-color:var(--green);background:rgba(10,40,25,.95)' : 'opacity:.4') : ''}">
      <div class="bar" style="width:${p * 100 * ease(u / 0.9)}%;${win && done ? 'background:rgba(57,245,160,.35)' : ''}"></div>
      <div class="tag">${tag}</div><div class="lbl">${lbl}</div><div class="pct">${Math.round(p * 100 * ease(u / 0.9))}%</div></div>`;
    s.img = W('desk_1791157171'); s.imgF = 'blur(8px) brightness(.3)'; s.imgT = 'scale(1.3)';
    s.html = `${chip('09:59 · BIVIO', u, 0)}
      <div class="t h1" style="top:160px">${pop(done ? 'Ha scelto il manga.' : 'Tu cosa sceglieresti?', u, done ? 1.15 : 0.05, done ? 'g' : '')}</div>
      ${card(420, 'OPZIONE A · la favorita', 'cerca “Corvette”', .572, false)}
      ${card(660, 'OPZIONE B', 'cerca “Blue Box” (manga)', .237, true)}
      ${done ? `<div class="stamp" style="left:${560 + 40 * (1 - ease((u - 1.15) / 0.12))}px;top:640px;transform:rotate(-8deg) scale(${1.6 - 0.6 * ease((u - 1.15) / 0.12)})">SCELTO</div>` : ''}
      ${done ? `<div style="position:absolute;left:60px;right:60px;top:520px;height:6px;background:var(--red);transform:rotate(-2deg)"></div>` : ''}`;
  } else if (t < 10.8) {                                            // the failed attempt, kept
    const u = t - 10.0;
    s.img = W('desk_1791157179'); s.imgF = 'brightness(.35)'; s.imgT = `translate(${u > 0.45 ? (Math.sin(t * 90) * 14) : 0}px,0) scale(1.2)`;
    s.html = `${chip('POCO DOPO · CERCA', u, 0)}${search('Re:Zero 4th season', u, 0, 220)}
      ${u > 0.45 ? `<div class="err" style="top:380px">✕ ERR_TOO_MANY_RETRIES<br><span style="font-size:30px;color:#fff">la ricerca fallisce. riprova da un'altra parte.</span></div>` : ''}`;
  } else if (t < 12.6) {                                            // reveal: the brain
    const u = t - 10.8;
    s.img = bt('hook', Math.round(u / 1.8 * 71), N.hook);
    s.html = `<div class="grad-t"></div><div class="t h1" style="top:130px;font-size:96px">${pop('Questo è SUB-01.', u, 0.05)}</div>`;
  } else if (t < 17.0) {                                            // the system running: room + brain
    const u = t - 12.6, split = u > 1.4;
    if (!split) { s.img = shot('hook-desk', Math.round(u * FPS)); }
    else { s.img = shot('desk', Math.round((u - 1.4) * FPS)); s.imgT = 'translateY(-270px)'; s.img2 = bt('main', Math.round((u - 1.4) * FPS), N.main); s.img2T = 'translateY(810px) scale(1, 0.4)'; s.img2A = 0; }
    s.html = split
      ? `<img src="${bt('main', Math.round((u - 1.4) * FPS), N.main)}" style="position:absolute;left:0;top:810px;width:1080px;height:540px;object-fit:cover">
         <div style="position:absolute;left:0;right:0;top:786px;text-align:center"><span class="chip" style="background:var(--awake)">AWAKE</span></div>
         <div class="t h2" style="top:560px;font-size:46px">${pop('Una simulazione costruita su connessioni derivate da una MRI umana.', u, 1.5)}</div>`
      : `<div class="grad-b"></div><div class="t h2" style="bottom:140px">${pop('Un personaggio inventato. Una stanza a Tokyo.', u, 0.1)}</div>`;
  } else if (t < 21.0) {                                            // tomorrow's test
    const u = t - 17.0, tl = ['tl-06', 'tl-09', 'tl-12', 'tl-15', 'tl-18', 'tl-20', 'tl-22', 'tl-01'], i = Math.min(7, Math.floor(u / 0.5));
    s.img = shot(tl[i], Math.round((u - i * 0.5) * FPS));
    s.html = `<div class="grad-t"></div><div class="grad-b"></div>
      <div class="t h1" style="top:120px">${pop('Domani: una giornata senza compiti.', u, 0.1)}</div>
      <div class="t h2" style="bottom:140px">${pop('Corvette o manga? Vediamo cosa sceglie.', u, 1.6, '')}</div>`;
  } else {                                                          // the consequence, the series
    const u = t - 21.0;
    s.img = bt('end', Math.round(u * FPS), N.end); s.imgA = 0.55;
    s.html = `<div class="t h2" style="top:200px">${pop('Oggi ha scelto il manga.', u, 0.05)}</div>
      <div class="t h2" style="top:280px">${pop('Domani il suo cervello parte da lì.', u, 0.8, 'p')}</div>
      <div style="position:absolute;left:0;right:0;bottom:180px;text-align:center;opacity:${ease((u - 1.8) / 0.4)}">
        <div class="mono" style="font-weight:800;font-size:110px">SUB–01</div>
        <div class="mono" style="font-size:36px;margin-top:8px">EP.1 / 30 · segui per l’EP.2</div></div>`;
  }
  return s;
}
(async () => {
  const cnt = n => fs.readdirSync(path.join(D, 'takes', 'brain_' + n)).length;
  const N = { hook: cnt('hook'), main: cnt('main'), end: cnt('end') };
  const out = path.join(D, 'doc_frames'); fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out);
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, ignoreHTTPSErrors: true });
  await p.goto('http://127.0.0.1:8899/video/x-film/doc.html'); await p.evaluate(() => document.fonts.ready);
  const only = process.env.ONLY ? process.env.ONLY.split(',').map(Number) : null;
  for (let f = 0; f < Math.round(DUR * FPS); f++) {
    if (only && !only.includes(f)) continue;
    await p.evaluate(s => window.frame(s), spec(f / FPS, N));
    await p.screenshot({ path: path.join(out, String(f).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 93 });
  }
  await b.close();
})();
