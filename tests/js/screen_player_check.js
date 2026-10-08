// web/room/screen_player.js in node with a stubbed DOM (no browser): the official embed URLs, the iframe replaced only
// when the video changes, the player's onError reported once per video (id + code only, rate-limited), messages from
// other origins or frames ignored, and the "playing" canvas drawn. Run by tests/test_screen_player.py; prints JSON.
import { nowWatching, embedSrc, playerError, createScreenPlayer, playingCanvas, REPORT_URL } from "../../web/room/screen_player.js";

const out = {};
const yt = {source: "youtube", id: "qpkTV1VolHU", title: "Grandmaster blunders", channel: "c", duration_s: 720, elapsed_s: 42};
const tt = {source: "tiktok", id: "6718335390845095173", title: "pets", channel: "scout2015", duration_s: null, elapsed_s: 0};
out.src_youtube = embedSrc(yt, "https://sub01.example", 42);
out.src_tiktok = embedSrc(tt, "https://sub01.example", 0);
out.rejects = [nowWatching({now_watching: {source: "youtube", id: "x\"><script>"}}), nowWatching({now_watching: {source: "vimeo", id: "123456789"}}),
               nowWatching({}), embedSrc({source: "youtube", id: "../evil/abc"}, "", 0)];
out.errors = {
  yt: playerError("youtube", "https://www.youtube-nocookie.com", JSON.stringify({event: "onError", info: 150})),
  yt_other_event: playerError("youtube", "https://www.youtube-nocookie.com", JSON.stringify({event: "infoDelivery", info: {}})),
  yt_wrong_origin: playerError("youtube", "https://evil.example", JSON.stringify({event: "onError", info: 150})),
  tt: playerError("tiktok", "https://www.tiktok.com", {type: "onError", value: {code: 1001}}),
  garbage: playerError("youtube", "https://www.youtube-nocookie.com", "not json"),
};

// the stub DOM
const listeners = {}, posts = [], appended = [];
function el(tag){
  const e = {tag, children: [], attrs: {}, listeners: {}, removed: false,
    classList: {s: new Set(), add(c){ this.s.add(c); }, remove(c){ this.s.delete(c); }, contains(c){ return this.s.has(c); }},
    setAttribute(k, v){ this.attrs[k] = v; }, addEventListener(t, f){ this.listeners[t] = f; },
    appendChild(c){ this.children.push(c); appended.push(c); c.parent = this; return c; },
    remove(){ this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); }};
  if (tag === "iframe") e.contentWindow = {posted: [], postMessage(m, o){ this.posted.push([m, o]); }};
  if (tag === "canvas") e.getContext = () => new Proxy({calls: 0}, {get(t, k){ if (k === "calls") return t.calls;
    if (k === "createLinearGradient") return () => ({addColorStop(){}}); return typeof k === "string" ? (...a) => { t.calls++; } : undefined; },
    set(){ return true; }});
  return e;
}
const doc = {createElement: el};
const win = {location: {origin: "https://sub01.example"}, addEventListener(t, f){ listeners[t] = f; }, removeEventListener(t){ delete listeners[t]; }};
let t = 1_000_000;
const frame = el("div"), errs = [];
const p = createScreenPlayer(frame, {win, doc, now: () => t, fetch: (u, o) => { posts.push([u, JSON.parse(o.body), o.method]); return Promise.resolve(); },
                                     onError: (nw, code) => errs.push([nw.id, code])});
out.shown = p.show({now_watching: yt}, t);
const f1 = p.iframe;
out.iframe = {src: f1.src, allow: f1.allow, referrer: f1.referrerPolicy, in_frame: frame.children.length === 1, playing: frame.classList.contains("playing")};
f1.listeners.load();
out.listening = f1.contentWindow.posted.map(([m, o]) => [JSON.parse(m).event, o]);
p.show({now_watching: yt, title: "same video, new status"}, t);
out.same_iframe_kept = p.iframe === f1 && appended.length === 1;
listeners.message({source: {}, origin: "https://www.youtube-nocookie.com", data: JSON.stringify({event: "onError", info: 150})});   // another frame
listeners.message({source: f1.contentWindow, origin: "https://evil.example", data: JSON.stringify({event: "onError", info: 150})});
out.ignored = posts.length === 0;
listeners.message({source: f1.contentWindow, origin: "https://www.youtube-nocookie.com", data: JSON.stringify({event: "onError", info: 150})});
listeners.message({source: f1.contentWindow, origin: "https://www.youtube-nocookie.com", data: JSON.stringify({event: "onError", info: 150})});
out.reported = posts;
out.on_error = errs;
// a new video replaces the iframe; the reports stay rate-limited (3 a minute)
for (const id of ["aaaaaaaaaa1", "aaaaaaaaaa2", "aaaaaaaaaa3"]) {
  p.show({now_watching: {...yt, id}}, t);
  listeners.message({source: p.iframe.contentWindow, origin: "https://www.youtube-nocookie.com", data: JSON.stringify({event: "onError", info: 5})});
}
out.reports_in_a_minute = posts.length;
t += 61_000;
p.show({now_watching: tt}, t);
listeners.message({source: p.iframe.contentWindow, origin: "https://www.tiktok.com", data: {type: "onError", value: 1}});
out.reports_after_a_minute = posts.length;
out.f1_removed = f1.removed;
p.show({title: "a web page"}, t);
out.hidden = p.iframe === null && frame.children.length === 0 && !frame.classList.contains("playing");
out.report_url = REPORT_URL;
const pc = playingCanvas(doc, {width: 1280, height: 720}, yt, 1024, 600);
out.canvas = {w: pc.canvas.width, h: pc.canvas.height, drew: pc.canvas.getContext("2d") !== null};
console.log(JSON.stringify(out));
