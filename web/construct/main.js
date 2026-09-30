// Life page entry: "the construct" (core stream). SUB-01 lives inside a world built from its own brain data.
// Boots the renderer, the websocket client and the render loop and wires the stream modules together. Each stream only
// replaces its own file (see docs/real-world/CONTRACT.md):
//   data.js     loadBrainData(quality) -> districts / roads / graph / pathBetween / placeDistrict (core)
//   city.js     createCity(scene, data, quality) -> {update(dt, env, act), flash(regions, color), setFear(k), object}
//   travel.js   createTravel(camera, controls, data, {scene}) -> {update(dt, life, env), setView(v), view}
//   fx.js       createFx(renderer, scene, camera, data, quality) -> {rain, innerLine, weather, update(dt, env), render()}
//   ../world/hud.js, minibrain.js, phone.js, net.js, quality.js   reused from the foundation
//
// Render loop hooks, in this fixed order every frame: city.update(dt, env, act), travel.update(dt, life, env),
// fx.update(dt, env), phone.update(state), hud.update(dt, env), minibrain.update(dt, env), then fx.render().
//   env  = {romeHour, dayK, night, stage, lab, sleep, quality, market, groups, groupRel, groupSelf, time, view, follow, replays,
//           walking}
//          market: "pumping" | "dumping" | "choppy" | "calm" (tick.market, or derived here from the trades)
//          groupRel: group activity / mean of the groups (1 = average); groupSelf: group activity / its own running
//          baseline (1 = usual); replays: [{text, t, seq}] (REM replay events, last 30)
//   act  = Float32Array per brain region: tick.act relative to the region's running baseline, normalised to the global
//          mean (1 = usual), null before the first tick. Updated in place (no per-frame allocation).
//   life = tick.life + {stage}; route / progress are filled in from the waypoint graph if the server does not send them.
// Messages: chat -> hud.chat + fx.rain + city.flash + minibrain.flash; speech -> hud.speech + fx.innerLine (with the chat
// it answers); tick.market -> fx.weather (on change); tick.groups -> city.setFear.
// URL params: ?view=first|orbit  ?q=low|medium|high  ?nofollow=1   (key "v" toggles the view)
// window.__sub01 = {ready, fps, drawCalls, triangles, quality, connected, view, districts, fibres}
// It is a model of brain activity, not a mind.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { connect } from "../world/net.js";
import { Quality } from "../world/quality.js";
import { createPhone } from "../world/phone.js";
import { createHud } from "../world/hud.js";
import { createMiniBrain } from "../world/minibrain.js";
import { loadBrainData } from "./data.js";
import { createCity } from "./city.js";
import { createTravel } from "./travel.js";
import { createFx } from "./fx.js";

const params = new URLSearchParams(location.search);
const $ = id => document.getElementById(id);
let view = params.get("view") === "orbit" ? "orbit" : "first";
const follow = params.get("nofollow") !== "1";
const stats = (window.__sub01 = { ready: false, fps: 0, drawCalls: 0, triangles: 0, quality: null, connected: false, view,
  districts: 0, fibres: 0 });

// life.py layout (hello.world): used only to time walks when tick.life has no route / progress yet
const FALLBACK_WORLD = {
  places: { bed: [1.6, 1.3], window: [4.0, 0.9], table: [6.3, 4.2], desk: [6.5, 1.6], door_in: [4.0, 5.4], door_out: [4.0, 6.9],
    street_home: [4.0, 10.0], street_bakery: [21.0, 10.0], bakery_door: [21.0, 13.0], bakery_in: [21.0, 15.2], counter: [21.0, 16.4],
    street_park: [-13.0, 10.0], park_gate: [-13.0, 13.4], bench: [-13.0, 17.4] },
  edges: [["bed", "window"], ["bed", "table"], ["bed", "desk"], ["bed", "door_in"], ["window", "table"], ["window", "desk"],
    ["window", "door_in"], ["table", "desk"], ["table", "door_in"], ["desk", "door_in"], ["door_in", "door_out"],
    ["door_out", "street_home"], ["street_home", "street_bakery"], ["street_home", "street_park"], ["street_bakery", "bakery_door"],
    ["bakery_door", "bakery_in"], ["bakery_in", "counter"], ["street_park", "park_gate"], ["park_gate", "bench"]],
};
const ACT_PLACE = { sleep: "bed", phone: "bed", eat: "table", buy_bread: "counter", chart: "desk", window: "window", park: "bench" };

// a hook that throws is reported once and the page keeps running
const failed = new Set();
function hook(name, fn) {
  try { fn(); }
  catch (e) { if (!failed.has(name)) { failed.add(name); console.error(`[construct] ${name} failed:`, e); } }
}

// ---------------- renderer, scene, camera ----------------
const quality = Quality.init();
stats.quality = quality.name;
const host = $("scene");
const renderer = new THREE.WebGLRenderer({ antialias: quality.antialias, powerPreference: "high-performance" });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
renderer.info.autoReset = false;               // count every pass of the frame (fx may render several)
host.prepend(renderer.domElement);

const scene = new THREE.Scene();
const SKY = new THREE.Color(0x05060c);
scene.background = SKY.clone();
scene.fog = new THREE.FogExp2(0x05060c, 0.0009);
const camera = new THREE.PerspectiveCamera(62, 1, 0.5, 6000);
camera.position.set(0, 700, 900);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.48;
controls.minDistance = 20;
controls.maxDistance = 2200;
controls.enabled = false;

function resize() {
  const w = host.clientWidth || window.innerWidth, h = host.clientHeight || window.innerHeight;
  renderer.setSize(w, h, false);
  renderer.domElement.style.width = "100%"; renderer.domElement.style.height = "100%";
  camera.aspect = w / h; camera.updateProjectionMatrix();
  hook("fx.resize", () => fx?.resize?.(w, h));
}
new ResizeObserver(() => resize()).observe(host);

// ---------------- foundation modules ----------------
const phone = createPhone();
$("phone-overlay").appendChild(phone.overlayEl);
let net = null;
const hud = createHud({ send: obj => (net ? net.send(obj) : false) });
const minibrain = createMiniBrain($("minibrain"), { quality });

// ---------------- construct modules (built when the brain data is loaded) ----------------
let data = null, city = null, travel = null, fx = null, building = null;
function build(q) {
  const want = q.name;
  building = loadBrainData(q).then(d => {
    if (Quality.current.name !== want) return;                 // a newer switch is loading
    hook("city.dispose", () => { if (city) { city.dispose ? city.dispose() : scene.remove(city.object); } });
    data = d;
    city = createCity(scene, d, q);
    if (!travel) { travel = createTravel(camera, controls, d, { scene }); travel.setView(view); }
    if (!fx) { fx = createFx(renderer, scene, camera, d, q); fx.weather(market); resize(); }
    stats.districts = d.districts.length; stats.fibres = d.roads.fibres;
  }).catch(e => { console.error("[construct] brain data failed:", e); $("boot").textContent = "could not load the brain data"; });
}

// ---------------- live state ----------------
let life = null, sleep = null, stage = "AWAKE", clock = "--:--", pool = "", market = "calm", serverMarket = false;
let world = FALLBACK_WORLD, walkStart = null, walkGoal = null, wasWalking = false;
let act = null, base = null, lastGroups = {};
const groupRel = {}, groupBase = {}, groupSelf = {};
const flow = []; let flowSum = 0;
const chatLines = [];
const chatByCid = new Map();
const replays = []; let replaySeq = 0;
const trades = [];                                           // [t, +1 buy / -1 sell] of the last minute (market fallback)

function updateAct(m) {
  if (!Array.isArray(m.act)) return;
  const n = m.act.length;
  if (!act || act.length !== n) { act = new Float32Array(n); base = Float32Array.from(m.act); }
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const a = +m.act[i] || 0;
    base[i] = base[i] * 0.998 + a * 0.002;
    act[i] = a / Math.max(base[i], 0.02); sum += act[i];
  }
  const gm = Math.max(1e-3, sum / n);
  for (let i = 0; i < n; i++) act[i] /= gm;
}

function updateGroups(m) {
  const g = m.groups;
  if (!g) return;
  lastGroups = g;
  const keys = Object.keys(g);
  const mean = Math.max(1e-6, keys.reduce((s, k) => s + (+g[k] || 0), 0) / Math.max(1, keys.length));
  for (const k of keys) {
    const v = +g[k] || 0;
    groupRel[k] = v / mean;
    groupBase[k] = groupBase[k] === undefined ? v : groupBase[k] * 0.998 + v * 0.002;
    groupSelf[k] = v / Math.max(groupBase[k], 1e-3);
  }
  const fear = Math.max(groupSelf.fear || 0, groupSelf.salience || 0);   // above its own usual level
  hook("city.setFear", () => city?.setFear(Math.max(0, Math.min(1, (fear - 1.15) / 0.5))));
}

function updateMarket(m) {
  const now = performance.now() / 1000;
  for (const t of m.trades || []) trades.push([now, t.kind === "buy" ? 1 : -1]);
  while (trades.length && now - trades[0][0] > 60) trades.shift();
  let next = market;
  if (typeof m.market === "string") { serverMarket = true; next = normMarket(m.market); }
  else if (!serverMarket) {
    const buys = trades.filter(t => t[1] > 0).length, sells = trades.length - buys;
    next = buys >= 3 && buys > 2 * sells ? "pumping" : sells >= 3 && sells > 2 * buys ? "dumping" : trades.length >= 6 ? "choppy" : "calm";
  }
  if (next !== market) { market = next; hook("fx.weather", () => fx?.weather(market)); }
}
function normMarket(s) {
  const x = s.toLowerCase();
  return /pump|up|bull/.test(x) ? "pumping" : /dump|down|bear|crash/.test(x) ? "dumping" : /chop|vol/.test(x) ? "choppy" : "calm";
}

// route / progress of the current walk from the life.py waypoint graph (only if the server does not send them)
function fillRoute(L) {
  if (!L) return;
  if (!L.walking) { wasWalking = false; walkStart = walkGoal = null; return; }
  if (Array.isArray(L.route) && typeof L.progress === "number") return;
  const goal = ACT_PLACE[L.activity] || L.place;
  if (!wasWalking || goal !== walkGoal) { walkStart = L.place; walkGoal = goal; wasWalking = true; }   // new walk / new goal
  const r = waypointRoute(walkStart || L.place, goal);
  if (!r) return;
  L.route = r.route;
  const P = world.places, k = r.route.indexOf(L.place);
  let walked = 0;
  if (k >= 0) {
    for (let j = 1; j <= k; j++) walked += dist2(P[r.route[j - 1]], P[r.route[j]]);
    walked += Math.hypot(L.x - P[L.place][0], L.z - P[L.place][1]);
  } else walked = r.total - Math.hypot(L.x - P[goal][0], L.z - P[goal][1]);
  L.progress = r.total > 0 ? Math.max(0, Math.min(1, walked / r.total)) : 1;
}
const dist2 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const routeCache = new Map();
function waypointRoute(a, b) {
  const P = world.places;
  if (!P[a] || !P[b]) return null;
  const key = a + ">" + b;
  if (routeCache.has(key)) return routeCache.get(key);
  const dist = { [a]: 0 }, prev = {}, todo = new Set(Object.keys(P));
  while (todo.size) {
    let u = null;
    for (const n of todo) if (dist[n] !== undefined && (u === null || dist[n] < dist[u])) u = n;
    if (u === null || u === b) break;
    todo.delete(u);
    for (const [x, y] of world.edges) {
      const v = x === u ? y : y === u ? x : null;
      if (v === null || !todo.has(v)) continue;
      const d = dist[u] + dist2(P[u], P[v]);
      if (dist[v] === undefined || d < dist[v]) { dist[v] = d; prev[v] = u; }
    }
  }
  if (dist[b] === undefined) return null;
  const route = [b];
  while (route[route.length - 1] !== a) route.push(prev[route[route.length - 1]]);
  const r = { route: route.reverse(), total: dist[b] };
  routeCache.set(key, r);
  return r;
}

function onChat(m) {
  chatLines.push(m); if (chatLines.length > 40) chatLines.shift();
  if (m.cid) { chatByCid.set(m.cid, m); if (chatByCid.size > 60) chatByCid.delete(chatByCid.keys().next().value); }
  hud.chat(m);
  const regions = m.regions && m.regions.length ? m.regions : m.networks;
  hook("fx.rain", () => fx?.rain(m));
  if (regions) {
    hook("city.flash", () => city?.flash(regions, 0xff6a00));
    minibrain.flash(regions, 0xff6a00); minibrain.pulse($("chat"));
  }
}

net = connect({
  open() { stats.connected = true; },
  close() { stats.connected = false; },
  hello(m) {
    if (m.world && m.world.places && m.world.edges) { world = m.world; routeCache.clear(); }
    chatLines.length = 0; (m.chat || []).forEach(x => chatLines.push(x));
    hud.hello(m); minibrain.hello(m);
  },
  tick(m) {
    sleep = m.sleep || null; stage = (sleep && sleep.stage) || "AWAKE"; clock = (sleep && sleep.clock) || clock; pool = m.pool || pool;
    for (const t of m.trades || []) { flowSum += (t.kind === "buy" ? 1 : -1) * Math.log10(1 + t.usd); flow.push(flowSum); if (flow.length > 90) flow.shift(); }
    for (const ev of m.events || []) if (ev.type === "replay" && ev.text) {
      replays.push({ text: ev.text, t: ev.t, seq: ++replaySeq }); if (replays.length > 30) replays.shift();
    }
    updateAct(m); updateGroups(m); updateMarket(m);
    if (m.life) { life = m.life; life.stage = stage; fillRoute(life); }
    hud.tick(m); minibrain.tick(m);
  },
  chat: onChat,
  chat_ack(m) { hud.chatAck(m); },
  eye(m) { hud.eye(m); },
  nights(m) { hud.nights(m); },
  mind(m) { hud.mind(m); },
  speech(m) {
    hud.speech(m);
    const chat = m.about ? chatByCid.get(m.about) || null : null;
    hook("fx.innerLine", () => fx?.innerLine({ ...m, chat }));
  },
});

// ---------------- HUD tools: view switch (#view), quality switch (#quality) ----------------
const viewBtn = document.createElement("button");
viewBtn.type = "button";
viewBtn.title = "switch view (v)";
function setView(v) {
  view = v === "orbit" ? "orbit" : "first";
  stats.view = view;
  viewBtn.textContent = view === "first" ? "overview" : "first person";
  viewBtn.setAttribute("aria-label", `switch to ${viewBtn.textContent}`);
  document.body.classList.toggle("view-orbit", view === "orbit");
  document.body.classList.toggle("view-first", view === "first");
  hook("travel.setView", () => travel?.setView(view));
  const u = new URL(location.href);
  if (view === "first") u.searchParams.delete("view"); else u.searchParams.set("view", view);
  history.replaceState(null, "", u);
}
viewBtn.onclick = () => setView(view === "first" ? "orbit" : "first");
($("view") || $("tools")).appendChild(viewBtn);
addEventListener("keydown", e => {
  if (e.key === "v" && !/input|textarea|select/i.test(document.activeElement?.tagName || "")) setView(view === "first" ? "orbit" : "first");
});
setView(view);
Quality.mountSwitch($("quality"));

function applyQuality(q) {
  stats.quality = q.name;
  renderer.setPixelRatio(Math.min(q.pixelRatio, window.devicePixelRatio || 1));
  for (const c of ["q-low", "q-medium", "q-high"]) document.body.classList.toggle(c, c === "q-" + q.name);
  resize();
}
Quality.onChange(q => { applyQuality(q); build(q); });
applyQuality(quality);
build(quality);

// ---------------- render loop ----------------
function romeHour() { const [h, m] = clock.split(":").map(Number); return isNaN(h) ? 12 : h + (m || 0) / 60; }
const env = { romeHour: 12, dayK: 1, night: false, stage: "AWAKE", lab: false, sleep: null, quality, market: "calm", groups: {},
  groupRel, groupSelf, time: 0, view, follow, replays, walking: false };
const phoneState = { app: null, visible: false, asleep: false, pool: "", flow, chat: chatLines, clock: "--:--" };


function updateEnv(dt) {
  env.romeHour = romeHour();
  env.dayK = Math.max(0, Math.sin(Math.PI * (env.romeHour - 6) / 14));
  env.night = env.dayK < 0.15;
  env.stage = stage; env.sleep = sleep; env.quality = Quality.current; env.market = market;
  env.groups = lastGroups; env.time += dt; env.view = view; env.walking = !!life?.walking;
}

function updatePhoneState() {
  const asleep = stage !== "AWAKE";
  phoneState.asleep = asleep;
  phoneState.app = life && life.phone && !asleep ? life.phone : null;
  phoneState.visible = !!phoneState.app;
  phoneState.pool = pool; phoneState.clock = clock;
  $("phone-overlay").classList.toggle("on", phoneState.visible);
}

let last = performance.now(), fpsAcc = 0, fpsN = 0, framesDrawn = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
  fpsAcc += dt; fpsN++;
  if (fpsAcc >= 0.5) { stats.fps = Math.round(fpsN / fpsAcc); fpsAcc = 0; fpsN = 0; }

  updateEnv(dt);
  updatePhoneState();
  hook("city", () => city?.update(dt, env, act));
  hook("travel", () => travel?.update(dt, life, env));
  hook("fx", () => fx?.update(dt, env));
  hook("phone", () => phone.update(phoneState));
  hook("hud", () => hud.update(dt, env));
  hook("minibrain", () => minibrain.update(dt, env));

  if (controls.enabled) controls.update();
  renderer.info.reset();
  if (fx) hook("fx.render", () => fx.render()); else renderer.render(scene, camera);
  stats.drawCalls = renderer.info.render.calls;
  stats.triangles = renderer.info.render.triangles;
  if (city && ++framesDrawn === 2) { stats.ready = true; document.body.classList.add("ready"); }
}
resize();
requestAnimationFrame(frame);
