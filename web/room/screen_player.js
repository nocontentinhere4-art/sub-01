// #89 client player (2026-10-04): YouTube refuses playback to the server's IP, so the video his brain picked plays here,
// in the VIEWER's browser, in the site's official embed player: youtube-nocookie.com/embed (no cookies) or TikTok's
// tiktok.com/player/v1. Muted autoplay, never with sound. The server publishes "now watching" (source, id, title,
// channel, duration, elapsed) in the screen status; it never opens the player itself. When the player says it cannot
// play the video (its onError), the page tells the server (the id and the error code, nothing else) so his brain moves
// on. The 3D monitor shows the server's card (thumbnail, title) with a "playing" frame and the progress.
export const IDS = {youtube: /^[\w-]{11}$/, tiktok: /^\d{8,25}$/};
const ORIGINS = {youtube: "https://www.youtube-nocookie.com", tiktok: "https://www.tiktok.com"};
export const REPORT_URL = "/api/screen/video_error";
const REPORTS_PER_MIN = 3;

// what the screen status asks to play, checked: {source, id, title, channel, duration_s, elapsed_s} or null
export function nowWatching(st){
  const nw = st && st.now_watching;
  if (!nw || !IDS[nw.source] || !IDS[nw.source].test(String(nw.id || ""))) return null;
  return nw;
}

// the official embed URL for a checked now_watching (elapsed: seconds into the video)
export function embedSrc(nw, origin, elapsed){
  if (!nw || !IDS[nw.source] || !IDS[nw.source].test(String(nw.id))) return null;
  if (nw.source === "youtube") {
    const start = Math.max(0, Math.floor(+elapsed || 0));
    return `${ORIGINS.youtube}/embed/${nw.id}?autoplay=1&mute=1&playsinline=1&rel=0&enablejsapi=1`
      + `&origin=${encodeURIComponent(origin || "")}` + (start ? `&start=${start}` : "");
  }
  return `${ORIGINS.tiktok}/player/v1/${nw.id}?autoplay=1&muted=1&rel=0&description=1`;
}

// the error code in a message from the player, or null. YouTube's embed posts JSON strings
// ({"event":"onError","info":150}); TikTok's player posts objects ({type:"onError", value:...}).
export function playerError(source, origin, data){
  if (origin !== ORIGINS[source]) return null;
  let d = data;
  if (typeof d === "string") { try { d = JSON.parse(d); } catch (e) { return null; } }
  if (!d || typeof d !== "object") return null;
  if (source === "youtube" && d.event === "onError") return Number.isInteger(+d.info) ? +d.info : 0;
  if (source === "tiktok" && /error/i.test(String(d.type || d.event || ""))) {
    const v = d.value && typeof d.value === "object" ? d.value.code : d.value;
    return Number.isInteger(+v) ? +v : 0;
  }
  return null;
}

// the side panel's player: one iframe in `frame`, replaced only when the video changes.
// opts: {win, doc, fetch, now} for tests; report(id, code) is rate-limited and sent once per video.
export function createScreenPlayer(frame, opts = {}){
  const win = opts.win || window, doc = opts.doc || document, post = opts.fetch || ((u, o) => win.fetch(u, o));
  const now = opts.now || (() => Date.now());
  let iframe = null, cur = null, sent = new Set(), times = [];
  function report(nw, code){
    const t = now();
    times = times.filter(x => t - x < 60000);
    if (sent.has(nw.id) || times.length >= REPORTS_PER_MIN) return false;
    sent.add(nw.id); times.push(t);
    post(REPORT_URL, {method: "POST", headers: {"Content-Type": "application/json"}, credentials: "same-origin",
                      body: JSON.stringify({id: nw.id, code})}).catch(() => {});
    if (opts.onError) opts.onError(nw, code);
    return true;
  }
  function onMessage(ev){
    if (!cur || !iframe || ev.source !== iframe.contentWindow) return;
    const code = playerError(cur.source, ev.origin, ev.data);
    if (code !== null) report(cur, code);
  }
  win.addEventListener("message", onMessage);
  function hide(){
    if (iframe) { iframe.remove(); iframe = null; }
    cur = null; frame.classList.remove("playing");
  }
  function show(st, receivedAt){
    const nw = nowWatching(st);
    if (!nw) { hide(); return false; }
    if (cur && cur.id === nw.id && cur.source === nw.source && iframe) return true;
    hide();
    cur = nw;
    const lag = receivedAt ? (now() - receivedAt) / 1000 : 0;
    iframe = doc.createElement("iframe");
    iframe.className = "player " + nw.source;
    iframe.title = `${nw.source === "youtube" ? "YouTube" : "TikTok"} player: ${nw.title || ""}`;
    iframe.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    iframe.referrerPolicy = "strict-origin-when-cross-origin";     // the YouTube embed needs the page's origin
    iframe.setAttribute("allowfullscreen", "");
    iframe.addEventListener("load", () => {                        // ask the YouTube embed for its events
      if (cur && cur.source === "youtube" && iframe && iframe.contentWindow)
        iframe.contentWindow.postMessage(JSON.stringify({event: "listening", id: 1, channel: "widget"}), ORIGINS.youtube);
    });
    iframe.src = embedSrc(nw, win.location ? win.location.origin : "", (+nw.elapsed_s || 0) + lag);
    frame.appendChild(iframe);
    frame.classList.add("playing");
    return true;
  }
  return {show, hide, report, get current(){ return cur; }, get iframe(){ return iframe; },
          destroy(){ hide(); win.removeEventListener("message", onMessage); }};
}

function fmt(s){ s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }

// the 3D monitor / phone screen: the server's card image with a "playing" frame and the progress, on a canvas that
// update() redraws (the caller sets texture.needsUpdate). No request to the video site from the 3D view.
export function playingCanvas(doc, img, nw, w = 1024, h = 600){
  const c = doc.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d"), t0 = performance.now() / 1000 - (+nw.elapsed_s || 0);
  function update(){
    const el = performance.now() / 1000 - t0, dur = +nw.duration_s || 0, wSec = +nw.watch_s || dur;
    g.fillStyle = "#000"; g.fillRect(0, 0, w, h);
    if (img && img.width) {                                        // cover-fit the card's image
      const a = img.width / img.height, sw = a > w / h ? img.height * w / h : img.width, sh = a > w / h ? img.height : img.width * h / w;
      g.drawImage(img, (img.width - sw) / 2, 0, sw, sh, 0, 0, w, h);
    }
    const grd = g.createLinearGradient(0, h * 0.55, 0, h); grd.addColorStop(0, "rgba(0,0,0,0)"); grd.addColorStop(1, "rgba(0,0,0,.85)");
    g.fillStyle = grd; g.fillRect(0, h * 0.55, w, h * 0.45);
    g.lineWidth = Math.max(4, w / 200); g.strokeStyle = "rgba(255,72,72,.9)"; g.strokeRect(g.lineWidth / 2, g.lineWidth / 2, w - g.lineWidth, h - g.lineWidth);
    const tall = h > w, s = Math.round((tall ? w * 1.9 : h) / 22), up = tall ? s * 1.3 : 0;   // a phone: two lines
    g.fillStyle = "rgba(255,72,72,.95)"; g.beginPath(); g.moveTo(s * 1.2, h - s * 3.1 - up); g.lineTo(s * 1.2, h - s * 1.9 - up); g.lineTo(s * 2.2, h - s * 2.5 - up); g.fill();
    g.fillStyle = "#fff"; g.font = `bold ${s}px -apple-system,Helvetica,Arial,sans-serif`;
    g.fillText("PLAYING", s * 2.8, h - s * 2.1 - up);
    g.font = `${Math.round(s * 0.8)}px -apple-system,Helvetica,Arial,sans-serif`; g.fillStyle = "rgba(255,255,255,.75)";
    const total = dur || wSec;
    if (total) g.fillText(`${fmt(Math.min(el, total))} / ${fmt(total)} · muted`, tall ? s * 1.2 : s * 7.4, h - s * 2.1);
    const pw = w - s * 2.4, p = total ? Math.min(1, el / total) : 0;
    g.fillStyle = "rgba(255,255,255,.25)"; g.fillRect(s * 1.2, h - s * 1.2, pw, s * 0.25);
    g.fillStyle = "rgba(255,72,72,.95)"; g.fillRect(s * 1.2, h - s * 1.2, pw * p, s * 0.25);
    return c;
  }
  update();
  return {canvas: c, update};
}
