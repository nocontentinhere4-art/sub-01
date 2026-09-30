// Life page entry (foundation / integration). Boots the renderer, the websocket client and the render loop, and wires
// the stream modules together. Each stream only replaces its own file (see docs/real-world/CONTRACT.md):
//   world/index.js  createWorld(renderer, scene, camera, assets, quality, layout) -> {update(dt, env), setLab(on), anchors}
//   assets.js       createAssets(renderer, quality)
//   character.js    createCharacter(scene, assets), createBaker(scene, assets, anchors) -> {update(dt, life), object}
//   phone.js        createPhone() -> {texture, chartTexture, overlayEl, update(state), setApp(app)}
//   hud.js          createHud({send}) -> {hello, tick, chat, chatAck, eye, nights, mind, speech, update(dt, env)}
//   minibrain.js    createMiniBrain(el, {quality}) -> {hello, tick, flash(regions, color), pulse(fromEl), update(dt, env)}
//
// Render loop hooks, in this fixed order every frame: world.update(dt, env), character.update(dt, life),
// baker.update(dt, life), phone.update(state), hud.update(dt, env), minibrain.update(dt, env).
//   env = {romeHour, dayK, night, stage, lab, sleep, quality}
//   life = tick.life snapshot + {stage} (null until the first tick)
// URL params: ?cam=apartment|street|bakery|park|phone|brain  ?q=low|medium|high  ?lab=1  ?nofollow=1
// window.__sub01 = {ready, fps, drawCalls, triangles, quality, connected}
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { connect } from "./net.js";
import { Quality } from "./quality.js";
import { createAssets } from "./assets.js";
import { createWorld } from "./world/index.js";
import { createCharacter, createBaker } from "./character.js";
import { createPhone } from "./phone.js";
import { createHud } from "./hud.js";
import { createMiniBrain } from "./minibrain.js";

const params = new URLSearchParams(location.search);
const CAM = params.get("cam");
const $ = id => document.getElementById(id);
const stats = (window.__sub01 = { ready: false, fps: 0, drawCalls: 0, triangles: 0, quality: null, connected: false });

// The server sends the layout in hello.world (life.WORLD). This copy is used only if hello is late (> 5 s) so the page
// still shows a world; the server's layout replaces nothing afterwards (the world is built once).
const FALLBACK_LAYOUT = {
  places: { bed: [1.6, 1.3], window: [4.0, 0.9], desk: [6.6, 1.4], table: [4.4, 3.6], door_in: [4.0, 5.4], door_out: [4.0, 6.9],
    street_home: [4.0, 10.0], street_bakery: [21.0, 10.0], bakery_door: [21.0, 13.0], bakery_in: [21.0, 15.2], counter: [21.0, 16.4],
    street_park: [-13.0, 10.0], park_gate: [-13.0, 13.4], bench: [-13.0, 17.4] },
  edges: [], apartment: [0, 0, 8, 6], bakery: [17, 14, 25, 20], park: [-19, 13, -7, 23], street: [-22, 8.5, 30, 11.5],
};

// ---------------- quality + renderer ----------------
const quality = Quality.init();
stats.quality = quality.name;
const host = $("scene");
const renderer = new THREE.WebGLRenderer({ antialias: quality.antialias, powerPreference: "high-performance" });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.info.autoReset = false;               // count every pass of the frame (composer = several renders)
host.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0c12);
const camera = new THREE.PerspectiveCamera(42, 1, 0.1, quality.drawDistance);
camera.position.set(4, 16, 22);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 1.5;
controls.maxDistance = 90;
controls.target.set(4, 0, 4);

// ---------------- post-processing (medium / high), loaded on demand ----------------
let composer = null, composerFor = null, composerLoading = null;
async function buildComposer(q) {
  const [{ EffectComposer }, { RenderPass }, { UnrealBloomPass }, { OutputPass }, gtao] = await Promise.all([
    import("three/addons/postprocessing/EffectComposer.js"), import("three/addons/postprocessing/RenderPass.js"),
    import("three/addons/postprocessing/UnrealBloomPass.js"), import("three/addons/postprocessing/OutputPass.js"),
    q.ao ? import("three/addons/postprocessing/GTAOPass.js") : null]);
  const size = renderer.getDrawingBufferSize(new THREE.Vector2());
  const target = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType, samples: q.msaa || 0 });
  const c = new EffectComposer(renderer, target);
  c.addPass(new RenderPass(scene, camera));
  if (gtao) { const p = new gtao.GTAOPass(scene, camera, size.x, size.y); p.blendIntensity = 0.8; c.addPass(p); }
  if (q.bloom) c.addPass(new UnrealBloomPass(new THREE.Vector2(size.x / 2, size.y / 2), 0.35, 0.4, 0.92));
  c.addPass(new OutputPass());
  return c;
}
function syncComposer() {
  const q = Quality.current;
  if (!q.post) { composer?.dispose(); composer = null; composerFor = null; return; }
  if (composerFor === q.name || composerLoading) return;
  const want = q.name;
  composerLoading = buildComposer(q).then(c => {
    composerLoading = null;
    if (Quality.current.name !== want) { c.dispose(); syncComposer(); return; }
    composer?.dispose(); composer = c; composerFor = want; resize();
  }).catch(e => { composerLoading = null; composerFor = want; console.warn("[main] post-processing off:", e?.message || e); });
}

function applyQuality(q) {
  stats.quality = q.name;
  renderer.setPixelRatio(Math.min(q.pixelRatio, window.devicePixelRatio || 1));
  if (renderer.shadowMap.enabled !== q.shadows) {
    renderer.shadowMap.enabled = q.shadows;
    scene.traverse(o => { if (o.material) for (const m of [].concat(o.material)) m.needsUpdate = true; });
  }
  const sun = world?.anchors?.sun;
  if (sun && sun.shadow.mapSize.x !== q.shadowMapSize) {
    sun.shadow.mapSize.set(q.shadowMapSize, q.shadowMapSize); sun.shadow.map?.dispose(); sun.shadow.map = null;
  }
  camera.far = q.drawDistance; camera.updateProjectionMatrix();
  for (const c of ["q-low", "q-medium", "q-high"]) document.body.classList.toggle(c, c === "q-" + q.name);
  resize();
  syncComposer();
}

function resize() {
  const w = host.clientWidth || window.innerWidth, h = host.clientHeight || window.innerHeight;
  renderer.setSize(w, h, false);
  renderer.domElement.style.width = "100%"; renderer.domElement.style.height = "100%";
  camera.aspect = w / h; camera.updateProjectionMatrix();
  if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); }
}
new ResizeObserver(resize).observe(host);

// ---------------- stream modules ----------------
const assets = createAssets(renderer, quality);
let world = null, character = null, baker = null;
const phone = createPhone();
$("phone-overlay").appendChild(phone.overlayEl);
let net = null;
const hud = createHud({ send: obj => (net ? net.send(obj) : false) });
const minibrain = createMiniBrain($("minibrain"), { quality });
if (CAM === "brain") document.body.classList.add("cam-brain");
if (CAM) document.body.classList.add("cam-" + CAM.replace(/[^a-z]/g, ""));
if (CAM === "phone") phone.setApp("chart");

// ---------------- live state ----------------
let life = null, sleep = null, stage = "AWAKE", clock = "--:--", pool = "";
const flow = []; let flowSum = 0;
const chatLines = [];
let lab = params.get("lab") === "1", follow = params.get("nofollow") !== "1" && !CAM;

function buildWorld(layout) {
  if (world) return;
  try {
    world = createWorld(renderer, scene, camera, assets, Quality.current, layout);
    world.setLab(lab);
    if (world.anchors?.monitor) { world.anchors.monitor.material.map = phone.chartTexture; world.anchors.monitor.material.needsUpdate = true; }
    character = createCharacter(scene, assets);
    baker = createBaker(scene, assets, world.anchors);
    applyQuality(Quality.current);
    applyCam();
  } catch (e) { console.error("[main] world failed to build:", e); }
}
setTimeout(() => { if (!world) buildWorld(FALLBACK_LAYOUT); }, 5000);

function applyCam() {
  const cams = world?.anchors?.cams || {};
  const c = cams[CAM];
  if (c) { camera.position.set(...c.pos); controls.target.set(...c.target); controls.update(); }
}

function onChat(m) {
  chatLines.push(m); if (chatLines.length > 40) chatLines.shift();
  hud.chat(m);
  const regions = m.regions || m.networks;
  if (regions) { minibrain.flash(regions, 0xff6a00); minibrain.pulse($("chat")); }
}

net = connect({
  open() { stats.connected = true; },
  close() { stats.connected = false; },
  hello(m) {
    buildWorld(m.world || FALLBACK_LAYOUT);
    chatLines.length = 0; (m.chat || []).forEach(x => chatLines.push(x));
    hud.hello(m); minibrain.hello(m);
  },
  tick(m) {
    sleep = m.sleep || null; stage = (sleep && sleep.stage) || "AWAKE"; clock = (sleep && sleep.clock) || clock; pool = m.pool || pool;
    for (const t of m.trades || []) { flowSum += (t.kind === "buy" ? 1 : -1) * Math.log10(1 + t.usd); flow.push(flowSum); if (flow.length > 90) flow.shift(); }
    if (m.life) { life = m.life; life.stage = stage; }
    hud.tick(m); minibrain.tick(m);
  },
  chat: onChat,
  chat_ack(m) { hud.chatAck(m); },
  eye(m) { hud.eye(m); },
  nights(m) { hud.nights(m); },
  mind(m) { hud.mind(m); },
  speech(m) { hud.speech(m); },
});

// ---------------- HUD tools: follow + lab mode (#lab), quality switch (#quality) ----------------
function toolButton(parent, text, on, onClick) {
  const b = document.createElement("button"); b.type = "button"; b.textContent = text; b.classList.toggle("on", on);
  b.setAttribute("aria-pressed", String(on)); b.onclick = () => onClick(b); parent.appendChild(b); return b;
}
const setOn = (b, on) => { b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); };
const followBtn = toolButton($("lab"), "follow", follow, b => { follow = !follow; setOn(b, follow); });
toolButton($("lab"), "lab mode", lab, b => { lab = !lab; setOn(b, lab); document.body.classList.toggle("lab", lab); world?.setLab(lab); });
document.body.classList.toggle("lab", lab);
controls.addEventListener("start", () => { follow = false; setOn(followBtn, false); });
Quality.mountSwitch($("quality"));
Quality.onChange(q => applyQuality(q));
applyQuality(quality);

// ---------------- render loop ----------------
function romeHour() { const [h, m] = clock.split(":").map(Number); return isNaN(h) ? 12 : h + (m || 0) / 60; }
const env = { romeHour: 12, dayK: 1, night: false, stage: "AWAKE", lab: false, sleep: null, quality };
const phoneState = { app: null, visible: false, asleep: false, pool: "", flow, chat: chatLines, clock: "--:--" };
const followTarget = new THREE.Vector3(), followCam = new THREE.Vector3(), FOLLOW_OFFSET = new THREE.Vector3(0, 9, 12);
const PHONE_OFFSET = new THREE.Vector3(0, 2.2, 2.6);

const failed = new Set();
function hook(name, fn) {
  try { fn(); }
  catch (e) { if (!failed.has(name)) { failed.add(name); console.error(`[main] ${name} failed:`, e); } }
}

function updateEnv() {
  env.romeHour = romeHour();
  env.dayK = Math.max(0, Math.sin(Math.PI * (env.romeHour - 6) / 14));
  env.night = env.dayK < 0.15;
  env.stage = stage; env.lab = lab; env.sleep = sleep; env.quality = Quality.current;
}

function updatePhoneState() {
  const asleep = stage !== "AWAKE";
  phoneState.asleep = asleep;
  phoneState.app = life && life.phone && !asleep ? life.phone : null;
  phoneState.visible = !!phoneState.app || CAM === "phone";
  phoneState.pool = pool; phoneState.clock = clock;
  $("phone-overlay").classList.toggle("on", phoneState.visible);
}

function updateCamera(dt) {
  const obj = character?.object;
  if (!obj) return;
  const k = 1 - Math.exp(-dt * 3), kc = 1 - Math.exp(-dt * 1.2);
  if (CAM === "phone") {
    followTarget.set(obj.position.x, 1.2, obj.position.z);
    controls.target.lerp(followTarget, k); camera.position.lerp(followCam.copy(followTarget).add(PHONE_OFFSET), kc);
  } else if (follow && life) {
    followTarget.set(obj.position.x, 0.8, obj.position.z);
    controls.target.lerp(followTarget, k); camera.position.lerp(followCam.copy(followTarget).add(FOLLOW_OFFSET), kc);
  }
}

let last = performance.now(), fpsAcc = 0, fpsN = 0, framesDrawn = 0;
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
  fpsAcc += dt; fpsN++;
  if (fpsAcc >= 0.5) { stats.fps = Math.round(fpsN / fpsAcc); fpsAcc = 0; fpsN = 0; }

  updateEnv();
  updatePhoneState();
  hook("world", () => world?.update(dt, env));
  hook("character", () => character?.update(dt, life));
  hook("baker", () => baker?.update(dt, life));
  hook("phone", () => phone.update(phoneState));
  hook("hud", () => hud.update(dt, env));
  hook("minibrain", () => minibrain.update(dt, env));

  updateCamera(dt);
  controls.update();
  renderer.info.reset();
  if (composer) composer.render(dt); else renderer.render(scene, camera);
  stats.drawCalls = renderer.info.render.calls;
  stats.triangles = renderer.info.render.triangles;
  if (world && ++framesDrawn === 2) { stats.ready = true; document.body.classList.add("ready"); }
}
resize();
requestAnimationFrame(frame);
