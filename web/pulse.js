// SUB-01 · pulse.js (defer, every page with <body data-pulse>). The pulse strip: 28 px at the bottom of the page, the
// four model readouts of the last 60 s scrolling right to left, their values at the right, the sleep stage when he is
// not awake. It also keeps the header's clock (#ui-clock) and live chip (#ui-live, #ui-live-t) up to date.
// The readouts are named attention, alertness, effort, activity (phones: AT · AL · EF · AC). window.SUB01Pulse.spike()
// sends a bright pulse along the strip (any page may call it; it also fires when the socket receives a "chat" message).
// The readouts are formulas over the model's simulated activity (as on web/live.html), not measured from anyone.
// One WebSocket (/ws?rate=5&q=1) per page; <body data-pulse="feed"> opens none: the page passes its own messages to
// window.SUB01Pulse.feed(msg) and its socket state to window.SUB01Pulse.online(bool).
(() => {
  "use strict";
  const body = document.body;
  if (!body || !body.hasAttribute("data-pulse") || document.getElementById("ui-pulse")) return;

  const RATE = 5, ACT_LO = 0.01, ACT_HI = 10, WIN_MS = 60000, WARM_MS = 25000, FPS = 10;
  const ACT_LUT = Float32Array.from({length:256}, (_, b) => ACT_LO * Math.pow(ACT_HI / ACT_LO, b / 255));
  const clamp = (v, a = 0, b = 100) => Math.max(a, Math.min(b, v));
  const R = x => clamp(50 + 40 * Math.log2(Math.max(1e-4, x)));        // 50 = his own baseline
  const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : NaN;
  const $ = id => document.getElementById(id);
  const RM = matchMedia("(prefers-reduced-motion: reduce)");
  const STAGE = {NREM:"NREM · asleep", REM:"REM · dreaming"};
  const KEYS = ["a", "r", "l", "n"], LETTER = {a:"AT", r:"AL", l:"EF", n:"AC"},
        NAME = {a:"attention", r:"alertness", l:"effort", n:"activity"};
  const COL = {a:"#ffffff", r:"#5aa9ff", l:"#ffd166", n:"#2ee6c5"};
  try { const cs = getComputedStyle(document.documentElement), g = k => cs.getPropertyValue(k).trim();
    COL.a = g("--ui-attn") || COL.a; COL.r = g("--ui-arousal") || COL.r; COL.l = g("--ui-load") || COL.l; COL.n = g("--ui-neural") || COL.n; } catch (e) {}

  // ---------------------------------------------------------------- the strip
  const root = document.createElement("div");
  root.id = "ui-pulse"; root.setAttribute("role", "group"); root.setAttribute("aria-label", "live readouts");
  root.title = "Attention · alertness · effort · activity, the last 60 s. Model readouts, not measured from anyone. 50 = his own baseline.";
  const cv = document.createElement("canvas"); cv.setAttribute("aria-hidden", "true");
  const vals = document.createElement("div"); vals.className = "ui-pulse-vals";
  const stageEl = document.createElement("span"); stageEl.className = "ui-chip ui-pulse-stage"; stageEl.hidden = true;
  stageEl.setAttribute("aria-live", "polite"); stageEl.setAttribute("aria-atomic", "true");   // the only live region
  const row = document.createElement("span"); row.className = "ui-pulse-row";
  const num = {}, sr = {};
  const cap = t => t[0].toUpperCase() + t.slice(1);
  const mk = (cls, text, attrs) => { const e = document.createElement("span"); e.className = cls; e.textContent = text;
    if (attrs) for (const a in attrs) e.setAttribute(a, attrs[a]); return e; };
  KEYS.forEach((k, i) => {
    // real text: a visually hidden "Attention 61" for screen readers, the visible short form (words, or letters on phones)
    // aria-hidden; the numbers are never a live region
    const item = document.createElement("span"); item.className = "ui-pulse-item";
    sr[k] = mk("ui-vh", `${cap(NAME[k])} --`);
    const vis = document.createElement("span"); vis.setAttribute("aria-hidden", "true");
    const b = document.createElement("b"); b.style.color = COL[k]; b.title = cap(NAME[k]);
    b.append(mk("ui-pw", NAME[k]), mk("ui-pl", LETTER[k]));
    const v = document.createElement("span"); v.textContent = "--"; num[k] = v;
    vis.append(b, " ", v); item.append(sr[k], vis);
    if (i) row.append(mk("ui-pulse-sep", " · ", {"aria-hidden":"true"}));
    row.append(item);
  });
  const spikeEl = mk("ui-pulse-spike", "", {"aria-hidden":"true"}), flashEl = mk("ui-pulse-flash", "", {"aria-hidden":"true"});
  vals.append(stageEl, row); root.append(cv, spikeEl, flashEl, vals); body.append(root);
  const ctx = cv.getContext("2d");

  // ---------------------------------------------------------------- state and readouts (per tick: arithmetic only)
  const S = {conn:null, viewers:null, stage:null, clock:"", tz:"Tokyo", syncS:0.1, first:0, last:0,
             gEma:{}, base:null, read:{a:50, r:50, l:50, n:50}, readS:{a:50, r:50, l:50, n:50}};
  const ring = [];                                   // {t, a, r, l, n}, one per tick, the last 60 s (+ a margin)
  const warm = now => S.first ? Math.min(1, (now - S.first) / WARM_MS) : 0;
  function onTick(m){
    const now = Date.now();
    S.last = now; if (!S.first) S.first = now;
    const k = 1 / (25 * RATE), w = warm(now);         // ~25 s EMA baselines; for the first 25 s rel leans towards 1
    const sl = m.sleep;
    if (sl && typeof sl === "object") { S.stage = sl.stage || S.stage; S.clock = sl.clock || S.clock; S.tz = sl.tz || "Tokyo"; }
    if (m.aud && typeof m.aud.n === "number") S.viewers = m.aud.n;
    if (typeof m.sync === "number" && isFinite(m.sync)) S.syncS += (m.sync - S.syncS) * 0.1;
    // per-region activity (aq: one byte a region, log-quantised) vs its own baseline
    let neural = NaN;
    if (typeof m.aq === "string") {
      try {
        const bin = atob(m.aq), n = bin.length;
        if (n) {
          if (!S.base || S.base.length !== n) S.base = Float32Array.from({length:n}, (_, i) => ACT_LUT[bin.charCodeAt(i)]);
          let s = 0;
          for (let i = 0; i < n; i++) {
            const a = ACT_LUT[bin.charCodeAt(i)];
            S.base[i] = S.base[i] * (1 - k) + a * k;
            s += a / Math.max(S.base[i], 0.02);
          }
          neural = R(1 + (s / n - 1) * w);
        }
      } catch (e) { /* a malformed aq: skip the neural line this tick */ }
    }
    // network levels vs their own baseline
    const grel = {}, groups = m.groups && typeof m.groups === "object" ? m.groups : null;
    if (groups) for (const g in groups) {
      const v = +groups[g]; if (!isFinite(v)) continue;
      const e = S.gEma[g] = S.gEma[g] === undefined ? Math.max(v, 1e-3) : S.gEma[g] * (1 - k) + v * k;
      grel[g] = 1 + (v / Math.max(e, 1e-3) - 1) * w;
    }
    const pick = ks => ks.map(g => grel[g]).filter(v => isFinite(v));
    const att = pick(["attention", "salience", "visual"]), ctl = pick(["control", "default"]);
    const nm = m.neuro && typeof m.neuro === "object" ? m.neuro : {}, rd = S.read;
    if (att.length) rd.a = R(mean(att));
    if (+nm.NE > 0) rd.r = clamp(50 + 30 * Math.log2(+nm.NE));
    if (ctl.length) rd.l = isFinite(+nm.ACh) ? 0.7 * R(mean(ctl)) + 0.3 * clamp(+nm.ACh / 2 * 100) : R(mean(ctl));
    else if (isFinite(+nm.ACh)) rd.l = clamp(+nm.ACh / 2 * 100);
    if (isFinite(neural)) rd.n = neural;
    const sm = S.readS;
    for (const key of KEYS) sm[key] += (rd[key] - sm[key]) * 0.25;
    ring.push({t:now, a:sm.a, r:sm.r, l:sm.l, n:sm.n});
    while (ring.length && now - ring[0].t > WIN_MS + 2000) ring.shift();
    if (!S.conn) setConn(true);
    dirtyText = true;
  }

  // ---------------------------------------------------------------- header: clock and live chip
  const shown = {};
  const put = (el, key, t) => { if (el && shown[key] !== t) { shown[key] = t; el.textContent = t; } };
  let dirtyText = true;
  function setConn(on){ S.conn = on; dirtyText = true; renderText(); }
  function renderText(){
    if (!dirtyText) return; dirtyText = false;
    const live = $("ui-live");
    if (S.conn !== null) {                            // null: still connecting, the chip keeps its markup
      if (live) live.classList.toggle("off", !S.conn);
      put($("ui-live-t"), "live", S.conn ? `live${typeof S.viewers === "number" ? ` · ${S.viewers} watching` : ""}` : "offline");
    }
    if (S.clock) put($("ui-clock"), "clock", `${S.clock} ${S.tz || "Tokyo"}`);
    const st = S.stage && STAGE[S.stage];
    stageEl.hidden = !st; if (st) put(stageEl, "stage", st);
    if (S.last) for (const k of KEYS) { const t = String(Math.round(S.readS[k]));
      put(num[k], k, t); put(sr[k], "s" + k, `${cap(NAME[k])} ${t}`); }
  }

  // ---------------------------------------------------------------- drawing: 10 fps, nothing while hidden
  let W = 0, H = 0, D = 1;
  function resize(){
    const r = cv.getBoundingClientRect(); D = Math.min(2, window.devicePixelRatio || 1);
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    cv.width = Math.round(W * D); cv.height = Math.round(H * D);
  }
  // 10..90 spans the strip (50, the baseline, in the middle); crisp 1 px lines
  const yOf = v => Math.round(3 + (1 - (clamp(v, 10, 90) - 10) / 80) * (H - 6)) + 0.5;
  function draw(){
    if (!W) resize();
    ctx.setTransform(D, 0, 0, D, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.lineWidth = 1;
    // 50 = his own baseline: a faint dashed line
    ctx.globalAlpha = 1; ctx.strokeStyle = "rgba(255,255,255,.16)"; ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(0, yOf(50)); ctx.lineTo(W, yOf(50)); ctx.stroke(); ctx.setLineDash([]);
    if (ring.length < 2) return;
    const now = Date.now();
    // the strip breathes with the network synchrony: opacity ±8 %, a 4 s cycle (off under reduced motion)
    const amp = RM.matches ? 0 : 0.08 * clamp(S.syncS / 0.25, 0.3, 1);
    ctx.globalAlpha = (S.conn ? 0.92 : 0.45) + amp * Math.sin(now / 4000 * 2 * Math.PI);
    ctx.lineJoin = "round";
    for (const key of ["n", "l", "r", "a"]) {        // attention last: on top
      ctx.strokeStyle = COL[key]; ctx.beginPath();
      let started = false;
      for (let i = 0; i < ring.length; i++) {
        const p = ring[i], x = W - (now - p.t) / WIN_MS * W;
        if (x < -4) continue;
        if (!started) { ctx.moveTo(x, yOf(p[key])); started = true; } else ctx.lineTo(x, yOf(p[key]));
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  let lastDraw = 0;
  function frame(){
    if (document.hidden) return;
    const now = performance.now();
    if (RM.matches && now - lastDraw < 1000) { renderText(); return; }   // reduced motion: the strip steps once a second
    lastDraw = now;
    renderText(); draw();
  }
  setInterval(frame, 1000 / FPS);
  addEventListener("resize", () => { W = 0; });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { W = 0; dirtyText = true; frame(); } });

  // ---------------------------------------------------------------- the spike: someone sent a stimulus
  // a 24 px bright pulse travels the strip left to right in 900 ms (ease-out) and fades; under reduced motion the whole
  // strip flashes for 300 ms. A second call within 500 ms is the same stimulus (the sender's page and the echo): ignored.
  let spikeAt = 0;
  function spike(){
    try {
      const now = performance.now();
      if (document.hidden || now - spikeAt < 500 || !spikeEl.animate) return;
      spikeAt = now;
      if (RM.matches) { flashEl.animate([{opacity:1}, {opacity:0}], {duration:300, easing:"ease-out"}); return; }
      const w = Math.max(24, root.clientWidth || window.innerWidth);
      spikeEl.animate([
        {transform:"translateX(-24px)", opacity:1, easing:"ease-out"},
        {transform:`translateX(${w}px)`, opacity:1, offset:.82},
        {transform:`translateX(${w}px)`, opacity:0}
      ], {duration:1100, easing:"linear"});
    } catch (e) { /* the strip is decoration: never throw */ }
  }

  // ---------------------------------------------------------------- the socket (or the page's own, in feed mode)
  function handle(m){
    if (!m || typeof m !== "object") return;
    if (m.type === "tick") { retry = 0; onTick(m); }
    else if (m.type === "chat") spike();
    else if (m.type === "full") { full = (+m.retry > 0 ? +m.retry : 30) * 1000; }
  }
  let retry = 0, full = 0, ws = null;
  function connect(){
    try { ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?rate=${RATE}&q=1`); }
    catch (e) { schedule(); return; }
    ws.onopen = () => setConn(true);
    ws.onmessage = e => { let m; try { m = JSON.parse(e.data); } catch (err) { return; } handle(m); };
    ws.onclose = () => { ws = null; setConn(false); schedule(); };
  }
  function schedule(){
    // 1.5 s doubling to 30 s, with jitter; "full" waits at least what the server asked
    const wait = Math.max(full, Math.min(30000, 1500 * 2 ** retry)) * (0.75 + 0.5 * Math.random());
    retry = Math.min(retry + 1, 5); full = 0;
    setTimeout(connect, wait);
  }
  const feedMode = body.getAttribute("data-pulse") === "feed";
  window.SUB01Pulse = Object.freeze({
    feed: m => { try { handle(m); } catch (e) {} },                  // feed mode: the page's messages
    online: on => { if (!on) setConn(false); },                         // feed mode: the page's socket closed (a tick reopens)
    spike,                                                              // a bright pulse along the strip (any page, any time)
    read: () => ({...S.readS, stage:S.stage, clock:S.clock, tz:S.tz, viewers:S.viewers, conn:S.conn}),
  });
  renderText();
  if (!feedMode) connect();
})();
