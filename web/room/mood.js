// The room's mood layer (?mood=1, a preview: the default page does not load this file). Four things on top of the room's
// own lights (room.html lighting()), all drawn with our own assets and code:
//
//   1. light and atmosphere: the sun comes in through the window from where the window shows it (window_view.js's
//      light.dir), low and warm in the morning and the evening, with soft shadows, a beam of light with dust in it, a
//      warm bounce off the floor where the sun lands, and an environment painted from the room's own colours (so metal,
//      glass and the rough surfaces pick up the warm walls and floor rather than a neutral grey studio);
//   2. light that changes with the hour: the Tokyo hour the site already uses (the same `hour` that drives windowView),
//      morning / noon / evening / night cross-faded (window_view.js dayPhase), the lamps on in the evening, the
//      monitor's own light at night, and a "preview the hour" slider that eases back to the real hour on its own;
//   3. the visitor's materials: swatches for the floor, the walls, the bed and the textiles, recoloured from the room's
//      own textures in the browser. The choice is kept in this browser only (localStorage, inside try/catch): nothing is
//      sent anywhere, and nobody else's room changes;
//   4. one rounded card in the side column (on phones: the first card under the scene), so it never covers him.
//
//   import { createMood } from "./room/mood.js";
//   const mood = createMood(THREE, ctx);   // ctx: see the destructuring below
//   mood.tick(dt, hour)                    // every frame, before windowView.update: returns the hour to show
//   mood.hour                              // the hour the room is lit for (the real one, or the preview)
//   mood.light(dt, {day})                  // every frame, after lighting(): the mood's lights on top
//   mood.onRoom(room)                      // once the room model is in: its materials for the swatches

import { dayPhase } from "./window_view.js";
import { createArrange } from "./mood_arrange.js";

export const STORE_KEY = "sub01.room.mood.v1";
export const HOLD_S = 6, BACK_S = 2.5;                  // a preview holds 6 s after the last touch, then eases back in 2.5 s

// swatches: the first of each group is the room as built (its own texture untouched); the others recolour that texture
// to a mean colour (`c`), keeping its grain. Colours are ours; `r`: roughness, when it should change with the finish
export const GROUPS = {
  floor: {label: "Floor", mats: ["floor"], variants: [
    {id: "oak", label: "Oak", sw: "#b37a45"},
    {id: "ash", label: "Pale ash", c: {floor: "#cdb698"}, sw: "#cdb698"},
    {id: "honey", label: "Honey", c: {floor: "#c4834a"}, sw: "#c4834a"},
    {id: "walnut", label: "Walnut", c: {floor: "#6e4a33"}, sw: "#6e4a33", r: 0.55},
    {id: "smoked", label: "Smoked oak", c: {floor: "#857565"}, sw: "#857565"},
  ]},
  wall: {label: "Walls", mats: ["wall"], variants: [
    {id: "chalk", label: "Chalk", sw: "#e7e2d8"},
    {id: "linen", label: "Linen", c: {wall: "#eedfc8"}, sw: "#eedfc8"},
    {id: "clay", label: "Clay", c: {wall: "#dcb6a2"}, sw: "#dcb6a2"},
    {id: "sage", label: "Sage", c: {wall: "#b8c1a3"}, sw: "#b8c1a3"},
    {id: "dusk", label: "Dusk blue", c: {wall: "#a7adbf"}, sw: "#a7adbf"},
  ]},
  bed: {label: "Bed", mats: ["duvet"], variants: [
    {id: "indigo", label: "Indigo", sw: "#4a5778"},
    {id: "rust", label: "Rust", c: {duvet: "#a9542c"}, sw: "#a9542c"},
    {id: "oat", label: "Oat", c: {duvet: "#d4c6ad"}, sw: "#d4c6ad"},
    {id: "moss", label: "Moss", c: {duvet: "#6c7750"}, sw: "#6c7750"},
    {id: "charcoal", label: "Charcoal", c: {duvet: "#3d3f45"}, sw: "#3d3f45"},
  ]},
  soft: {label: "Rug", mats: ["rug"], variants: [
    {id: "mustard", label: "Stone grey", sw: "#8a8478"},
    {id: "terra", label: "Cream", c: {rug: "#d9cdb8"}, sw: "#d9cdb8"},
    {id: "navy", label: "Oat", c: {rug: "#c4b393"}, sw: "#c4b393"},
    {id: "forest", label: "Charcoal", c: {rug: "#4f5054"}, sw: "#4f5054"},
    {id: "sun", label: "Terracotta", c: {rug: "#b0674a"}, sw: "#b0674a"},
  ]},
};
// looks: a whole room at once (the same swatches)
export const LOOKS = [
  {id: "built", label: "As built", set: {floor: "oak", wall: "chalk", bed: "indigo", soft: "mustard"}},
  {id: "golden", label: "Golden", set: {floor: "honey", wall: "linen", bed: "rust", soft: "terra"}},
  {id: "nordic", label: "Nordic", set: {floor: "ash", wall: "chalk", bed: "oat", soft: "forest"}},
  {id: "studio", label: "Studio", set: {floor: "walnut", wall: "dusk", bed: "charcoal", soft: "navy"}},
  {id: "calm", label: "Calm", set: {floor: "smoked", wall: "sage", bed: "moss", soft: "sun"}},
];
export const LAMPS = ["auto", "on", "off"];
export const CHIPS = [["Morning", 8.0], ["Noon", 12.5], ["Evening", 18.2], ["Night", 1.0]];

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const wrap24 = h => ((h % 24) + 24) % 24;
export const hourDelta = (from, to) => { let d = wrap24(to) - wrap24(from); if (d > 12) d -= 24; if (d < -12) d += 24; return d; };   // the short way round the clock
export const fmtHour = h => { const m = Math.round(wrap24(h) * 60) % 1440; return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };
// the lamps by the hour (auto): on from the late afternoon until after midnight
// late in the evening the ceiling light dims and the desk lamp and the screen carry the room (1 = late)
export const lateByHour = h => { h = wrap24(h); return h < 12 ? 1 : smooth(21.3, 23.0, h); };
export const lampsByHour = h => { h = wrap24(h); return Math.max(smooth(16.6, 17.8, h), h < 6 ? 1 - smooth(0.3, 1.0, h) : 0); };

// the visitor's choices: this browser only; any storage error (private mode, blocked, full) is the defaults
export function loadChoice(storage){
  const out = {floor: "oak", wall: "chalk", bed: "indigo", soft: "mustard", lamps: "auto", rays: true, open: true};
  try {
    const s = storage || (typeof localStorage !== "undefined" ? localStorage : null);
    const raw = s && s.getItem(STORE_KEY); if (!raw) return out;
    const v = JSON.parse(raw); if (!v || typeof v !== "object") return out;
    for (const g of Object.keys(GROUPS)) if (GROUPS[g].variants.some(x => x.id === v[g])) out[g] = v[g];
    if (LAMPS.includes(v.lamps)) out.lamps = v.lamps;
    if (typeof v.rays === "boolean") out.rays = v.rays;
    if (typeof v.open === "boolean") out.open = v.open;
  } catch {}
  return out;
}
export function saveChoice(choice, storage){
  try { const s = storage || localStorage; s.setItem(STORE_KEY, JSON.stringify(choice)); return true; } catch { return false; }
}

// recolour a texture's image to a mean colour, keeping its grain: half per-channel gain (keeps the texture's own hue
// variation), half luminance (keeps the grain when the hue moves far)
function recolour(img, hex, maxSize){
  const w0 = img.width, h0 = img.height, k = Math.min(1, maxSize / Math.max(w0, h0));
  const w = Math.max(1, Math.round(w0 * k)), h = Math.max(1, Math.round(h0 * k));
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  const cx = cv.getContext("2d", {willReadFrequently: true}); cx.drawImage(img, 0, 0, w, h);
  const im = cx.getImageData(0, 0, w, h), d = im.data;
  let mr = 0, mg = 0, mb = 0, n = 0;
  for (let i = 0; i < d.length; i += 4 * 7) { mr += d[i]; mg += d[i + 1]; mb += d[i + 2]; n++; }
  mr = Math.max(1, mr / n); mg = Math.max(1, mg / n); mb = Math.max(1, mb / n);
  const ml = 0.2126 * mr + 0.7152 * mg + 0.0722 * mb;
  const t = parseInt(hex.slice(1), 16), tr = t >> 16 & 255, tg = t >> 8 & 255, tb = t & 255;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2], l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / ml;
    d[i] = Math.min(255, tr * (0.5 * r / mr + 0.5 * l));
    d[i + 1] = Math.min(255, tg * (0.5 * g / mg + 0.5 * l));
    d[i + 2] = Math.min(255, tb * (0.5 * b / mb + 0.5 * l));
  }
  cx.putImageData(im, 0, 0);
  return cv;
}

const BEAM_VERT = /* glsl */`
  attribute vec2 aUV; varying vec2 vUV; varying vec3 vW;
  void main(){ vUV = aUV; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const BEAM_FRAG = /* glsl */`
  uniform vec3 uColor; uniform float uI; uniform float uTime; varying vec2 vUV; varying vec3 vW;
  void main(){
    float edge = pow(sin(3.14159 * clamp(vUV.x, 0.0, 1.0)), 2.2);
    float along = pow(1.0 - vUV.y, 2.2) * smoothstep(0.0, 0.08, vUV.y);
    float drift = 0.8 + 0.2 * sin(vW.x * 6.0 + vW.z * 4.0 + uTime * 0.35) * sin(vW.y * 8.0 - uTime * 0.25);
    gl_FragColor = vec4(uColor * (uI * edge * along * drift), 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }`;
const DUST_VERT = /* glsl */`
  attribute float aA; uniform float uSize; varying float vA;
  void main(){ vA = aA; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = uSize / -mv.z; gl_Position = projectionMatrix * mv; }`;
const DUST_FRAG = /* glsl */`
  uniform vec3 uColor; uniform float uI; varying float vA;
  void main(){ vec2 p = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.0, length(p));
    gl_FragColor = vec4(uColor * (uI * vA * a), 1.0);
    #include <colorspace_fragment>
  }`;

export function createMood(THREE, ctx){
  const {scene, renderer, pmrem, sun, hemi, ceiling, lamp, monitorGlow, SURF, F, roomMats, host} = ctx;
  const stage = ctx.stage || (() => "AWAKE"), home = ctx.home || (() => true), monitorOn = ctx.monitorOn || (() => null);
  const windowLight = () => (ctx.windowView && ctx.windowView.light) || {sun: 1, cloud: 0, dir: new THREE.Vector3(-1, 0.3, 0), up: 0, moon: false};
  const lite = !!ctx.lite;                                   // phones: fewer dust motes, a smaller shadow map, no screen area light
  const choice = loadChoice();
  // the light's levels (in the room's units; ?debug can tune them live through mood.tune)
  const T = {sun: 7.0, moon: 0.6, sky: 8.0, skyDusk: 1.5, bounce: 2.6, hemi: 0.42, hemiLamp: 0.28, ceil: 4.6, desk: 2.6, screen: 6.0,
    env: 0.55, exp0: 0.80, exp: 0.30, beam: 0.14, dust: 0.9};
  const state = {hour: 12, real: 12, preview: null, from: 0, t: 0, holdUntil: 0, dragging: false, back: null, now: 0};

  // ---- light: soft sun shadows (a wider PCF kernel instead of the fixed soft one), a warm bounce, the beam, the dust
  renderer.shadowMap.type = THREE.PCFShadowMap;
  sun.shadow.radius = lite ? 3 : 4.5; sun.shadow.blurSamples = 12;
  if (lite) { sun.shadow.mapSize.set(1024, 1024); if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; } }
  Object.assign(sun.shadow.camera, {left: -3.4, right: 3.4, top: 3.4, bottom: -3.4, near: 0.3, far: 16}); sun.shadow.camera.updateProjectionMatrix();
  const bounce = new THREE.PointLight(0xffc48a, 0, 4.2, 1.6); bounce.name = "mood_bounce"; scene.add(bounce);
  let screenLight = null;
  if (!lite && THREE.RectAreaLight) { screenLight = new THREE.RectAreaLight(0xbcd4ff, 0, 0.6, 0.36); screenLight.name = "mood_screen"; scene.add(screenLight); }
  scene.traverse(o => { if (o.material) for (const m of [].concat(o.material)) m.needsUpdate = true; });   // the new shadow kernel and lights

  // the beam: four sides of the prism of light from the window's glass along the sun's direction, additive
  const W = SURF.window, UP = new THREE.Vector3(0, 1, 0);
  const beamGeo = new THREE.BufferGeometry();
  beamGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(16 * 3), 3));
  const uv = []; for (let f = 0; f < 4; f++) uv.push(0, 0, 1, 0, 1, 1, 0, 1);
  beamGeo.setAttribute("aUV", new THREE.BufferAttribute(new Float32Array(uv), 2));
  const idx = []; for (let f = 0; f < 4; f++) idx.push(f * 4, f * 4 + 1, f * 4 + 2, f * 4, f * 4 + 2, f * 4 + 3);
  beamGeo.setIndex(idx);
  const beamMat = new THREE.ShaderMaterial({uniforms: {uColor: {value: new THREE.Color(1, 0.8, 0.55)}, uI: {value: 0}, uTime: {value: 0}},
    vertexShader: BEAM_VERT, fragmentShader: BEAM_FRAG, transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending});
  const beam = new THREE.Mesh(beamGeo, beamMat); beam.name = "mood_beam"; beam.frustumCulled = false; beam.renderOrder = 2; scene.add(beam);
  const NDUST = lite ? 70 : 160, dustP = new Float32Array(NDUST * 3), dustA = new Float32Array(NDUST), dustQ = [];
  for (let i = 0; i < NDUST; i++) { dustQ.push([Math.random(), Math.random(), Math.random(), 0.02 + 0.05 * Math.random(), Math.random() * 6.28]); dustA[i] = 0.35 + 0.65 * Math.random(); }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dustP, 3)); dustGeo.setAttribute("aA", new THREE.BufferAttribute(dustA, 1));
  const dustMat = new THREE.ShaderMaterial({uniforms: {uColor: {value: new THREE.Color(1, 0.86, 0.66)}, uI: {value: 0}, uSize: {value: 9}},
    vertexShader: DUST_VERT, fragmentShader: DUST_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending});
  const dust = new THREE.Points(dustGeo, dustMat); dust.name = "mood_dust"; dust.frustumCulled = false; dust.renderOrder = 3; scene.add(dust);

  // the glass's corners (world), its right and up
  const wc = new THREE.Vector3(...W.c), wr = new THREE.Vector3(1, 0, 0).applyAxisAngle(UP, W.ry), corners = [];
  for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) corners.push(wc.clone().addScaledVector(wr, sx * W.w / 2 * 0.96).add(new THREE.Vector3(0, sy * W.h / 2 * 0.94, 0)));
  const far = corners.map(c => c.clone()), into = new THREE.Vector3(), pool = new THREE.Vector3();
  const ROOM = {x0: -1.95, x1: 2.0, z0: -1.6, z1: 1.6};
  function reach(c, d){                                          // how far light from c along d goes before the floor or the room's edge
    let t = 6;
    if (d.y < -1e-3) t = Math.min(t, (c.y - F) / -d.y);
    if (d.x > 1e-3) t = Math.min(t, (ROOM.x1 - c.x) / d.x); else if (d.x < -1e-3) t = Math.min(t, (ROOM.x0 - c.x) / d.x);
    if (d.z > 1e-3) t = Math.min(t, (ROOM.z1 - c.z) / d.z); else if (d.z < -1e-3) t = Math.min(t, (ROOM.z0 - c.z) / d.z);
    return Math.max(0.05, t);
  }
  const lastDir = new THREE.Vector3(9, 9, 9);
  function placeBeam(dir){                                       // dir: towards the sun; the light travels along -dir
    into.copy(dir).negate();
    const P = beamGeo.attributes.position.array; pool.set(0, 0, 0);
    for (let i = 0; i < 4; i++) { far[i].copy(corners[i]).addScaledVector(into, reach(corners[i], into)); pool.add(far[i]); }
    pool.multiplyScalar(0.25);
    for (let f = 0; f < 4; f++) {
      const a = f, b = (f + 1) % 4, q = [corners[a], corners[b], far[b], far[a]];
      for (let k = 0; k < 4; k++) q[k].toArray(P, (f * 4 + k) * 3);
    }
    beamGeo.attributes.position.needsUpdate = true;
  }

  // ---- the environment: painted from the room's own colours and the hour, so reflections and the rough surfaces'
  // ambient pick up the warm walls and floor (a cheap stand-in for light bouncing round the room); re-made only when
  // what it shows changes (the hour in quarter hours while it moves, a swatch, the lamps)
  const envCv = document.createElement("canvas"); envCv.width = 128; envCv.height = 64;
  const envCx = envCv.getContext("2d"); let envTex = null, envRT = null, envKey = "", envAt = -1e9;
  const baseEnv = scene.environment;
  const colOf = (g) => { const v = GROUPS[g].variants.find(x => x.id === choice[g]); return new THREE.Color(Array.isArray(v.sw) ? v.sw[0] : v.sw); };
  const css = c => `rgb(${Math.round(255 * clamp(c.r, 0, 1))},${Math.round(255 * clamp(c.g, 0, 1))},${Math.round(255 * clamp(c.b, 0, 1))})`;
  function paintEnv(sky, sunC, direct, lampK, level){
    const g = envCx, w = envCv.width, h = envCv.height;
    const wall = colOf("wall").multiplyScalar(level), floor = colOf("floor").multiplyScalar(level * 0.8);
    const warm = new THREE.Color(1.0, 0.72, 0.45).multiplyScalar(lampK * 0.55);
    wall.add(warm); floor.add(warm.clone().multiplyScalar(0.6)).add(sunC.clone().multiplyScalar(direct * 0.35));
    const top = wall.clone().lerp(new THREE.Color(1, 0.93, 0.85).multiplyScalar(level), 0.3);
    const grd = g.createLinearGradient(0, 0, 0, h);
    grd.addColorStop(0, css(top)); grd.addColorStop(0.45, css(wall)); grd.addColorStop(0.52, css(wall.clone().multiplyScalar(0.8)));
    grd.addColorStop(0.6, css(floor)); grd.addColorStop(1, css(floor.clone().multiplyScalar(0.7)));
    g.fillStyle = grd; g.fillRect(0, 0, w, h);
    // the window: a bright patch where it is, seen from the middle of the room
    const out = new THREE.Vector3(0, 0, -1).applyAxisAngle(UP, W.ry);
    const u = (Math.atan2(out.z, out.x) / (2 * Math.PI) + 0.5) * w;
    const win = sky.clone().multiplyScalar(1.0);
    g.fillStyle = css(win);
    for (const du of [-w, 0, w]) g.fillRect(u + du - w * 0.07, h * 0.30, w * 0.14, h * 0.16);
    const t = new THREE.CanvasTexture(envCv); t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace;
    const rt = pmrem.fromEquirectangular(t); t.dispose();
    const prev = scene.environment; scene.environment = rt.texture;
    scene.traverse(o => { if (o.material) for (const m of [].concat(o.material)) if (m.envMap === prev || m.envMap === baseEnv) m.envMap = rt.texture; });
    if (envRT) envRT.dispose();                                  // (the render target, not only its texture: no GPU memory left behind)
    envRT = rt; envTex = rt.texture;
  }

  // ---- materials: the room's, by name (only once the model is in)
  const mats = {};                                               // name -> [materials]
  const orig = new Map();                                        // material -> {map, roughness, color}
  const made = new Map();                                        // material -> {key, tex}: its one recoloured texture in use
  let arrange = null;
  function onRoom(room){
    if (ctx.controls && ctx.camera && ctx.dom) {
      arrange = createArrange(THREE, {...ctx, room, shadowsDirty: () => { sun.shadow.needsUpdate = true; }});
      if (ui) { arrange.mount(ui.card.querySelector('section[data-tab="arr"]')); arrange.setActive(ui.tab() === "arr"); }
    }
    room.traverse(o => { if (!o.isMesh) return; for (const m of [].concat(o.material)) if (m && m.name) (mats[m.name] = mats[m.name] || []).includes(m) || mats[m.name].push(m); });
    for (const g of Object.keys(GROUPS)) apply(g, choice[g], true);
    for (const m of Object.values(mats).flat()) if (m.aoMap) m.aoMapIntensity = 1.25;   // the baked occlusion a little deeper
    envKey = "";
  }
  function apply(group, id, quiet){
    const G = GROUPS[group], v = G.variants.find(x => x.id === id) || G.variants[0];
    for (const name of G.mats) for (const m of mats[name] || []) {
      if (!orig.has(m)) orig.set(m, {map: m.map, roughness: m.roughness});
      const o = orig.get(m);
      const was = made.get(m);
      if (!v.c || !v.c[name] || !o.map || !o.map.image) {
        m.map = o.map; m.roughness = o.roughness; m.needsUpdate = true;
        if (was) { was.tex.dispose(); made.delete(m); }
        continue;
      }
      const key = v.c[name];
      if (was && was.key === key) continue;
      // a texture of its own: a clone shares the original's image (its Source), so it gets a new Source; the room's own
      // texture is never written to, and the previous recolour is freed (one recoloured texture per material at most)
      const t = o.map.clone(); t.source = new THREE.Source(recolour(o.map.image, key, lite ? 1024 : 2048)); t.needsUpdate = true;
      if (was) was.tex.dispose();
      made.set(m, {key, tex: t});
      m.map = t; m.roughness = v.r ?? o.roughness; m.needsUpdate = true;
    }
    choice[group] = v.id;
    if (!quiet) { saveChoice(choice); envKey = ""; }
    ui && ui.sync();
  }

  // ---- the hour: the real one, or the visitor's preview, easing back on its own
  function setPreview(h, tween){
    const cur = state.hour;
    if (tween) state.back = {from: cur, to: wrap24(h), t: 0, dur: 1.2, then: "hold"};
    else { state.back = null; state.preview = wrap24(h); }
    state.holdUntil = state.now + HOLD_S;
  }
  function goLive(){ if (state.preview === null && !state.back) return; state.back = {from: state.hour, to: null, t: 0, dur: BACK_S, then: "live"}; state.dragging = false; }
  function tick(dt, real){
    state.now += dt; state.real = Number.isFinite(real) ? wrap24(real) : state.real;
    if (state.back) {
      const b = state.back; b.t = Math.min(1, b.t + dt / b.dur);
      const to = b.to === null ? state.real : b.to, e = b.t * b.t * (3 - 2 * b.t);
      state.preview = wrap24(b.from + hourDelta(b.from, to) * e);
      if (b.t >= 1) { state.back = null; if (b.then === "live") state.preview = null; else state.holdUntil = state.now + HOLD_S; }
    } else if (state.preview !== null && !state.dragging && state.now > state.holdUntil) goLive();
    state.hour = state.preview === null ? state.real : state.preview;
    return state.hour;
  }

  // ---- every frame, after the room's own lighting(): the mood's lights on top
  const cSun = new THREE.Color(), cLow = new THREE.Color(0xffa45c), cHigh = new THREE.Color(0xfff0dd), cMoon = new THREE.Color(0x8da2e0);
  const cSky = new THREE.Color(), cSkyDay = new THREE.Color(0xdfe9ff), cSkyDusk = new THREE.Color(0xffb27a), cSkyNight = new THREE.Color(0x1c2440);
  const cLamp = new THREE.Color(0xffa860), cCeil = new THREE.Color(0xffcf9a), cWarmHemi = new THREE.Color(0xffd7b0), cNightHemi = new THREE.Color(0.20, 0.24, 0.42);
  let roomK = 0, deskK = 0, nightK = 0, lateK = 0, rays = choice.rays ? 1 : 0, sDirect = 0;
  function light(dt, base){
    const h = state.hour, ph = dayPhase(h), wl = windowLight();
    const up = wl.up ?? Math.sin(Math.PI * (h - 5.6) / 12.2), day = base && Number.isFinite(base.day) ? base.day : smooth(-0.08, 0.3, up);
    const k = Math.min(1, dt * 2.5), awake = stage() === "AWAKE", isHome = home();
    // the lamps: by the hour (auto) while he is up and in, or as the visitor set them
    const want = choice.lamps === "on" ? 1 : choice.lamps === "off" ? 0 : (awake && isHome ? lampsByHour(h) : 0);
    roomK += (want - roomK) * k; deskK += ((choice.lamps === "off" ? 0 : choice.lamps === "on" ? 1 : want) - deskK) * k;
    nightK += (ph.night - nightK) * k;
    // the sun (or the moon) from where the window shows it; direct light only as the weather lets it through
    const dir = wl.dir && wl.dir.lengthSq() > 0.5 ? wl.dir : new THREE.Vector3(-1, 0.35, 0);
    const direct = wl.moon ? 0 : smooth(-0.02, 0.16, up) * (wl.sun ?? 1);
    sDirect += (direct - sDirect) * Math.min(1, dt * 4);
    cSun.copy(cLow).lerp(cHigh, smooth(0.08, 0.65, up));
    if (wl.moon) { sun.color.copy(cMoon); sun.intensity = T.moon * (1 - 0.8 * (wl.cloud ?? 0)); }
    else { sun.color.copy(cSun); sun.intensity = 0.12 + T.sun * sDirect; }
    sun.position.copy(wc).addScaledVector(dir, 6); sun.target.position.copy(wc).addScaledVector(dir, -1.6);
    if (dir.distanceToSquared(lastDir) > 4e-6) { lastDir.copy(dir); placeBeam(dir); sun.shadow.needsUpdate = true; }
    // the sky's light through the glass: warm at dawn and dusk, deep blue at night
    cSky.copy(cSkyNight).lerp(cSkyDusk, smooth(-0.15, 0.05, up)).lerp(cSkyDay, smooth(0.1, 0.5, up));
    if (ctx.skyLight) { ctx.skyLight.color.copy(cSky); ctx.skyLight.intensity = 0.25 + T.sky * day * (0.55 + 0.45 * (wl.sun ?? 1)) + T.skyDusk * ph.evening * (1 - nightK); }
    // the floor where the sun lands throws warm light back up; the walls and the bed get it
    const floorC = colOf("floor"), alb = clamp(0.2126 * floorC.r + 0.7152 * floorC.g + 0.0722 * floorC.b, 0.15, 0.8);
    bounce.position.set(clamp(pool.x, ROOM.x0 + 0.2, ROOM.x1 - 0.2), F + 0.45, clamp(pool.z, ROOM.z0 + 0.2, ROOM.z1 - 0.2));
    bounce.color.copy(cSun).multiply(floorC.clone().lerp(new THREE.Color(1, 1, 1), 0.35));
    bounce.intensity = T.bounce * sDirect * alb;
    // ambient: warm by day and under the lamps, a cool dim blue at night with them off
    hemi.color.copy(cWarmHemi).lerp(cNightHemi, nightK * (1 - roomK));
    hemi.groundColor.copy(floorC).multiplyScalar(0.35).lerp(cNightHemi.clone().multiplyScalar(0.4), nightK * (1 - roomK));
    hemi.intensity = 0.06 + T.hemi * day + T.hemiLamp * roomK * (1 - 0.55 * lateK) + 0.10 * nightK;
    // the lamps: the ceiling light and the desk lamp, warm
    ceiling.color.copy(cCeil); lateK += (lateByHour(h) - lateK) * k;
    // (the mood decides the lamps on its own: in the small hours they are off and the screen lights the room)
    ceiling.intensity = T.ceil * roomK * (1 - 0.6 * lateK);
    lamp.color.copy(cLamp); lamp.intensity = T.desk * deskK;
    // the monitor: its own light, the room's main light at night
    const mon = monitorOn();
    if (screenLight) {
      const m = SURF.monitor, n = new THREE.Vector3(0, 0, 1).applyEuler(new THREE.Euler(m.rx || 0, m.ry, 0, "YXZ"));
      screenLight.width = m.w; screenLight.height = m.h;
      screenLight.position.set(...m.c).addScaledVector(n, 0.02); screenLight.lookAt(screenLight.position.clone().add(n));
      screenLight.color.copy(mon && mon.glow || new THREE.Color(0xbcd4ff));
      screenLight.intensity = mon ? 1.2 + T.screen * nightK * (1 - 0.5 * roomK) : 0;
      monitorGlow.intensity *= 0.5;
    } else if (mon) monitorGlow.intensity = Math.max(monitorGlow.intensity, 0.6 + 1.6 * nightK);
    // reflections: the painted environment, brighter by day
    const envI = 0.10 + T.env * day + 0.25 * roomK * (1 - 0.5 * lateK) + 0.05 * nightK;
    for (const m of roomMats) m.envMapIntensity = envI;
    scene.environmentIntensity = 0.25 + 0.35 * day + 0.2 * roomK;
    renderer.toneMappingExposure = T.exp0 + T.exp * day + 0.12 * roomK + 0.05 * nightK * (mon ? 1 : 0);
    // the beam and the dust: only with direct sun, strongest when the sun is low
    beamMat.uniforms.uTime.value = state.now;
    rays += ((choice.rays ? 1 : 0) - rays) * k;
    const lowK = 1 - 0.55 * smooth(0.2, 0.75, up);
    beamMat.uniforms.uColor.value.copy(cSun);
    beamMat.uniforms.uI.value = T.beam * sDirect * lowK * rays;
    beam.visible = beamMat.uniforms.uI.value > 0.002;
    dustMat.uniforms.uI.value = T.dust * sDirect * rays; dustMat.uniforms.uColor.value.copy(cSun);
    dustMat.uniforms.uSize.value = (lite ? 7 : 9) * renderer.getPixelRatio();
    dust.visible = dustMat.uniforms.uI.value > 0.01;
    if (dust.visible) {
      for (let i = 0; i < NDUST; i++) {
        const q = dustQ[i]; q[2] = (q[2] + q[3] * dt * 0.25) % 1; q[4] += dt * 0.4;
        const a = clamp(q[0] + 0.03 * Math.sin(q[4]), 0, 1), b = clamp(q[1] + 0.03 * Math.cos(q[4] * 0.7), 0, 1), s = q[2];
        const x0 = corners[0].x + (corners[1].x - corners[0].x) * a, y0 = corners[0].y + (corners[3].y - corners[0].y) * b, z0 = corners[0].z + (corners[1].z - corners[0].z) * a;
        const L = (reach(corners[0], into) + reach(corners[2], into)) * 0.5 * s;
        dustP[i * 3] = x0 + into.x * L; dustP[i * 3 + 1] = y0 + into.y * L; dustP[i * 3 + 2] = z0 + into.z * L;
      }
      dustGeo.attributes.position.needsUpdate = true;
    }
    // the environment, re-painted when what it shows has changed
    const key = [Math.round(h * 4), choice.floor, choice.wall, Math.round(roomK * 4), wl.moon ? 1 : 0].join(",");
    if (key !== envKey && state.now - envAt > 0.25) {
      envKey = key; envAt = state.now;
      paintEnv(cSky.clone().multiplyScalar(0.25 + 0.75 * day), cSun, sDirect, roomK, 0.12 + 0.6 * day + 0.25 * roomK);
    }
    if (arrange) arrange.tick(dt, choice.lamps === "off" ? 0 : Math.max(roomK, choice.lamps === "on" ? 1 : 0));
    ui && ui.tick();
  }

  // ---- the card
  let ui = null;
  if (typeof document !== "undefined" && ctx.ui !== false) ui = buildUI();
  function buildUI(){
    const style = document.createElement("style");
    style.textContent = `
  #mood { padding:12px 14px 12px; }
  #mood .k { margin-bottom:0; align-items:center; }
  #mood .k .md-now { color:var(--fg); letter-spacing:.04em; text-transform:none; font-size:11px; }
  #mood .k .md-now i { font-style:normal; color:var(--st); }
  #mood .md-tog { font:inherit; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim); background:none; border:0; cursor:pointer; padding:4px 0 4px 8px; }
  #mood .md-tog:hover { color:var(--fg); }
  #mood .md-body { margin-top:10px; }
  #mood.shut .md-body { display:none; }
  #mood .md-tabs { display:flex; gap:4px; background:rgba(255,255,255,.04); border:1px solid var(--line); border-radius:999px; padding:3px; margin-bottom:12px; }
  #mood .md-tabs button { flex:1; font:inherit; font-size:10.5px; min-width:0; color:var(--dim); background:none; border:0; border-radius:999px; padding:6px 0; cursor:pointer; transition:background .2s, color .2s; }
  #mood .md-tabs button[aria-selected="true"] { background:var(--or); color:#0a0a0a; }
  #mood .md-tabs button:not([aria-selected="true"]):hover { color:var(--fg); }
  #mood section[hidden] { display:none; }
  #mood .md-clock { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
  #mood .md-clock b { font-weight:400; font-size:26px; letter-spacing:.02em; }
  #mood .md-clock span { font-size:10.5px; color:var(--dim); text-align:right; }
  #mood .md-clock span.pv { color:var(--st); }
  #mood .md-range { position:relative; height:28px; }
  #mood .md-range .trk { position:absolute; left:0; right:0; top:10px; height:8px; border-radius:999px;
    background:linear-gradient(90deg, #1b2342 0%, #1b2342 20%, #e88a4f 25.5%, #f3e2c4 33%, #eaf0fb 50%, #f3e2c4 66%, #e0763a 74%, #3a2a4a 80%, #1b2342 86%, #1b2342 100%);
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }
  #mood .md-range .live { position:absolute; top:5px; width:2px; height:18px; margin-left:-1px; background:var(--fg); border-radius:1px; opacity:.75; pointer-events:none; }
  #mood input[type=range] { position:absolute; inset:0; width:100%; margin:0; background:none; -webkit-appearance:none; appearance:none; cursor:pointer; touch-action:pan-y; }
  #mood input[type=range]::-webkit-slider-runnable-track { height:28px; background:none; }
  #mood input[type=range]::-moz-range-track { height:28px; background:none; }
  #mood input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:20px; height:20px; margin-top:4px; border-radius:50%; background:var(--or);
    border:3px solid #0d0d12; box-shadow:0 0 0 1px rgba(255,154,60,.6), 0 2px 10px rgba(0,0,0,.6); }
  #mood input[type=range]::-moz-range-thumb { width:14px; height:14px; border-radius:50%; background:var(--or); border:3px solid #0d0d12; box-shadow:0 0 0 1px rgba(255,154,60,.6); }
  #mood input[type=range]:focus-visible { outline:none; } #mood input[type=range]:focus-visible::-webkit-slider-thumb { box-shadow:0 0 0 3px rgba(255,106,0,.55); }
  #mood .md-ticks { display:flex; justify-content:space-between; font-size:9.5px; color:var(--faint); margin-top:2px; }
  #mood .md-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  #mood .md-chips button, #mood .md-seg button { font:inherit; font-size:11px; color:#c9c9d6; background:rgba(255,255,255,.05); border:1px solid var(--line);
    border-radius:999px; padding:5px 10px; cursor:pointer; transition:border-color .2s, color .2s, background .2s; }
  #mood .md-chips button:hover, #mood .md-seg button:hover { color:var(--fg); border-color:rgba(255,255,255,.2); }
  #mood .md-chips button.on, #mood .md-seg button.on { color:#0a0a0a; background:var(--st); border-color:var(--st); }
  #mood .md-row { display:grid; grid-template-columns:96px 1fr; align-items:center; gap:8px; padding:5px 0; }
  #mood .md-row + .md-row { border-top:1px solid var(--line); }
  #mood .md-row .l { font-size:11px; color:var(--dim); }
  #mood .md-row .l b { display:block; font-weight:400; color:var(--fg); font-size:11.5px; margin-top:1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #mood .md-sw { display:flex; gap:7px; flex-wrap:wrap; }
  #mood .md-sw button { width:26px; height:26px; border-radius:50%; border:0; padding:0; cursor:pointer; position:relative;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.18), 0 1px 4px rgba(0,0,0,.5); transition:transform .15s; }
  #mood .md-sw button:hover { transform:scale(1.08); }
  #mood .md-sw button.on { box-shadow:0 0 0 2px #0d0d12, 0 0 0 4px var(--or); }
  #mood .md-seg { display:flex; gap:6px; flex-wrap:wrap; }
  #mood .md-looks { display:grid; grid-template-columns:repeat(auto-fill, minmax(92px, 1fr)); gap:6px; margin-bottom:10px; }
  #mood .md-looks button { font:inherit; font-size:11px; color:#c9c9d6; text-align:left; background:rgba(255,255,255,.04); border:1px solid var(--line);
    border-radius:10px; padding:7px 8px 6px; cursor:pointer; transition:border-color .2s; }
  #mood .md-looks button:hover { border-color:rgba(255,255,255,.22); }
  #mood .md-looks button.on { border-color:var(--or); color:var(--fg); }
  #mood .md-looks i { display:flex; height:8px; border-radius:4px; overflow:hidden; margin-bottom:6px; }
  #mood .md-looks i u { flex:1; }
  #mood .md-hint { font-size:11px; color:var(--dim); line-height:1.45; margin-bottom:8px; }
  #mood button:disabled { opacity:.4; cursor:default; }
  #mood .md-foot { font-size:10px; color:var(--faint); margin-top:10px; line-height:1.45; }
  #mood .md-reset { font:inherit; font-size:10px; color:var(--dim); background:none; border:0; text-decoration:underline; cursor:pointer; padding:0; }
  @media (max-width: 900px) {
    #mood .md-row { grid-template-columns:84px 1fr; }
    #mood .md-sw button { width:30px; height:30px; }
  }`;
    document.head.appendChild(style);
    const sw = v => Array.isArray(v.sw) ? `linear-gradient(135deg, ${v.sw[0]} 0 55%, ${v.sw[1]} 55% 100%)` : v.sw;
    const card = document.createElement("div"); card.className = "card"; card.id = "mood";
    card.innerHTML = `
  <div class="k"><span>Room mood</span><span class="md-now" id="md-now"></span><button class="md-tog" id="md-tog" aria-expanded="true" aria-controls="md-body">hide</button></div>
  <div class="md-body" id="md-body">
    <div class="md-tabs" role="tablist">
      <button role="tab" data-tab="time" aria-selected="true">Time</button><button role="tab" data-tab="light" aria-selected="false">Mood</button><button role="tab" data-tab="mat" aria-selected="false">Materials</button><button role="tab" data-tab="arr" aria-selected="false">Arrange</button>
    </div>
    <section data-tab="time">
      <div class="md-clock"><b id="md-h">--:--</b><span id="md-st">live · Tokyo time</span></div>
      <div class="md-range"><div class="trk"></div><div class="live" id="md-live" title="now in Tokyo"></div>
        <input type="range" id="md-r" min="0" max="24" step="0.0166667" value="12" aria-label="preview the hour"></div>
      <div class="md-ticks"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div>
      <div class="md-chips" id="md-chips">${CHIPS.map(([l, h]) => `<button data-h="${h}">${l}</button>`).join("")}<button data-h="live">Live</button></div>
    </section>
    <section data-tab="light" hidden>
      <div class="md-looks" id="md-looks">${LOOKS.map(L => `<button data-look="${L.id}"><i>${["floor", "wall", "bed", "soft"].map(g => {
        const v = GROUPS[g].variants.find(x => x.id === L.set[g]); return `<u style="background:${v.sw}"></u>`; }).join("")}</i>${L.label}</button>`).join("")}</div>
      <div class="md-row"><div class="l">Lamps</div><div class="md-seg" id="md-lamps">${LAMPS.map(x => `<button data-lamps="${x}">${x === "auto" ? "By the hour" : x[0].toUpperCase() + x.slice(1)}</button>`).join("")}</div></div>
      <div class="md-row"><div class="l">Sunbeams</div><div class="md-seg" id="md-rays"><button data-rays="1">On</button><button data-rays="0">Off</button></div></div>
    </section>
    <section data-tab="mat" hidden>
      ${Object.entries(GROUPS).map(([g, G]) => `<div class="md-row"><div class="l">${G.label}<b id="md-n-${g}"></b></div><div class="md-sw" data-group="${g}">${
        G.variants.map(v => `<button data-v="${v.id}" title="${v.label}" aria-label="${G.label}: ${v.label}" style="background:${sw(v)}"></button>`).join("")}</div></div>`).join("")}
      <button class="md-reset" id="md-reset">back to the room as built</button>
    </section>
    <section data-tab="arr" hidden><div class="md-hint">the room is still loading…</div></section>
    <div class="md-foot">Only in your browser: what you pick here is kept on this device and never changes the room for anyone else.</div>
  </div>`;
    const side = document.getElementById("side");
    if (side) side.insertBefore(card, side.firstChild); else (host || document.body).appendChild(card);
    const $ = s => card.querySelector(s), $$ = s => [...card.querySelectorAll(s)];
    const range = $("#md-r");
    const begin = () => { state.dragging = true; state.back = null; };
    const end = () => { if (!state.dragging) return; state.dragging = false; state.holdUntil = state.now + HOLD_S; };
    range.addEventListener("pointerdown", begin); range.addEventListener("touchstart", begin, {passive: true});
    range.addEventListener("input", () => { state.back = null; state.preview = wrap24(+range.value); state.holdUntil = state.now + HOLD_S; });
    for (const ev of ["pointerup", "pointercancel", "touchend", "change", "blur"]) range.addEventListener(ev, end);
    range.addEventListener("keydown", () => { state.holdUntil = state.now + HOLD_S; });
    $("#md-chips").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.h === "live") goLive(); else setPreview(+b.dataset.h, true); });
    $$(".md-tabs button").forEach(b => b.addEventListener("click", () => {
      $$(".md-tabs button").forEach(x => x.setAttribute("aria-selected", String(x === b)));
      $$("section[data-tab]").forEach(s => { s.hidden = s.dataset.tab !== b.dataset.tab; });
      if (arrange) arrange.setActive(b.dataset.tab === "arr"); }));
    $$(".md-sw").forEach(row => row.addEventListener("click", e => { const b = e.target.closest("button"); if (b) apply(row.dataset.group, b.dataset.v); }));
    $("#md-looks").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
      const L = LOOKS.find(x => x.id === b.dataset.look); for (const g of Object.keys(L.set)) apply(g, L.set[g]); });
    $("#md-reset").addEventListener("click", () => { for (const g of Object.keys(GROUPS)) apply(g, GROUPS[g].variants[0].id); });
    $("#md-lamps").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; choice.lamps = b.dataset.lamps; saveChoice(choice); envKey = ""; sync(); });
    $("#md-rays").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; choice.rays = b.dataset.rays === "1"; saveChoice(choice); sync(); });
    $("#md-tog").addEventListener("click", () => { choice.open = !choice.open; saveChoice(choice); sync(); });
    function sync(){
      card.classList.toggle("shut", !choice.open);
      $("#md-tog").textContent = choice.open ? "hide" : "show"; $("#md-tog").setAttribute("aria-expanded", String(choice.open));
      for (const g of Object.keys(GROUPS)) {
        const v = GROUPS[g].variants.find(x => x.id === choice[g]);
        card.querySelectorAll(`.md-sw[data-group="${g}"] button`).forEach(b => b.classList.toggle("on", b.dataset.v === choice[g]));
        $(`#md-n-${g}`).textContent = v.label;
      }
      $$("#md-looks button").forEach(b => { const L = LOOKS.find(x => x.id === b.dataset.look); b.classList.toggle("on", Object.keys(L.set).every(g => choice[g] === L.set[g])); });
      $$("#md-lamps button").forEach(b => b.classList.toggle("on", b.dataset.lamps === choice.lamps));
      $$("#md-rays button").forEach(b => b.classList.toggle("on", (b.dataset.rays === "1") === choice.rays));
    }
    let shown = "";
    function tickUI(){
      const pv = state.preview !== null;
      const s = `${fmtHour(state.hour)}|${pv}|${fmtHour(state.real)}|${Math.ceil(Math.max(0, state.holdUntil - state.now))}|${!!state.back}`;
      if (s === shown) return; shown = s;
      $("#md-h").textContent = fmtHour(state.hour);
      const st = $("#md-st"); st.classList.toggle("pv", pv);
      st.textContent = !pv ? "live · Tokyo time" : state.back && state.back.then === "live" ? "back to live…"
        : state.dragging || state.holdUntil - state.now > 99 ? `preview · now ${fmtHour(state.real)}` : `preview · live in ${Math.ceil(Math.max(0, state.holdUntil - state.now))} s`;
      $("#md-now").innerHTML = pv ? `<i>preview</i> ${fmtHour(state.hour)}` : `${fmtHour(state.hour)} Tokyo`;
      if (!state.dragging) range.value = String(state.hour);
      $("#md-live").style.left = `calc(${(state.real / 24 * 100).toFixed(2)}% + ${(10 - 20 * state.real / 24).toFixed(1)}px)`;
      $$("#md-chips button").forEach(b => b.classList.toggle("on", b.dataset.h === "live" ? !pv : pv && Math.abs(hourDelta(+b.dataset.h, state.hour)) < 0.02));
    }
    sync();
    const tab = () => (card.querySelector('.md-tabs button[aria-selected="true"]') || {}).dataset?.tab;
    return {card, sync, tick: tickUI, tab};
  }

  return {
    tune: T, tick, light, onRoom, apply, setPreview, goLive, choice, state, GROUPS, LOOKS,
    get hour(){ return state.hour; },
    get ui(){ return ui && ui.card; },
    get arrange(){ return arrange; },
    // (tests: what the mood layer has done)
    info: () => ({hour: state.hour, real: state.real, preview: state.preview, choice: {...choice}, roomK, deskK, nightK, direct: sDirect,
      beam: beam.visible ? +beamMat.uniforms.uI.value.toFixed(4) : 0, env: envKey, lite, arrange: arrange && arrange.info()}),
  };
}
