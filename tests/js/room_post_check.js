// Node check of web/room_post.js (#98 G6) with a minimal THREE stub (no WebGL) and stub passes: run by
// tests/test_room_post.py. Prints one JSON line: the pass chain per tier, the fallbacks when a pass's import fails or a
// render throws, the governor's tier changes on slow and fast frames, the device detection, the grade per hour, the
// environment class per material, shadow snapping, the sun shafts' placement, the contact blob and the captured
// environment's re-capture rule.
"use strict";
const path = require("path"), fs = require("fs"), os = require("os");
const root = path.resolve(__dirname, "..", "..");
// the module is ESM in a directory without a package.json: node < 22.7 reads a .js file there as CommonJS, so it is
// imported from a temporary .mjs copy (it has no relative imports)
function esmCopy(file) { const dir = fs.mkdtempSync(path.join(os.tmpdir(), "room-post-")); const out = path.join(dir, "room_post.mjs"); fs.copyFileSync(file, out); return out; }

// ---- a tiny THREE: only what the module touches ----
class V3 { constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; } copy(v) { return this.set(v.x, v.y, v.z); } clone() { return new V3(this.x, this.y, this.z); }
  add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; } sub(v) { this.x -= v.x; this.y -= v.y; this.z -= v.z; return this; }
  addScaledVector(v, s) { this.x += v.x * s; this.y += v.y * s; this.z += v.z * s; return this; }
  multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; } length() { return Math.hypot(this.x, this.y, this.z); }
  normalize() { const l = this.length() || 1; return this.multiplyScalar(1 / l); } dot(v) { return this.x * v.x + this.y * v.y + this.z * v.z; }
  cross(v) { const x = this.y * v.z - this.z * v.y, y = this.z * v.x - this.x * v.z, z = this.x * v.y - this.y * v.x; return this.set(x, y, z); }
  applyAxisAngle(axis, a) { // Rodrigues
    const c = Math.cos(a), s = Math.sin(a), k = axis.clone().normalize(), v = this.clone(), kv = k.clone().cross(v), kd = k.dot(v);
    return this.set(v.x * c + kv.x * s + k.x * kd * (1 - c), v.y * c + kv.y * s + k.y * kd * (1 - c), v.z * c + kv.z * s + k.z * kd * (1 - c)); }
  applyMatrix4(m) { const e = m.e, x = this.x, y = this.y, z = this.z;   // rotation + translation, w = 1
    return this.set(e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]); } }
class M4 { constructor() { this.e = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; }
  copy(m) { this.e = m.e.slice(); return this; }
  lookAt(eye, target, up) { // three.js Matrix4.lookAt: z = eye - target (the camera looks down -z)
    const z = eye.clone().sub(target).normalize(), x = up.clone().cross(z).normalize(), y = z.clone().cross(x);
    this.e = [x.x, x.y, x.z, 0, y.x, y.y, y.z, 0, z.x, z.y, z.z, 0, 0, 0, 0, 1]; return this; }
  transpose() { const e = this.e, t = e.slice(); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) e[i * 4 + j] = t[j * 4 + i]; return this; } }
class Color { constructor(r = 1, g = 1, b = 1) { if (typeof r === "number" && g === undefined) { this.r = ((r >> 16) & 255) / 255; this.g = ((r >> 8) & 255) / 255; this.b = (r & 255) / 255; } else { this.r = r; this.g = g; this.b = b; } }
  copy(c) { this.r = c.r; this.g = c.g; this.b = c.b; return this; } set() { return this; } }
class Obj { constructor() { this.children = []; this.visible = true; this.position = new V3(); this.rotation = {x: 0, y: 0, z: 0, set(x, y, z) { this.x = x; this.y = y; this.z = z; }}; this.name = ""; this.userData = {}; }
  add(...o) { this.children.push(...o); return this; } }
class Geom { constructor(w = 1, h = 1) { this.attributes = {position: {count: 4}}; this.w = w; this.h = h; } setAttribute(k, a) { this.attributes[k] = a; } dispose() {} }
class Mat { constructor(p = {}) { Object.assign(this, p); this.uniforms = p.uniforms || {}; } dispose() {} }
class RT { constructor(w, h, o = {}) { this.width = w; this.height = h; this.texture = {name: ""}; this.depthTexture = o.depthTexture || null; this.samples = o.samples || 0; } dispose() {} }
const THREE = {
  Vector2: class V2 { constructor(x = 0, y = 0) { this.x = x; this.y = y; } set(x, y) { this.x = x; this.y = y; return this; } clone() { return new V2(this.x, this.y); } },
  Vector3: V3, Matrix4: M4, Color, Group: Obj, Mesh: class extends Obj { constructor(g, m) { super(); this.geometry = g; this.material = m; this.renderOrder = 0; } },
  PlaneGeometry: Geom, Float32BufferAttribute: class { constructor(a, n) { this.array = a; this.itemSize = n; } },
  ShaderMaterial: Mat, MeshBasicMaterial: Mat, CanvasTexture: class { constructor(c) { this.image = c; } }, DepthTexture: class { constructor(w, h, t) { this.w = w; this.h = h; this.type = t; } },
  WebGLRenderTarget: RT, WebGLCubeRenderTarget: class extends RT { constructor(s) { super(s, s); } },
  CubeCamera: class extends Obj { constructor(n, f, rt) { super(); this.rt = rt; this.updates = 0; this.seen = []; } update(r, scene) { this.updates++; this.seen.push(scene.children.map(o => o.visible)); } },
  PMREMGenerator: class { constructor() { this.n = 0; } fromCubemap(t) { this.n++; return {texture: {from: t, n: this.n}, dispose() {}}; } },
  UniformsUtils: {clone: u => { const o = {}; for (const [k, v] of Object.entries(u)) o[k] = {value: v.value && v.value.clone ? v.value.clone() : Array.isArray(v.value) ? v.value.slice() : v.value}; return o; }},
  HalfFloatType: "half", UnsignedByteType: "byte", UnsignedIntType: "uint", AdditiveBlending: 2, DoubleSide: 2,
};

// ---- stub passes, as the page's import map would give them ----
function mods(fail = new Set()) {
  class Pass { constructor() { this.enabled = true; this.renderToScreen = false; this.sized = null; } setSize(w, h) { this.sized = [w, h]; } dispose() {} }
  class EffectComposer { constructor(r, rt) { this.renderer = r; this.rt = rt; this.passes = []; this.renders = 0; this.size = null; this.pr = 1; this.writeBuffer = rt; }
    addPass(p) { this.passes.push(p); p.setSize(1, 1); } setSize(w, h) { this.size = [w, h]; } setPixelRatio(p) { this.pr = p; }
    render() { this.renders++; if (this.renderer.throwOnComposer) throw new Error("composer boom"); } }
  class RenderPass extends Pass { constructor(s, c) { super(); this.kind = "render"; } }
  class ShaderPass extends Pass { constructor(sh) { super(); this.uniforms = THREE.UniformsUtils.clone(sh.uniforms); this.material = {uniforms: this.uniforms, toneMapped: true}; this.fs = sh.fragmentShader; }
    get resolution() { return this.uniforms.resolution; } }
  class N8AOPass extends Pass { constructor(s, c, w, h) { super(); this.kind = "ao"; this.configuration = {}; this.beautyRenderTarget = {depthTexture: {tag: "n8ao-depth"}}; } }
  class SMAAPass extends Pass { constructor(w, h) { super(); this.kind = "smaa"; } }
  class UnrealBloomPass extends Pass { constructor(res, s, r, t) { super(); this.kind = "bloom"; this.strength = s; this.radius = r; this.threshold = t; } }
  const FXAAShader = {uniforms: {tDiffuse: {value: null}, resolution: {value: new THREE.Vector2(1 / 1024, 1 / 512)}}, vertexShader: "", fragmentShader: ""};
  const table = {
    "three/addons/postprocessing/EffectComposer.js": {EffectComposer}, "three/addons/postprocessing/RenderPass.js": {RenderPass},
    "three/addons/postprocessing/ShaderPass.js": {ShaderPass}, "n8ao": {N8AOPass}, "three/addons/postprocessing/SMAAPass.js": {SMAAPass},
    "three/addons/shaders/FXAAShader.js": {FXAAShader}, "three/addons/postprocessing/UnrealBloomPass.js": {UnrealBloomPass},
  };
  return async spec => { if (fail.has(spec) || [...fail].some(f => spec.includes(f))) throw new Error("cannot import " + spec); if (!table[spec]) throw new Error("unknown " + spec); return table[spec]; };
}
function renderer() { return {toneMappingExposure: 0.9, capabilities: {isWebGL2: true}, extensions: {has: () => true}, direct: 0, throwOnComposer: false,
  render() { this.direct++; }, getRenderTarget() { return null; }, setRenderTarget() {}}; }
const camera = {near: 0.02, far: 200};

async function main() {
  const P = await import(esmCopy(path.join(root, "web", "room_post.js")));
  const out = {tiers: P.TIERS, chains: {}, fallbacks: {}, governor: {}, detect: {}, grade: {}, env: {}, snap: {}, shafts: {}, blob: {}, roomenv: {}};
  const scene = new Obj();
  // chains per tier, and the fallback when the resolution of a tier is forced
  const r = renderer(), post = P.createPost(THREE, r, scene, camera, {tier: "high", load: mods()});
  post.setSize(1280, 800, 1.5);
  await post.ready;
  for (const t of P.TIERS) { post.setTier(t); const info = post.info(); out.chains[t] = {chain: info.chain, active: info.active, mode: post.render(0.016), halfRes: post.passes.ao.configuration.halfRes,
    msaa: post.composer === post.composers.msaa,
    dof: info.dof, aa: info.aa, bloom: info.bloom, grain: info.grain, shadow: info.shadow, env: info.env, shafts: info.shafts, hdr: info.hdr}; }
  post.setTier("high"); post.focus(1.2, 1); out.chains.high.dof_on = post.info().dof; out.chains.high.depth_from = post.passes.dof.uniforms.tDepth.value && post.passes.dof.uniforms.tDepth.value.tag;
  post.focus(1.2, 0); out.chains.high.dof_off = post.info().dof;
  post.grade(P.gradeAt(19, {day: 0, lampOn: 1})); out.chains.high.grade_exposure = post.passes.grade.uniforms.exposure.value; out.chains.high.grade_grain = post.passes.grade.uniforms.grain.value;
  post.setTier("medium"); post.grade(P.gradeAt(19, {day: 0, lampOn: 1})); out.chains.medium.grade_grain = post.passes.grade.uniforms.grain.value;
  out.chains.sizes = {fxaa: post.passes.fxaa.uniforms.resolution.value, composer: post.composer.size, pr: post.composer.pr, rt: [post.rt.width, post.rt.height]};
  // fallbacks: no AO module, no AA modules, no composer at all, a composer that throws while rendering, no WebGL2
  const noAo = P.createPost(THREE, renderer(), scene, camera, {tier: "high", load: mods(new Set(["n8ao"]))}); await noAo.ready; noAo.focus(1, 1);
  out.fallbacks.no_ao = {chain: noAo.info().chain, failed: Object.keys(noAo.info().failed), depth_from_rt: noAo.passes.dof.uniforms.tDepth.value === noAo.rt.depthTexture, mode: noAo.render()};
  const noAa = P.createPost(THREE, renderer(), scene, camera, {tier: "high", load: mods(new Set(["SMAAPass", "FXAAShader"]))}); await noAa.ready;
  out.fallbacks.no_aa = {chain: noAa.info().chain, aa: noAa.info().aa};
  const rc = renderer(), noC = P.createPost(THREE, rc, scene, camera, {tier: "high", load: mods(new Set(["EffectComposer"]))}); await noC.ready;
  out.fallbacks.no_composer = {active: noC.active, mode: noC.render(), direct: rc.direct, failed: noC.info().failed.composer, chain: noC.info().chain, aa: noC.info().aa};
  const rb = renderer(), boom = P.createPost(THREE, rb, scene, camera, {tier: "high", load: mods()}); await boom.ready; rb.throwOnComposer = true;
  out.fallbacks.render_throws = {first: boom.render(), second: boom.render(), direct: rb.direct, broken: !!boom.info().broken, active: boom.active};
  const r1 = renderer(); r1.capabilities.isWebGL2 = false; const noGl2 = P.createPost(THREE, r1, scene, camera, {tier: "high", load: mods()}); await noGl2.ready;
  out.fallbacks.no_webgl2 = {active: noGl2.active, mode: noGl2.render(), failed: noGl2.info().failed.composer};
  const r2 = renderer(); r2.extensions.has = () => false; const noHalf = P.createPost(THREE, r2, scene, camera, {tier: "high", load: mods()}); await noHalf.ready;
  out.fallbacks.no_half_float = {rtType: noHalf.info().rtType, active: noHalf.active};
  // bloom only when asked for (a faint lens veil), on the tiers with a composer
  const wb = P.createPost(THREE, renderer(), scene, camera, {tier: "high", load: mods(), bloom: true}); await wb.ready;
  out.fallbacks.bloom_opt = {high: wb.info().chain, medium: (wb.setTier("medium"), wb.info().chain), low: (wb.setTier("low"), wb.info().chain),
    strength: wb.passes.bloom.strength, threshold: wb.passes.bloom.threshold};
  // the governor through the Post: slow frames drop the tier (resolution first), fast ones raise it, a failed tier waits
  const g = P.createPost(THREE, renderer(), scene, camera, {tier: "high", load: mods(), governor: {windowMs: 1000}}); await g.ready;
  const run = (ms, n, canDropDpr = false) => { const changes = []; for (let i = 0; i < n; i++) { const t = g.frame(ms, canDropDpr); if (t) changes.push([i, t]); } return changes; };
  out.governor.slow_with_dpr_left = run(40, 100, true);        // 4 s of slow frames while the page can still lower its pixel ratio: nothing
  out.governor.slow = run(40, 100);                            // then: high -> medium after 2 windows, -> low after 2 more
  out.governor.tier_after_slow = g.tier;
  out.governor.fast_short = run(10, 1100);                     // 11 s of fast frames: medium failed 4 windows ago, so no raise yet
  out.governor.fast_retry = run(10, 100 * 95);                 // after the retry wait: low -> medium, then -> high
  out.governor.tier_after_fast = g.tier;
  out.governor.hitch_ignored = (() => { const h = new P.Governor({tier: "high"}); const c = []; for (let i = 0; i < 300; i++) { const t = h.frame(i % 60 === 0 ? 400 : 12); if (t) c.push(t); } return c; })();
  out.governor.hidden_tab = (() => { const h = new P.Governor({tier: "high"}); return h.frame(5000) === null && h.n === 0; })();
  // device detection
  const D = P.detectTier;
  out.detect = {
    desktop_nvidia: D({gpu: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)", mobile: false, memory: 8, cores: 12, width: 1920}),
    desktop_intel_uhd620: D({gpu: "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)", mobile: false, memory: 8, cores: 8, width: 1536}),
    desktop_apple: D({gpu: "ANGLE (Apple, Apple M2, OpenGL 4.1)", mobile: false, memory: 8, cores: 8, width: 1440}),
    iphone: D({gpu: "Apple GPU", mobile: true, memory: undefined, cores: 6, width: 390}),
    android_mid: D({gpu: "ANGLE (Qualcomm, Adreno (TM) 730, OpenGL ES 3.2)", mobile: true, memory: 8, cores: 8, width: 412}),
    android_weak: D({gpu: "ANGLE (ARM, Mali-G52 MC2, OpenGL ES 3.2)", mobile: true, memory: 3, cores: 8, width: 360}),
    android_adreno610: D({gpu: "Adreno (TM) 610", mobile: true, memory: 4, cores: 8, width: 360}),
    software: D({gpu: "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)))", mobile: false, memory: 16, cores: 8, width: 1280}),
    no_info_desktop: D({width: 1280}), no_info_phone: D({width: 390}),
  };
  // the grade per hour
  for (const h of [8, 14, 19, 23]) { const g0 = P.gradeAt(h, {day: h === 19 || h === 23 ? 0 : 1, lampOn: h === 19 ? 1 : 0, roomOn: h === 19 ? 1 : 0});
    out.grade[h] = {balance: g0.balance.map(x => +x.toFixed(3)), sat: +g0.sat.toFixed(3), contrast: +g0.contrast.toFixed(3), lift: +g0.lift.toFixed(3),
      highs: g0.highs.map(x => +x.toFixed(3)), shadows: g0.shadows.map(x => +x.toFixed(3)), vignette: +g0.vignette.toFixed(3)}; }
  out.grade.continuous = (() => { let maxJump = 0; let prev = P.gradeAt(0); for (let h = 0.05; h <= 24; h += 0.05) { const g1 = P.gradeAt(h);
    for (const k of ["sat", "contrast", "vignette", "lift"]) maxJump = Math.max(maxJump, Math.abs(g1[k] - prev[k])); for (let i = 0; i < 3; i++) maxJump = Math.max(maxJump, Math.abs(g1.balance[i] - prev.balance[i])); prev = g1; } return +maxJump.toFixed(4); })();
  out.grade.wraps = JSON.stringify(P.gradeAt(24)) === JSON.stringify(P.gradeAt(0)) && JSON.stringify(P.gradeAt(-1)) === JSON.stringify(P.gradeAt(23));
  // environment class per material
  for (const n of ["steel", "metal_dark", "wall_clock_glass", "screen", "oak", "floor", "wall", "duvet", "curtain", "rug", "hp_pad", "chair_fabric_black", "plastic_black", "desk_lamp_arm_01", "potted_plant_02_leaves", "unknown_thing", ""]) out.env[n || "(empty)"] = P.envClassOf(n);
  // shadow snapping: light-space x and y land on texel multiples, the direction is unchanged, the move is under a texel
  {
    const light = {position: new V3(-5.37, 3.9, 1.14), target: {position: new V3(0.2, 0.3, 0.1)}, shadow: {camera: {left: -3, right: 3}}};
    const dir0 = light.target.position.clone().sub(light.position).normalize();
    const moved = P.snapShadow(THREE, light, 2048), texel = 6 / 2048;
    const dir1 = light.target.position.clone().sub(light.position).normalize();
    const rot = new M4().lookAt(light.position, light.target.position, new V3(0, 1, 0)), inv = new M4().copy(rot).transpose();
    const p = light.position.clone().applyMatrix4(inv);
    const frac = v => Math.abs(v / texel - Math.round(v / texel));
    out.snap = {moved_under_texel: moved <= texel * Math.SQRT2 + 1e-9, on_grid: frac(p.x) < 1e-6 && frac(p.y) < 1e-6, dir_same: dir0.clone().sub(dir1).length() < 1e-9,
      second_call_zero: P.snapShadow(THREE, light, 2048) < 1e-9, bad_map: P.snapShadow(THREE, light, 0)};
  }
  // sun shafts: the window at x = -1.87 facing +x (ry = pi/2); every slice ends up inside the room along the sun's direction
  {
    const win = {c: [-1.872, 1.685, 0.14], w: 1.48, h: 0.8, ry: Math.PI / 2, mullion: 0.44};
    const S = new P.SunShafts(THREE, win, {slices: 6, depth: 2.4});
    const dir = new V3(5.6, -3.6, -1.0).normalize(); S.set(dir, new Color(1, 0.9, 0.7), 0.5, 3);
    const xs = S.meshes.map(m => m.position.x), ys = S.meshes.map(m => m.position.y);
    const onBeam = S.meshes.every(m => { const d = m.position.clone(); d.x -= win.c[0]; d.y -= win.c[1]; d.z -= win.c[2];
      const u = m.userData.u * win.w; d.z -= u * -1; /* along the glass: the r axis for ry = pi/2 is -z */ const t = d.dot(dir); const off = d.clone().sub(dir.clone().multiplyScalar(t)); return off.length() < 1e-6 && t > 0; });
    out.shafts = {slices: S.meshes.length, panes: new Set(S.meshes.map(m => m.userData.u)).size, inside_room: xs.every(x => x > win.c[0] + 0.05), descending: ys.every(y => y < win.c[1] + 1e-9),
      ordered: xs.every((x, i) => i === 0 || i % 6 === 0 || x > xs[i - 1]), on_beam: onBeam, visible: S.group.visible, uStrength: S.mat.uniforms.uStrength.value,
      hidden_when_zero: (S.set(null, null, 0), S.group.visible === false), max_depth: +Math.max(...xs.map(x => x - win.c[0])).toFixed(2)};
  }
  // the contact blob under his feet
  {
    const B = new P.ContactBlob(THREE, {floorY: 0.16, strength: 0.5, canvas: {getContext: () => ({createRadialGradient: () => ({addColorStop() {}}), fillRect() {}})}});
    const on = B.set(0.3, -0.2, 0.16, 1.0), lifted = B.set(0.3, -0.2, 0.16 + 0.08), hanging = B.set(-0.4, 0.4, 0.86), hidden = B.set(0, 0, 0.16, 0, false);
    out.blob = {on, on_opacity: +B.set(0.3, -0.2, 0.16).toFixed(3) && +B.mat.opacity.toFixed(3), lifted: +lifted.toFixed(3), hanging, hidden, y: B.mesh.position.y, visible_hanging: (B.set(0, 0, 0.86), B.mesh.visible)};
  }
  // the captured room environment: the same key is not re-taken, hidden objects are hidden during the capture and restored after
  {
    const sc = new Obj(); const a = new Obj(), b = new Obj(); sc.add(a, b);
    const E = new P.RoomEnv(THREE, renderer(), sc, {size: 64});
    const first = E.update("d1.0_r0_l0", [a]), again = E.update("d1.0_r0_l0", [a]), changed = E.update("d0.5_r1_l1", [a, null]);
    out.roomenv = {first, again, changed, captures: E.captures, updates: E.cam.updates, hidden_during: E.cam.seen[0], restored: a.visible && b.visible, has_texture: !!E.texture};
  }
  console.log(JSON.stringify(out));
}
main().catch(e => { console.error(e && e.stack || e); process.exit(1); });
