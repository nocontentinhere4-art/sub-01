// Phone overlay (hud stream). SUB-01's simulated phone is a HUD overlay only (the construct has no 3D phone prop): when
// life.phone is set (lying in bed, scrolling) a compact phone screen shows what it is looking at.
//
// createPhone() -> {overlayEl, update(state), setApp(app), pushTrades(trades), feed, drawOrderFlow}
//   overlayEl     element main.js mounts into #phone-overlay (the container sizes it); main.js toggles
//                 #phone-overlay.on with state.visible. Tap/click the screen = enlarge, x = close (comes back with the
//                 next phone session), esc / backdrop = shrink.
//   update(state) called every frame; state = {app: "chart"|"chat"|"tiktok"|null, visible, asleep, pool, flow: [number],
//                 chat: [{t, text, nick?}], clock, candles?}. Redraws are throttled here (2 Hz).
//   setApp(app)   force an app (screenshots / tests); null = follow the life snapshot. URL ?phoneapp=chart|chat|tiktok
//                 does the same.
//   pushTrades(trades)  optional: raw tick.trades ([{kind, usd}]) for real time-bucketed candles. Without it the chart is
//                 built from state.flow (the cumulative flow main.js already keeps), so nothing has to be wired for it.
// chart: NET ORDER FLOW of its pool from the trade stream (trades carry no price): candles of cumulative signed volume.
// chat: the latest accepted chat lines, drawn on a canvas (never as HTML).
// tiktok: ONLY the official embed (https://www.tiktok.com/embed/v2/<id>) of URLs listed in /phone_feed.json (curated,
// validated, see docs/real-world/PHONE.md); videos are never downloaded or re-hosted. An empty list shows
// "No curated videos yet" and nothing is ever requested from tiktok.com. The embed only loads after the viewer enlarges
// the phone. The phone is a stage prop of a simulation: nothing on it claims the model is alive or a person.
import { validateFeed, embedSrc, candlesFromFlow, TradeAggregator, drawOrderFlow, drawChatApp, drawCard, drawLock } from "./phone_util.js";

export { drawOrderFlow, validateFeed, candlesFromFlow };

const APPS = ["chart", "chat", "tiktok"];
const OV_W = 540, OV_H = 930;

const CSS = `
.phone-ov{position:relative;width:100%;height:100%;box-sizing:border-box;border-radius:20px;background:#0b0b10;border:3px solid #2a2a36;
  box-shadow:0 10px 40px rgba(0,0,0,.6),0 0 0 1px rgba(255,106,0,.25);padding:24px 5px 6px;font:11px/1.2 ui-monospace,Menlo,Consolas,monospace;
  color:#b5b5c4;touch-action:manipulation}
.phone-ov .pv-top{position:absolute;top:0;left:0;right:0;height:24px;display:flex;align-items:center;gap:2px;padding:0 3px 0 10px;
  font-size:9px;color:#80808f;white-space:nowrap}
.phone-ov .pv-title{flex:1;overflow:hidden;text-overflow:ellipsis}
.phone-ov button{background:transparent;border:0;color:#b5b5c4;font:inherit;font-size:14px;line-height:1;min-width:26px;min-height:24px;cursor:pointer;padding:0 3px}
.phone-ov button:hover,.phone-ov button:focus-visible{color:#ff6a00;outline:0}
.phone-ov .pv-screen{position:relative;width:100%;height:100%;border-radius:12px;overflow:hidden;background:#000;cursor:pointer}
.phone-ov canvas,.phone-ov iframe{position:absolute;inset:0;width:100%;height:100%;display:block;border:0}
.phone-ov iframe{display:none;background:#000}
.phone-ov.tt-open iframe{display:block}
.phone-ov .pv-next{display:none}.phone-ov.tt-open .pv-next{display:inline}
.phone-ov.closed{display:none}
.phone-ov.big{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(92vw,380px);height:min(80vh,680px);z-index:60;padding-top:32px;border-radius:26px}
.phone-ov.big .pv-top{height:32px;font-size:12px}.phone-ov.big button{font-size:18px;min-height:32px;min-width:36px}
.phone-bd{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:49;display:none}.phone-bd.on{display:block}
`;

export function createPhone() {
  const ovCv = Object.assign(document.createElement("canvas"), { width: OV_W, height: OV_H });
  const ovCtx = ovCv.getContext("2d");

  if (!document.getElementById("phone-css")) { const s = document.createElement("style"); s.id = "phone-css"; s.textContent = CSS; document.head.appendChild(s); }
  const overlayEl = document.createElement("div"); overlayEl.className = "phone-ov";
  overlayEl.setAttribute("role", "region"); overlayEl.setAttribute("aria-label", "SUB-01's simulated phone");
  const mkBtn = (cls, txt, label) => { const b = document.createElement("button"); b.type = "button"; b.className = cls; b.textContent = txt; b.setAttribute("aria-label", label); b.title = label; return b; };
  const top = document.createElement("div"); top.className = "pv-top";
  const title = document.createElement("span"); title.className = "pv-title";
  const bNext = mkBtn("pv-next", "›", "next curated video"), bBig = mkBtn("", "⤢", "enlarge phone"), bClose = mkBtn("", "×", "close phone");
  top.append(title, bNext, bBig, bClose);
  const screen = document.createElement("div"); screen.className = "pv-screen";
  ovCv.setAttribute("role", "img");
  screen.appendChild(ovCv);
  overlayEl.append(top, screen);
  const backdrop = document.createElement("div"); backdrop.className = "phone-bd";

  let iframe = null;
  function showEmbed(id) {
    if (!iframe) {
      iframe = document.createElement("iframe"); iframe.title = "TikTok (official embed)";
      iframe.setAttribute("allow", "encrypted-media; fullscreen"); iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
      iframe.setAttribute("sandbox", "allow-scripts allow-same-origin allow-popups allow-presentation");
      screen.appendChild(iframe);
    }
    const src = embedSrc(id);
    if (iframe.getAttribute("src") !== src) iframe.setAttribute("src", src);
    overlayEl.classList.add("tt-open");
  }
  function hideEmbed() { overlayEl.classList.remove("tt-open"); if (iframe) iframe.removeAttribute("src"); }

  const params = new URLSearchParams(location.search);
  const pinned = APPS.includes(params.get("phoneapp")) ? params.get("phoneapp") : null;   // ?phoneapp= wins over setApp()
  let forced = pinned;
  let feed = [], feedLoaded = false, vid = -1;
  let home = null, big = false, dismissed = false, wasVisible = false, lastDraw = 0, lastApp = null;
  const agg = new TradeAggregator(4, 48);
  const dbg = (window.__phone = { app: null, feed: 0, feedErrors: [], embed: null, visible: false });

  fetch("/phone_feed.json", { cache: "no-store" }).then(r => (r.ok ? r.json() : [])).catch(() => [])
    .then(j => {
      const v = validateFeed(j); feed = v.items; feedLoaded = true; dbg.feed = feed.length; dbg.feedErrors = v.errors;
      if (v.errors.length) console.warn("[phone] phone_feed.json: " + v.errors.join("; "));
    });

  function setBig(on) {
    big = on; overlayEl.classList.toggle("big", on); backdrop.classList.toggle("on", on);
    if (on) { home = overlayEl.parentNode; document.body.append(backdrop, overlayEl); }   // above every other overlay
    else { backdrop.remove(); if (home) home.appendChild(overlayEl); hideEmbed(); }
    bBig.textContent = on ? "⤡" : "⤢"; bBig.setAttribute("aria-label", on ? "shrink phone" : "enlarge phone");
    lastDraw = 0;
  }
  bBig.onclick = () => setBig(!big);
  screen.onclick = () => { if (!big) setBig(true); };
  backdrop.onclick = () => setBig(false);
  bClose.onclick = () => { if (big) setBig(false); dismissed = true; overlayEl.classList.add("closed"); };
  bNext.onclick = () => { if (feed.length) vid = (vid + 1) % feed.length; lastDraw = 0; };
  addEventListener("keydown", e => { if (e.key === "Escape" && big) setBig(false); });

  const candlesOf = state => {
    if (Array.isArray(state.candles) && state.candles.length) return state.candles;
    const a = agg.list(); return a.length >= 2 ? a : candlesFromFlow(state.flow);
  };
  function drawApp(ctx, W, H, app, state, cd) {
    if (app === "chat") return drawChatApp(ctx, W, H, state.chat);
    if (app === "tiktok") {
      const item = feed[vid];
      if (!feed.length) return drawCard(ctx, W, H, "tiktok", [feedLoaded ? "No curated videos yet" : "loading…"], "the curated list is empty");
      return drawCard(ctx, W, H, "tiktok", [item && item.note ? item.note : "curated video"], "tap to enlarge · official TikTok embed");
    }
    return drawOrderFlow(ctx, W, H, { pool: state.pool, candles: cd });
  }

  function update(state) {
    const now = performance.now();
    const app = state.asleep && !forced ? null : (forced || state.app || null);
    const visible = !!state.visible && !(state.asleep && !forced);
    dbg.app = app; dbg.visible = visible;
    // auto-hide when the phone is not in use; a closed phone comes back with the next phone session
    if (visible !== wasVisible) {
      wasVisible = visible;
      if (!visible) { dismissed = false; overlayEl.classList.remove("closed"); if (big) setBig(false); hideEmbed(); }
      else lastDraw = 0;
    }
    // a new tiktok session advances to the next curated video
    if (app !== lastApp) { if (app === "tiktok" && feed.length) vid = (vid + 1) % feed.length; lastApp = app; lastDraw = 0; }
    if (now - lastDraw < 500) return;              // 2 Hz is plenty for a chart and a chat list
    lastDraw = now;
    if (vid < 0 && feed.length) vid = 0;
    if (feed.length && vid >= feed.length) vid = 0;
    if (!visible || dismissed) return;
    title.textContent = app ? `phone · ${app}${app === "tiktok" && feed[vid] ? ` ${vid + 1}/${feed.length}` : ""}` : "phone · idle";
    ovCv.setAttribute("aria-label", `Phone screen: ${app || "idle"}`);
    if (app) drawApp(ovCtx, OV_W, OV_H, app, state, candlesOf(state)); else drawLock(ovCtx, OV_W, OV_H, state.clock);
    if (big && app === "tiktok" && feed[vid]) { dbg.embed = embedSrc(feed[vid].id); showEmbed(feed[vid].id); }
    else { if (overlayEl.classList.contains("tt-open")) hideEmbed(); dbg.embed = null; }
  }

  return {
    overlayEl, update,
    setApp(app) { if (pinned) return; forced = APPS.includes(app) ? app : null; lastDraw = 0; },
    pushTrades(trades) { agg.push(trades, performance.now() / 1000); },
    get feed() { return feed.slice(); },
    drawOrderFlow,
  };
}
