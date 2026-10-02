// The pure parts of web/room/window_view.js, run in node by tests/test_window_view.py (no WebGL here): the weather
// pattern's shares over a year of Tokyo hours, its smoothness, the lit-window probability by hour, the sun's elevation,
// and that the shader source compiles the view's contract (the layers, the uniforms, no brand words). Prints one JSON line.
import { weatherAt, litProbability, sunElevation, tokyoDayKey, createWindowView, LAYERS, GAIN, TRAIN, GROUND } from "../../web/room/window_view.js";

const out = {};
// a year of hours, every 10 minutes
let n = 0, rain = 0, overcast = 0, clear = 0, maxStep = 0, prev = null, switches = 0, prevKind = null;
const day0 = tokyoDayKey(new Date("2026-10-01T00:00:00Z"));
for (let d = 0; d < 365; d++) for (let h = 0; h < 24; h += 1 / 6) {
  const w = weatherAt(day0 + d, h);
  n++; if (w.kind === "rain") rain++; else if (w.kind === "overcast") overcast++; else clear++;
  if (prev) maxStep = Math.max(maxStep, Math.abs(w.cloud - prev.cloud), Math.abs(w.rain - prev.rain));
  if (prevKind && w.kind !== prevKind) switches++;
  prev = w; prevKind = w.kind;
}
out.weather = {rain: +(rain / n).toFixed(3), overcast: +(overcast / n).toFixed(3), clear: +(clear / n).toFixed(3),
  max_step_per_10min: +maxStep.toFixed(3), changes_per_day: +(switches / 365).toFixed(2)};
// the same clock gives the same weather (deterministic), the override values are in range
const a = weatherAt(20000, 13.5), b = weatherAt(20000, 13.5);
out.deterministic = a.kind === b.kind && a.cloud === b.cloud && a.rain === b.rain;
out.range_ok = [0, 3, 7.9, 12, 18.25, 23.9].every(h => { const w = weatherAt(20001, h); return w.cloud >= 0 && w.cloud <= 1 && w.rain >= 0 && w.rain <= 1 && w.cloud >= w.rain; });
// lights: evening high, small hours low, continuous
out.lit = {h20: +litProbability(20).toFixed(2), h3: +litProbability(3).toFixed(2), h12: +litProbability(12).toFixed(2), h24_eq_h0: Math.abs(litProbability(24) - litProbability(0)) < 1e-9};
let litJump = 0; for (let h = 0; h < 24; h += 0.05) litJump = Math.max(litJump, Math.abs(litProbability(h + 0.05) - litProbability(h)));
out.lit.max_jump_per_3min = +litJump.toFixed(3);
out.sun = {noon: +sunElevation(11.7).toFixed(3), midnight: +sunElevation(23.7).toFixed(3), rise: +sunElevation(5.6).toFixed(3)};
// the module builds its material with a THREE stub: the shader declares every texture and layer uniform it samples
class V2 { constructor(x = 0, y = 0){ this.x = x; this.y = y; } set(x, y){ this.x = x; this.y = y; return this; } }
class V3 extends V2 { constructor(x = 0, y = 0, z = 0){ super(x, y); this.z = z; } set(x, y, z){ this.x = x; this.y = y; this.z = z; return this; } }
class V4 extends V3 { constructor(x, y, z, w){ super(x, y, z); this.w = w; } }
const loads = [];
const THREE = {Vector2: V2, Vector3: V3, Vector4: V4, RepeatWrapping: 1, ClampToEdgeWrapping: 2, SRGBColorSpace: "srgb", NoColorSpace: "",
  TextureLoader: class { load(u){ loads.push(u); return {}; } },
  ShaderMaterial: class { constructor(o){ Object.assign(this, o); } },
  Mesh: class { constructor(g, m){ this.geometry = g; this.material = m; this.position = new V3(); this.rotation = new V3(); } },
  PlaneGeometry: class { constructor(w, h){ this.w = w; this.h = h; } }};
const view = createWindowView(THREE, {base: "room/window/"});
const frag = view.material.fragmentShader, vert = view.material.vertexShader, U = view.material.uniforms;
const samplers = [...frag.matchAll(/uniform sampler2D (t\w+)/g)].map(m => m[1]);
out.textures = {declared: samplers, loaded: loads.map(u => u.split("/").pop()), every_sampler_has_a_uniform: samplers.every(s => s in U && U[s].value)};
out.uniforms_declared = Object.keys(U).every(k => frag.includes(k) || vert.includes(k));
out.layers = {near: U.uNear.value.x === LAYERS.near.d, mid: U.uMid.value.x === LAYERS.mid.d, far: U.uFar.value.x === LAYERS.far.d, ground_y: U.uGroundY.value === GROUND,
  train: U.uTrainP.value.x === TRAIN.d, order_ok: LAYERS.near.d < LAYERS.mid.d && LAYERS.mid.d < TRAIN.d && TRAIN.d < LAYERS.far.d};
out.gain = GAIN;
out.colorspace_included = frag.includes("#include <colorspace_fragment>");
// a simulated day of updates: the sun crosses left to right, the lights follow the hour, weather eases towards the override
const added = []; const scene = {add: m => added.push(m)};
view.build({c: [-2.012, 1.685, 0.14], w: 1.58, h: 0.89, ry: Math.PI / 2}, scene);
out.built = added.length === 1 && Math.abs(U.uSize.value.x - 1.58) < 1e-9;
view.update(0.016, 8); const sx8 = U.uSunDir.value.x; view.update(0.016, 16); const sx16 = U.uSunDir.value.x;
out.sun_crosses = sx8 < 0 && sx16 > 0;
view.update(0.016, 21); out.lit_uniform_follows_hour = Math.abs(U.uLitP.value - litProbability(21)) < 1e-9;
view.setWeather("rain"); for (let i = 0; i < 400; i++) view.update(0.05, 21);
out.rain_override = {rain: +U.uRain.value.toFixed(3), cloud: +U.uCloud.value.toFixed(3), sun_factor: +view.light.sun.toFixed(3)};
view.setWeather(null); out.state_kind_after_reset = view.state().weather.kind;
// a train passes: within one cycle uTrain becomes >= 0 for a while and the direction alternates between cycles
let seen = 0; let dirs = new Set(); for (let t = 0; t < TRAIN.every * 2; t += 0.5) { view.update(0.5, 21); if (U.uTrain.value >= -TRAIN.len) { seen++; dirs.add(U.uTrainDir.value); } }
out.train = {steps_visible: seen, directions: [...dirs].sort()};
// words that must not appear in the shader or the module (no brands, no real signage)
const src = (await import("fs")).readFileSync(new URL("../../web/room/window_view.js", import.meta.url), "utf8");
out.brand_free = !/\b(Sony|Toshiba|Hitachi|Coca|Suntory|Asahi|Kirin|7-?Eleven|Lawson|FamilyMart|Skytree|Tokyo Tower|JR\b|Chuo|Chūō)/i.test(src);
console.log(JSON.stringify(out));
