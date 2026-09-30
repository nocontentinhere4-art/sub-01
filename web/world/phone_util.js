// Pure helpers for the phone stream (no three.js, no DOM): feed validation, order-flow candles, canvas drawers.
// Imported by phone.js (which re-exports drawOrderFlow) and by tests/js/phone_util.test.mjs.

// ---------------------------------------------------------------- curated TikTok list
// web/phone_feed.json = [{"url": "https://www.tiktok.com/@user/video/<digits>", "note": "why it is on the list"}]
// Only these URLs are ever embedded (official embed player); videos are never downloaded or re-hosted.
export const TIKTOK_URL = /^https:\/\/www\.tiktok\.com\/@[A-Za-z0-9._-]{1,64}\/video\/(\d{8,25})$/;

// validateFeed(json) -> {items: [{url, id, note}], errors: [string]}; invalid or duplicate entries are dropped.
export function validateFeed(json) {
  const items = [], errors = [], seen = new Set();
  if (!Array.isArray(json)) return { items, errors: ["phone_feed.json must be a JSON array"] };
  json.forEach((e, i) => {
    const url = e && typeof e === "object" && typeof e.url === "string" ? e.url.trim() : "";
    const m = TIKTOK_URL.exec(url);
    if (!m) { errors.push(`#${i}: url must look like https://www.tiktok.com/@user/video/<digits>`); return; }
    if (seen.has(m[1])) { errors.push(`#${i}: duplicate video id`); return; }
    seen.add(m[1]);
    const note = typeof e.note === "string" ? e.note.replace(/[\u0000-\u001f]+/g, " ").trim().slice(0, 140) : "";
    items.push({ url, id: m[1], note });
  });
  return { items, errors };
}

// The only URL the overlay iframe may use for an id that came out of validateFeed.
export const embedSrc = id => `https://www.tiktok.com/embed/v2/${id}`;

// ---------------------------------------------------------------- order-flow candles
// Trades carry no price, so the chart shows NET ORDER FLOW: cumulative signed volume (buys up, sells down),
// grouped into candles (open/high/low/close of the cumulative line) with a volume bar per candle.
//   candle = {o, h, l, c, v (total volume), b (buy volume)}

// From a cumulative-flow series (one point per trade, as main.js keeps in `flow`): `group` points per candle.
export function candlesFromFlow(flow, group = 3, maxCandles = 48) {
  const out = [];
  if (!Array.isArray(flow) || flow.length < 2) return out;
  const n = flow.length;
  for (let end = n - 1; end >= 1 && out.length < maxCandles; end -= group) {
    const start = Math.max(1, end - group + 1);
    let h = -Infinity, l = Infinity, v = 0, b = 0;
    for (let i = start; i <= end; i++) {
      const d = flow[i] - flow[i - 1];
      h = Math.max(h, flow[i]); l = Math.min(l, flow[i]); v += Math.abs(d); if (d > 0) b += d;
    }
    const o = flow[start - 1];
    out.unshift({ o, h: Math.max(h, o), l: Math.min(l, o), c: flow[end], v, b });
  }
  return out;
}

// Streaming aggregator for raw trades ({kind: "buy"|"sell", usd}); buckets of `bucketSec` seconds.
export class TradeAggregator {
  constructor(bucketSec = 4, maxCandles = 48) { this.bucket = bucketSec; this.max = maxCandles; this.cum = 0; this.candles = []; this.cur = null; this.curT = -1; }
  push(trades, nowSec) {
    for (const t of trades || []) {
      const usd = Number(t && t.usd); if (!(usd > 0)) continue;
      const d = (t.kind === "buy" ? 1 : -1) * usd, slot = Math.floor(nowSec / this.bucket);
      if (!this.cur || slot !== this.curT) { this.flush(); this.cur = { o: this.cum, h: this.cum, l: this.cum, c: this.cum, v: 0, b: 0 }; this.curT = slot; }
      this.cum += d; const c = this.cur; c.c = this.cum; c.h = Math.max(c.h, this.cum); c.l = Math.min(c.l, this.cum); c.v += usd; if (d > 0) c.b += usd;
    }
  }
  flush() { if (this.cur) { this.candles.push(this.cur); if (this.candles.length > this.max) this.candles.shift(); this.cur = null; } }
  list() { return this.cur ? this.candles.concat([{ ...this.cur }]) : this.candles.slice(); }
}

// ---------------------------------------------------------------- canvas drawers
const C = { bg: "#07080c", grid: "#1a1c26", dim: "#80808f", fg: "#ececf2", up: "#39f5a0", down: "#ff4d6d", accent: "#ff6a00", ink: "#0a0a0a" };
export const PHONE_COLORS = C;
const MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace";

// Fit text into lines of at most `maxW` px (canvas measureText), at most `maxLines` (last one gets an ellipsis).
export function wrapText(ctx, text, maxW, maxLines = 99) {
  const lines = []; let line = "";
  for (const w of String(text).split(/\s+/).filter(Boolean)) {
    let word = w;
    while (ctx.measureText(word).width > maxW && word.length > 1) {          // a single very long word
      let k = word.length; while (k > 1 && ctx.measureText(word.slice(0, k)).width > maxW) k--;
      if (line) { lines.push(line); line = ""; }
      lines.push(word.slice(0, k)); word = word.slice(k);
    }
    const tryLine = line ? line + " " + word : word;
    if (ctx.measureText(tryLine).width > maxW && line) { lines.push(line); line = word; } else line = tryLine;
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] = lines[maxLines - 1].replace(/.{0,2}$/, "") + "…"; }
  return lines;
}

// Reusable order-flow chart (phone screen, phone overlay, desk monitor).
//   data = {title?: string, pool?: string, candles: [{o,h,l,c,v,b}], header?: bool (default true)}
// Draws over the whole w x h area; text scales with the canvas size.
export function drawOrderFlow(ctx, w, h, data = {}) {
  const u = Math.max(0.6, Math.min(w / 360, h / 300));
  const candles = (data.candles || []).slice(-60);
  ctx.save();
  ctx.fillStyle = C.bg; ctx.fillRect(0, 0, w, h);
  const headH = data.header === false ? 0 : Math.round(34 * u);
  if (headH) {
    ctx.fillStyle = C.accent; ctx.fillRect(0, 0, w, headH);
    ctx.fillStyle = C.ink; ctx.font = `bold ${Math.round(17 * u)}px ${MONO}`; ctx.textBaseline = "middle";
    ctx.fillText(`${data.pool || data.title || "order flow"} · net order flow`.slice(0, Math.floor(w / (10 * u))), 10 * u, headH / 2 + 1);
  }
  const pad = 10 * u, x0 = pad, x1 = w - pad;
  const footH = Math.round(24 * u), volH = Math.round((h - headH) * 0.22);
  const pTop = headH + 12 * u, pBot = h - footH - volH - 8 * u, vTop = pBot + 6 * u, vBot = h - footH;
  // grid
  ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) { const y = pTop + (pBot - pTop) * i / 4; ctx.beginPath(); ctx.moveTo(x0, y + .5); ctx.lineTo(x1, y + .5); ctx.stroke(); }
  if (candles.length < 2) {
    ctx.fillStyle = C.dim; ctx.font = `${Math.round(14 * u)}px ${MONO}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("waiting for trades…", w / 2, (pTop + pBot) / 2); ctx.restore(); return;
  }
  let lo = Infinity, hi = -Infinity, vmax = 0, buy = 0, tot = 0;
  for (const c of candles) { lo = Math.min(lo, c.l); hi = Math.max(hi, c.h); vmax = Math.max(vmax, c.v); buy += c.b; tot += c.v; }
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const padR = (hi - lo) * 0.06; lo -= padR; hi += padR;
  const slot = (x1 - x0) / Math.max(24, candles.length), bw = Math.max(2, slot * 0.68);
  const Y = v => pTop + (pBot - pTop) * (1 - (v - lo) / (hi - lo));
  candles.forEach((c, i) => {
    const cx = x0 + slot * (i + 0.5), up = c.c >= c.o, col = up ? C.up : C.down;
    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = Math.max(1, u);
    ctx.beginPath(); ctx.moveTo(cx, Y(c.h)); ctx.lineTo(cx, Y(c.l)); ctx.stroke();
    const yo = Y(c.o), yc = Y(c.c); ctx.fillRect(cx - bw / 2, Math.min(yo, yc), bw, Math.max(2, Math.abs(yo - yc)));
    // volume bar: green part = buys, red part = sells
    const vh = vmax > 0 ? (vBot - vTop) * c.v / vmax : 0, bh = c.v > 0 ? vh * c.b / c.v : 0;
    ctx.fillStyle = C.down; ctx.globalAlpha = 0.75; ctx.fillRect(cx - bw / 2, vBot - vh, bw, vh - bh);
    ctx.fillStyle = C.up; ctx.fillRect(cx - bw / 2, vBot - bh, bw, bh); ctx.globalAlpha = 1;
  });
  // last value line + footer
  const last = candles[candles.length - 1], ly = Y(last.c);
  ctx.setLineDash([4 * u, 4 * u]); ctx.strokeStyle = C.dim; ctx.beginPath(); ctx.moveTo(x0, ly); ctx.lineTo(x1, ly); ctx.stroke(); ctx.setLineDash([]);
  ctx.font = `${Math.round(12 * u)}px ${MONO}`; ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.fillStyle = C.dim; ctx.fillText("volume", x0, vTop + 11 * u);
  const share = tot > 0 ? Math.round(100 * buy / tot) : 50;
  ctx.fillStyle = share >= 50 ? C.up : C.down; ctx.fillText(`buys ${share}% · sells ${100 - share}%`, x0, h - 7 * u);
  ctx.textAlign = "right"; ctx.fillStyle = C.dim; ctx.fillText(`${candles.length} candles`, x1, h - 7 * u);
  ctx.restore();
}

// Chat list app: lines = [{t, text, nick?}] (newest last). Text is drawn on a canvas, never as HTML.
export function drawChatApp(ctx, w, h, lines) {
  const u = w / 360;
  ctx.save();
  ctx.fillStyle = "#0a0a10"; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = C.accent; ctx.fillRect(0, 0, w, 38 * u);
  ctx.fillStyle = C.ink; ctx.font = `bold ${Math.round(18 * u)}px ${MONO}`; ctx.textBaseline = "middle"; ctx.fillText("chat", 12 * u, 20 * u);
  const items = (lines || []).slice(-12), bodyFont = `${Math.round(15 * u)}px ${MONO}`, nameFont = `${Math.round(12 * u)}px ${MONO}`;
  // lay out from the bottom (newest) upwards so the latest message is always visible
  let y = h - 12 * u; ctx.textBaseline = "alphabetic";
  const blocks = [];
  for (let i = items.length - 1; i >= 0; i--) {
    ctx.font = bodyFont; const ls = wrapText(ctx, items[i].text, w - 34 * u, 4), bh = ls.length * 19 * u + 20 * u + 10 * u;
    if (y - bh < 44 * u) break; y -= bh; blocks.push({ m: items[i], ls, y });
  }
  if (!blocks.length) { ctx.fillStyle = C.dim; ctx.font = bodyFont; ctx.textAlign = "center"; ctx.fillText("no messages yet", w / 2, h / 2); ctx.restore(); return; }
  for (const b of blocks) {
    ctx.textAlign = "left"; ctx.font = nameFont; ctx.fillStyle = C.dim;
    ctx.fillText(`${b.m.t || ""}${b.m.nick ? "  " + b.m.nick : ""}`.trim(), 14 * u, b.y + 13 * u);
    ctx.fillStyle = "#15151f"; const bubbleH = b.ls.length * 19 * u + 8 * u;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(10 * u, b.y + 18 * u, w - 20 * u, bubbleH, 8 * u) : ctx.rect(10 * u, b.y + 18 * u, w - 20 * u, bubbleH); ctx.fill();
    ctx.font = bodyFont; ctx.fillStyle = C.fg; b.ls.forEach((l, k) => ctx.fillText(l, 17 * u, b.y + 18 * u + 17 * u + k * 19 * u));
  }
  ctx.restore();
}

// Card for the tiktok app: neutral on purpose (cross-origin iframes cannot be textures and the video is never re-hosted).
export function drawCard(ctx, w, h, title, lines, foot) {
  const u = w / 360;
  ctx.save();
  ctx.fillStyle = "#0a0a10"; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = C.accent; ctx.fillRect(0, 0, w, 38 * u);
  ctx.fillStyle = C.ink; ctx.font = `bold ${Math.round(18 * u)}px ${MONO}`; ctx.textBaseline = "middle"; ctx.textAlign = "left"; ctx.fillText(title, 12 * u, 20 * u);
  ctx.fillStyle = "#15151f"; const cy = h * 0.30, ch = h * 0.34;
  ctx.beginPath(); ctx.roundRect ? ctx.roundRect(24 * u, cy, w - 48 * u, ch, 14 * u) : ctx.rect(24 * u, cy, w - 48 * u, ch); ctx.fill();
  // play triangle
  ctx.fillStyle = C.accent; ctx.beginPath(); const px = w / 2, py = cy + ch * 0.36, r = 22 * u;
  ctx.moveTo(px - r * 0.7, py - r); ctx.lineTo(px + r, py); ctx.lineTo(px - r * 0.7, py + r); ctx.closePath(); ctx.fill();
  ctx.textAlign = "center"; ctx.textBaseline = "alphabetic"; ctx.font = `${Math.round(14 * u)}px ${MONO}`; ctx.fillStyle = C.fg;
  let ty = cy + ch * 0.72;
  for (const l of lines) for (const s of wrapText(ctx, l, w - 80 * u, 3)) { ctx.fillText(s, w / 2, ty); ty += 18 * u; }
  if (foot) { ctx.fillStyle = C.dim; ctx.font = `${Math.round(11 * u)}px ${MONO}`; ctx.fillText(foot, w / 2, h - 14 * u); }
  ctx.restore();
}

// Lock screen: the phone is lying around / asleep. Shows only the clock.
export function drawLock(ctx, w, h, clock) {
  const u = w / 360;
  ctx.save(); ctx.fillStyle = "#050507"; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#3a3a48"; ctx.font = `bold ${Math.round(54 * u)}px ${MONO}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(clock || "--:--", w / 2, h * 0.36); ctx.restore();
}
