// SUB-01 room: the rendering layer on top of three.js (#98 G6). Pure parts first (quality tiers, the adaptive governor,
// the colour grade per time of day, the environment-map class of a material), then the scene helpers (sun shafts, the
// contact shadow under him, the captured room environment, shadow-map texel snapping) and the post-processing chain.
//
//   import { createPost, detectTier, gradeAt, SunShafts, ContactBlob, RoomEnv, snapShadow } from "./room_post.js";
//   const post = createPost(THREE, renderer, scene, camera, {tier, load: spec => import(spec)});
//   post.ready.then(...); every frame: post.frame(ms); post.grade(gradeAt(hour, state)); post.focus(d, k); post.render(dt);
//
// Chain (high): N8AO (ambient occlusion, replaces the RenderPass) -> UnrealBloom -> depth of field -> grade (ACES tone
// mapping, white balance, split toning, contrast, saturation, vignette, grain; sRGB out) -> SMAA. Medium: N8AO at half
// resolution, bloom, grade, FXAA. Low: no composer at all (renderer.render, MSAA from the canvas, the page's CSS
// vignette). Every pass is imported on its own and skipped when its import fails or throws, and a render that throws
// turns the composer off for good: the room always draws. Nothing here touches `window` or `document` at import time,
// so the pure parts run in node (tests/js/room_post_check.js).

export const TIERS = ["low", "medium", "high"];
// what each tier draws; `ao` is N8AO's resolution, `aa` the anti-aliasing pass after the grade
export const TIER_PASSES = {
  low:    {composer:false, ao:null,   aa:null,   bloom:false, dof:false, grain:false, shadow:1024, shafts:false, env:false},
  medium: {composer:true,  ao:"half", aa:"fxaa", bloom:true,  dof:false, grain:false, shadow:1024, shafts:true,  env:true},
  high:   {composer:true,  ao:"full", aa:"smaa", bloom:true,  dof:true,  grain:true,  shadow:2048, shafts:true,  env:true},
};
export const SPECS = {                               // what each pass imports (the page's import map resolves them)
  composer:["three/addons/postprocessing/EffectComposer.js", "three/addons/postprocessing/RenderPass.js", "three/addons/postprocessing/ShaderPass.js"],
  ao:["n8ao"], smaa:["three/addons/postprocessing/SMAAPass.js"], fxaa:["three/addons/shaders/FXAAShader.js"],
  bloom:["three/addons/postprocessing/UnrealBloomPass.js"],
};

// ---------- quality tier from what the device says about itself ----------
// env: {gpu (UNMASKED_RENDERER), mobile, memory (GB, navigator.deviceMemory), cores, width (CSS px), dpr, software}
export function detectTier(env = {}){
  const gpu = String(env.gpu || "").toLowerCase();
  if (env.software || /swiftshader|llvmpipe|software|microsoft basic render/.test(gpu)) return "low";
  const weakMobile = /mali-(4|t|g3|g5)|mali-g7[0-6]\b|adreno \(tm\) [1-5]|adreno \(tm\) 6[01]\d|powervr|apple a([4-9]|1[01])\b|videocore/.test(gpu);
  const weakDesktop = /intel.*(hd|uhd) graphics [2-6]\d\d|intel.*(hd|uhd) graphics\b(?! 7)|iris\b(?! xe)|gma |radeon (hd|r5|r7)/.test(gpu);
  const lowMemory = env.memory != null && env.memory <= 3, fewCores = env.cores != null && env.cores <= 4;
  if (env.mobile || (env.width && env.width <= 900)) {
    if (weakMobile || lowMemory || (fewCores && lowMemory)) return "low";
    return "medium";                                  // phones start mid: the governor raises it after 12 s of fast frames
  }
  if (weakDesktop || lowMemory) return "medium";
  return "high";
}

// ---------- the adaptive governor: drops a tier on slow frames, raises it back after a while of fast ones ----------
// frame(ms) takes one frame's duration and returns the new tier, or null. Windows of ~1 s; the slowest frame of each
// window is left out (one hitch, a shader compile, is not "slow"). It waits while the page can still lower its pixel
// ratio (cheaper first), drops after `dropAfter` slow windows in a row, raises after `raiseAfter` fast ones, and a tier
// that failed before is retried only after `retryWindows` windows.
export class Governor {
  constructor(opts = {}){
    Object.assign(this, {tiers:TIERS, tier:"high", slowMs:30, fastMs:17, dropAfter:2, raiseAfter:12, retryWindows:90, windowMs:1000}, opts);
    this.n = 0; this.sum = 0; this.max = 0; this.slow = 0; this.fast = 0; this.failed = {}; this.windows = 0;
  }
  frame(ms, {canDropDpr = false} = {}){
    if (!(ms > 0) || ms > 1000) { this.n = this.sum = this.max = 0; return null; }   // a hidden tab coming back
    this.n++; this.sum += ms; this.max = Math.max(this.max, ms);
    if (this.sum < this.windowMs || this.n < 3) return null;
    const avg = this.n > 1 ? (this.sum - this.max) / (this.n - 1) : this.sum; this.n = this.sum = this.max = 0; this.windows++;
    const i = this.tiers.indexOf(this.tier);
    if (avg > this.slowMs) {
      this.fast = 0;
      if (canDropDpr) return null;                     // resolution first
      if (++this.slow >= this.dropAfter && i > 0) { this.slow = 0; this.failed[this.tier] = this.windows; this.tier = this.tiers[i - 1]; return this.tier; }
      return null;
    }
    this.slow = 0;
    if (avg < this.fastMs && i < this.tiers.length - 1) {
      const up = this.tiers[i + 1];
      if (this.failed[up] != null && this.windows - this.failed[up] < this.retryWindows) return null;
      if (++this.fast >= this.raiseAfter) { this.fast = 0; this.tier = up; return up; }
    } else this.fast = 0;
    return null;
  }
}

// ---------- the colour grade per time of day ----------
// Keyframes by Tokyo hour, interpolated: white balance (linear RGB gains), saturation, contrast, lift (the black level),
// split toning (shadows / highlights tints), vignette strength. The lamp and the room light pull the evening towards the
// warm-highlights / teal-shadows look; night without them is cool and desaturated with lifted blue blacks.
const GRADES = [
  // hour, balance,              sat,  con,  lift,  shadows tint,          highs tint,            vig
  [ 0.0,  [0.93, 0.97, 1.09],   0.82, 1.12, 0.020, [0.85, 0.92, 1.12],   [0.98, 1.00, 1.04],    0.50],
  [ 4.5,  [0.93, 0.97, 1.09],   0.82, 1.12, 0.020, [0.85, 0.92, 1.12],   [0.98, 1.00, 1.04],    0.50],
  [ 6.0,  [1.04, 0.98, 0.95],   1.02, 1.04, 0.010, [0.92, 0.94, 1.08],   [1.06, 1.00, 0.94],    0.36],
  [ 8.0,  [1.03, 1.00, 0.96],   1.08, 1.06, 0.004, [0.96, 0.97, 1.04],   [1.03, 1.00, 0.97],    0.30],
  [12.0,  [0.99, 1.00, 1.03],   1.06, 1.08, 0.000, [0.97, 0.98, 1.03],   [1.00, 1.00, 1.00],    0.28],
  [15.0,  [1.00, 1.00, 1.01],   1.07, 1.07, 0.000, [0.96, 0.97, 1.04],   [1.02, 1.00, 0.98],    0.30],
  [17.3,  [1.08, 0.98, 0.90],   1.14, 1.05, 0.006, [0.88, 0.90, 1.10],   [1.08, 0.98, 0.90],    0.38],
  [19.0,  [1.00, 0.98, 0.97],   1.00, 1.10, 0.012, [0.86, 0.94, 1.10],   [1.06, 1.00, 0.92],    0.45],
  [22.0,  [0.98, 0.98, 1.00],   0.95, 1.11, 0.016, [0.86, 0.93, 1.11],   [1.04, 1.00, 0.95],    0.48],
  [24.0,  [0.93, 0.97, 1.09],   0.82, 1.12, 0.020, [0.85, 0.92, 1.12],   [0.98, 1.00, 1.04],    0.50],
];
const lerp = (a, b, t) => a + (b - a) * t, lerp3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
export function gradeAt(hour, s = {}){
  const h = ((hour % 24) + 24) % 24;
  let i = 0; while (i < GRADES.length - 2 && GRADES[i + 1][0] <= h) i++;
  const A = GRADES[i], B = GRADES[i + 1], t = Math.min(1, Math.max(0, (h - A[0]) / (B[0] - A[0])));
  const g = {balance:lerp3(A[1], B[1], t), sat:lerp(A[2], B[2], t), contrast:lerp(A[3], B[3], t), lift:lerp(A[4], B[4], t),
    shadows:lerp3(A[5], B[5], t), highs:lerp3(A[6], B[6], t), vignette:lerp(A[7], B[7], t), grain:0.028};
  const lamp = s.lampOn || 0, room = s.roomOn || 0, day = s.day == null ? 1 : s.day;
  const warm = (1 - day) * Math.max(lamp, 0.7 * room);          // practicals on at night: warm highlights, teal shadows, a bit more colour
  g.highs = lerp3(g.highs, [1.10, 0.99, 0.88], 0.6 * warm); g.shadows = lerp3(g.shadows, [0.82, 0.94, 1.10], 0.5 * warm);
  g.sat = lerp(g.sat, 1.02, 0.5 * warm); g.lift = lerp(g.lift, 0.008, 0.5 * warm);
  return g;
}

// ---------- how much of the environment map each material class reflects ----------
// (multiplies the page's overall level, which follows the light): metal and glass reflect, fabric does not
export function envClassOf(name = ""){
  const n = name.toLowerCase();
  if (/glass|screen|led/.test(n)) return 1.0;
  if (/steel|metal|chrome|alarm_clock|wall_clock(?!_glass)/.test(n)) return 0.9;
  if (/plastic|white|painted|pot\b|potted_plant_\d+_pot|cardboard|notepads|bag|cable|lamp/.test(n)) return 0.45;
  if (/oak|door|floor|wood/.test(n)) return 0.35;
  if (/wall|cut|posters|pinboard/.test(n)) return 0.2;
  if (/fabric|sheet|duvet|curtain|rug|cushion|hoodie|hp_pad|leaves|dirt|towel|sock/.test(n)) return 0.1;
  return 0.3;
}

// ---------- shadow-map texel snapping for a directional light (the frustum moves only in whole texels) ----------
const _m = {}, _v = {};
const upOf = T => _v.up || (_v.up = new T.Vector3(0, 1, 0));
export function snapShadow(THREE, light, mapSize){
  const cam = light.shadow.camera, texel = (cam.right - cam.left) / mapSize;
  if (!(texel > 0) || !isFinite(texel)) return 0;
  _m.rot = _m.rot || new THREE.Matrix4(); _m.inv = _m.inv || new THREE.Matrix4(); _v.p = _v.p || new THREE.Vector3(); _v.s = _v.s || new THREE.Vector3();
  _m.rot.lookAt(light.position, light.target.position, upOf(THREE));   // light space axes (rotation only)
  _m.inv.copy(_m.rot).transpose();
  _v.p.copy(light.position).applyMatrix4(_m.inv);
  const dx = _v.p.x - Math.round(_v.p.x / texel) * texel, dy = _v.p.y - Math.round(_v.p.y / texel) * texel;
  _v.s.set(dx, dy, 0).applyMatrix4(_m.rot);
  light.position.sub(_v.s); light.target.position.sub(_v.s);
  return Math.hypot(dx, dy);
}

// ---------- sun shafts: slices of the window's light, additive, fading into the room ----------
// Slices parallel to the window, one quad per pane per depth, following the sun's direction; depth-tested so furniture
// cuts them, never written to depth. set(dir, color, strength) every frame (cheap: uniforms and a few matrices).
export class SunShafts {
  constructor(THREE, win, {slices = 7, depth = 2.4, panes = 2} = {}){
    this.THREE = THREE; this.win = win; this.slices = slices; this.depth = depth; this.group = new THREE.Group(); this.group.name = "sun_shafts";
    this.mat = new THREE.ShaderMaterial({transparent:true, depthWrite:false, blending:THREE.AdditiveBlending, side:THREE.DoubleSide, toneMapped:false,
      uniforms:{uColor:{value:new THREE.Color(1, 0.9, 0.7)}, uStrength:{value:0}, uTime:{value:0}},
      vertexShader:`attribute float aDepth; varying vec2 vUv; varying float vD; void main(){ vUv = uv; vD = aDepth; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader:`varying vec2 vUv; varying float vD; uniform vec3 uColor; uniform float uStrength; uniform float uTime;
        float h2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(h2(i), h2(i + vec2(1, 0)), f.x), mix(h2(i + vec2(0, 1)), h2(i + vec2(1, 1)), f.x), f.y); }
        void main(){
          vec2 e = smoothstep(0.0, 0.22, vUv) * smoothstep(1.0, 0.78, vUv);   // soft pane edges
          float edge = e.x * e.y;
          float dust = 0.7 + 0.3 * vn(vUv * vec2(4.0, 6.0) + vec2(uTime * 0.02, -uTime * 0.035) + vD * 3.0);
          float a = uStrength * exp(-vD * 1.25) * edge * dust * (1.0 - 0.35 * vD);
          gl_FragColor = vec4(uColor * a, a * 0.9);
        }`});
    this.meshes = [];
    const w = win.w, h = win.h, mul = win.mullion, hasMullion = mul != null && mul >= 0 && mul <= 1;
    const paneList = hasMullion && panes > 1 ? [[0, mul], [mul, 1]] : [[0, 1]];
    for (const [u0, u1] of paneList) for (let k = 0; k < slices; k++) {
      const pw = (u1 - u0) * w * 0.92, g = new THREE.PlaneGeometry(pw, h * 0.94);
      const d = (k + 0.5) / slices;
      g.setAttribute("aDepth", new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count).fill(d), 1));
      const m = new THREE.Mesh(g, this.mat); m.renderOrder = 3; m.frustumCulled = false; m.userData.d = d; m.userData.u = (u0 + u1) / 2 - 0.5;
      this.meshes.push(m); this.group.add(m);
    }
    this._dir = new THREE.Vector3(1, -0.5, 0); this._p = new THREE.Vector3(); this._n = new THREE.Vector3(); this._r = new THREE.Vector3();
    this.place(this._dir);
  }
  // dir: the sun's direction INTO the room (world); the slices stay parallel to the glass and slide along dir
  place(dir){
    const T = this.THREE, w = this.win, ry = w.ry;
    this._n.set(0, 0, 1).applyAxisAngle(upOf(T), ry);                                        // into the room, normal to the glass
    this._r.set(1, 0, 0).applyAxisAngle(upOf(T), ry);                                          // along the glass
    const along = Math.max(0.25, this._dir.copy(dir).normalize().dot(this._n));                // keep the slices in the room
    for (const m of this.meshes) {
      const t = m.userData.d * this.depth / along;                                              // distance along the beam
      this._p.set(w.c[0], w.c[1], w.c[2]).addScaledVector(this._r, m.userData.u * w.w).addScaledVector(this._dir, t);
      m.position.copy(this._p); m.rotation.set(0, ry, 0);
    }
  }
  set(dir, color, strength, time){
    if (dir) this.place(dir);
    this.mat.uniforms.uStrength.value = strength; if (color) this.mat.uniforms.uColor.value.copy(color);
    if (time != null) this.mat.uniforms.uTime.value = time;
    this.group.visible = strength > 0.002;
  }
  dispose(){ this.mat.dispose(); for (const m of this.meshes) m.geometry.dispose(); }
}

// ---------- the contact shadow under him: a soft dark disc on the floor under his feet, gone when the feet leave it ----------
export class ContactBlob {
  constructor(THREE, {size = 0.9, floorY = 0, strength = 0.5, canvas} = {}){
    this.strength = strength; this.floorY = floorY;
    const c = canvas || (typeof document !== "undefined" ? document.createElement("canvas") : null);
    let tex = null;
    if (c) { c.width = c.height = 128; const g = c.getContext("2d"), r = g.createRadialGradient(64, 64, 4, 64, 64, 62);
      r.addColorStop(0, "rgba(0,0,0,1)"); r.addColorStop(0.45, "rgba(0,0,0,0.55)"); r.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = r; g.fillRect(0, 0, 128, 128);
      tex = new THREE.CanvasTexture(c); }
    this.mat = new THREE.MeshBasicMaterial({color:0x000000, transparent:true, opacity:0, depthWrite:false, alphaMap:tex, polygonOffset:true, polygonOffsetFactor:-1, polygonOffsetUnits:-1});
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(size, size * 0.8), this.mat); this.mesh.rotation.x = -Math.PI / 2; this.mesh.renderOrder = 2;
    this.mesh.name = "contact_blob"; this.mesh.visible = false;
  }
  // x, z: under the hips; feetY: the lowest foot's height above the floor (world); heading: his rotation about y
  set(x, z, feetY, heading = 0, visible = true){
    const lift = Math.max(0, feetY - this.floorY), k = visible ? Math.max(0, 1 - lift / 0.22) : 0;
    this.mat.opacity = this.strength * k * k; this.mesh.visible = this.mat.opacity > 0.01;
    this.mesh.position.set(x, this.floorY + 0.004, z); this.mesh.rotation.z = heading;
    return k;
  }
}

// ---------- the room as its own environment map: a cube render from the room's centre, re-taken when the light changes ----------
export class RoomEnv {
  constructor(THREE, renderer, scene, {size = 128, position = [0, 1.3, 0.1], pmrem} = {}){
    this.THREE = THREE; this.renderer = renderer; this.scene = scene; this.pmrem = pmrem || new THREE.PMREMGenerator(renderer);
    this.rt = new THREE.WebGLCubeRenderTarget(size, {type:THREE.HalfFloatType, generateMipmaps:false});
    this.cam = new THREE.CubeCamera(0.05, 40, this.rt); this.cam.position.set(...position);
    this.key = null; this.texture = null; this._env = null; this.captures = 0;
  }
  // key: a short string of the quantised light state; hide: objects left out of the capture (him, the shafts, the blob)
  update(key, hide = []){
    if (key === this.key) return false;
    const was = hide.filter(o => o).map(o => [o, o.visible]); for (const [o] of was) o.visible = false;
    const target = this.renderer.getRenderTarget();
    try { this.cam.update(this.renderer, this.scene); }                 // linear light: no tone mapping on a render target
    finally { this.renderer.setRenderTarget(target); for (const [o, v] of was) o.visible = v; }
    const env = this.pmrem.fromCubemap(this.rt.texture);
    if (this._env) this._env.dispose(); this._env = env; this.texture = env.texture; this.key = key; this.captures++;
    return true;
  }
  dispose(){ this.rt.dispose(); if (this._env) this._env.dispose(); }
}

// ---------- the final pass: ACES tone mapping, the grade, vignette, grain, sRGB ----------
export const GRADE_SHADER = {
  uniforms:{tDiffuse:{value:null}, exposure:{value:1}, balance:{value:[1, 1, 1]}, sat:{value:1}, contrast:{value:1}, lift:{value:0},
    shadows:{value:[1, 1, 1]}, highs:{value:[1, 1, 1]}, vignette:{value:0.35}, grain:{value:0}, time:{value:0}, aspect:{value:1.6}},
  vertexShader:`varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader:`
    uniform sampler2D tDiffuse; uniform float exposure, sat, contrast, lift, vignette, grain, time, aspect; uniform vec3 balance, shadows, highs;
    varying vec2 vUv;
    vec3 RRTAndODTFit(vec3 v){ vec3 a = v * (v + 0.0245786) - 0.000090537; vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081; return a / b; }
    vec3 aces(vec3 c){   // three.js's ACESFilmicToneMapping (Stephen Hill's fit), exposure folded in
      const mat3 IN = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
      const mat3 OUT = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
      c *= exposure / 0.6; c = IN * c; c = RRTAndODTFit(c); c = OUT * c; return clamp(c, 0.0, 1.0); }
    vec3 toSRGB(vec3 c){ return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
    float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main(){
      vec3 c = texture2D(tDiffuse, vUv).rgb * balance;              // white balance in linear light
      c = aces(c);
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c *= mix(shadows, highs, smoothstep(0.12, 0.75, l));           // split toning
      c = (c - 0.5) * contrast + 0.5;
      c = c * (1.0 - lift) + lift;                                   // the black level
      c = mix(vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), c, sat);
      vec2 d = (vUv - 0.5) * vec2(aspect, 1.0) / vec2(max(aspect, 1.0), 1.0);
      float v = 1.0 - vignette * smoothstep(0.45, 1.05, length(d) * 1.45);
      c *= v;
      c += (hash(gl_FragCoord.xy + fract(time) * 100.0) - 0.5) * grain * (1.0 - 0.6 * l);
      gl_FragColor = vec4(toSRGB(clamp(c, 0.0, 1.0)), 1.0);
    }`,
};

// ---------- a light depth of field for the close camera modes (reads the scene depth already drawn; 12 taps) ----------
export const DOF_SHADER = {
  uniforms:{tDiffuse:{value:null}, tDepth:{value:null}, focus:{value:1.5}, aperture:{value:0}, maxBlur:{value:0.012}, near:{value:0.02}, far:{value:200}, aspect:{value:1.6}},
  vertexShader:`varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader:`
    uniform sampler2D tDiffuse, tDepth; uniform float focus, aperture, maxBlur, near, far, aspect; varying vec2 vUv;
    float viewZ(vec2 uv){ float z = texture2D(tDepth, uv).x; float ndc = z * 2.0 - 1.0; return (2.0 * near * far) / (far + near - ndc * (far - near)); }
    float coc(float z){ return clamp(aperture * abs(z - focus) / max(z, 0.05), 0.0, maxBlur); }
    void main(){
      float zc = viewZ(vUv), cc = coc(zc);
      vec4 sum = texture2D(tDiffuse, vUv); float wsum = 1.0;
      if (cc > 0.0005) {
        const vec2 P[12] = vec2[12](vec2(-0.326, -0.406), vec2(-0.840, -0.074), vec2(-0.696, 0.457), vec2(-0.203, 0.621), vec2(0.962, -0.195), vec2(0.473, -0.480),
          vec2(0.519, 0.767), vec2(0.185, -0.893), vec2(0.507, 0.064), vec2(0.896, 0.412), vec2(-0.322, -0.933), vec2(-0.792, -0.598));
        for (int i = 0; i < 12; i++) {
          vec2 o = P[i] * cc * vec2(1.0 / aspect, 1.0); vec2 uv = vUv + o;
          float cs = coc(viewZ(uv)); float w = cs >= cc * 0.6 ? 1.0 : 0.25;     // a sharp thing in front does not bleed
          sum += texture2D(tDiffuse, uv) * w; wsum += w; }
      }
      gl_FragColor = sum / wsum;
    }`,
};

// ---------- the post-processing chain ----------
export function createPost(THREE, renderer, scene, camera, opts = {}){ return new Post(THREE, renderer, scene, camera, opts); }
export class Post {
  constructor(THREE, renderer, scene, camera, opts = {}){
    this.THREE = THREE; this.renderer = renderer; this.scene = scene; this.camera = camera;
    this.load = opts.load || (spec => import(spec));
    this.tier = TIERS.includes(opts.tier) ? opts.tier : "high";
    this.governor = new Governor({tier:this.tier, ...(opts.governor || {})});
    this.mods = {}; this.failed = {}; this.passes = {}; this.composer = null; this.active = false; this.broken = null; this.chain = [];
    this.width = 1; this.height = 1; this.dpr = 1; this.time = 0; this._focus = {d:1.5, k:0};
    this.onTier = opts.onTier || null; this.hdrScreens = 1.25;   // how much brighter a lit screen is drawn in HDR, so that it blooms
    this.fixed = !!opts.fixed;                                    // ?post=<tier>: the governor never changes it
    this.ready = this._load();
  }
  tiers(){ return TIERS.slice(); }
  get hdr(){ return this.active && TIER_PASSES[this.tier].composer; }
  async _load(){
    await Promise.resolve();                                      // never apply a tier inside the constructor (the page's callbacks come later)
    const T = this.THREE, R = this.renderer, caps = R.capabilities || {};
    const webgl2 = caps.isWebGL2 !== false;
    const ext = R.extensions && R.extensions.has ? (R.extensions.has("EXT_color_buffer_float") || R.extensions.has("EXT_color_buffer_half_float")) : true;
    this.rtType = ext && webgl2 ? T.HalfFloatType : T.UnsignedByteType;
    if (!webgl2) { this.failed.composer = "no WebGL2"; return this._apply(); }
    const get = async (name) => { try { const ms = await Promise.all(SPECS[name].map(s => this.load(s))); this.mods[name] = Object.assign({}, ...ms); return true; }
      catch (e) { this.failed[name] = String(e && e.message || e); return false; } };
    if (!(await get("composer"))) return this._apply();
    await Promise.all(["ao", "smaa", "fxaa", "bloom"].map(get));
    try { this._build(); } catch (e) { this.failed.composer = "build: " + String(e && e.message || e); this.composer = null; }
    return this._apply();
  }
  _build(){
    const T = this.THREE, M = this.mods, R = this.renderer, w = Math.max(1, Math.round(this.width * this.dpr)), h = Math.max(1, Math.round(this.height * this.dpr));
    const rt = new T.WebGLRenderTarget(w, h, {type:this.rtType, depthTexture:new T.DepthTexture(w, h, T.UnsignedIntType)});
    rt.texture.name = "room_post.rt";
    this.composer = new M.composer.EffectComposer(R, rt);
    this.composer.setPixelRatio(this.dpr);
    const P = this.passes;
    P.render = new M.composer.RenderPass(this.scene, this.camera);
    if (M.ao) { try { const ao = new M.ao.N8AOPass(this.scene, this.camera, w, h);
      Object.assign(ao.configuration, {aoRadius:0.6, distanceFalloff:0.25, intensity:2.6, aoSamples:12, denoiseSamples:6, denoiseRadius:10, gammaCorrection:false,
        screenSpaceRadius:false, halfRes:false, transparencyAware:false});
      P.ao = ao; } catch (e) { this.failed.ao = "pass: " + String(e && e.message || e); } }
    if (M.bloom) { try { P.bloom = new M.bloom.UnrealBloomPass(new T.Vector2(w, h), 0.32, 0.45, 0.92); } catch (e) { this.failed.bloom = String(e && e.message || e); } }
    P.dof = new M.composer.ShaderPass({uniforms:T.UniformsUtils.clone(DOF_SHADER.uniforms), vertexShader:DOF_SHADER.vertexShader, fragmentShader:DOF_SHADER.fragmentShader});
    P.grade = new M.composer.ShaderPass({uniforms:T.UniformsUtils.clone(GRADE_SHADER.uniforms), vertexShader:GRADE_SHADER.vertexShader, fragmentShader:GRADE_SHADER.fragmentShader});
    P.grade.material.toneMapped = false;
    if (M.smaa) { try { P.smaa = new M.smaa.SMAAPass(w, h); } catch (e) { this.failed.smaa = String(e && e.message || e); } }
    if (M.fxaa) { try { P.fxaa = new M.composer.ShaderPass(M.fxaa.FXAAShader); } catch (e) { this.failed.fxaa = String(e && e.message || e); } }
    this.rt = rt;
  }
  // the pass list of the current tier; a pass that is missing is just left out
  _apply(){
    const C = this.composer, cfg = TIER_PASSES[this.tier], P = this.passes;
    this.active = !!(C && cfg.composer && !this.broken);
    if (!this.active) { this.chain = []; if (this.onTier) this.onTier(this.tier, this.info()); return this; }
    C.passes.length = 0;
    const chain = [];
    if (P.ao && cfg.ao) { P.ao.configuration.halfRes = cfg.ao === "half"; P.ao.configuration.aoSamples = cfg.ao === "half" ? 8 : 12;
      P.ao.configuration.denoiseSamples = cfg.ao === "half" ? 4 : 6; chain.push(["ao", P.ao]); }
    else chain.push(["render", P.render]);
    if (P.bloom && cfg.bloom) chain.push(["bloom", P.bloom]);
    if (P.dof && cfg.dof) chain.push(["dof", P.dof]);
    chain.push(["grade", P.grade]);
    if (cfg.aa === "smaa" && P.smaa) chain.push(["smaa", P.smaa]); else if (cfg.aa && P.fxaa) chain.push(["fxaa", P.fxaa]);
    for (const [, p] of chain) { p.renderToScreen = false; C.addPass(p); }
    chain[chain.length - 1][1].renderToScreen = true;
    this.chain = chain.map(c => c[0]);
    this._depth();
    this.setSize(this.width, this.height, this.dpr);
    if (this.onTier) this.onTier(this.tier, this.info());
    return this;
  }
  _depth(){ const P = this.passes; if (!P.dof) return;
    const tex = this.chain.includes("ao") && P.ao.beautyRenderTarget ? P.ao.beautyRenderTarget.depthTexture : this.rt && this.rt.depthTexture;
    P.dof.uniforms.tDepth.value = tex || null; P.dof.enabled = !!tex && this._focus.k > 0; }
  setTier(tier, force = false){
    if (!TIERS.includes(tier) || (tier === this.tier && !force)) return this.tier;
    this.tier = tier; this.governor.tier = tier; this._apply(); return tier;
  }
  // one frame's duration; the governor may change the tier (returns it) -- `canDropDpr`: the page still has resolution to give
  frame(ms, canDropDpr = false){ if (this.fixed) return null; const t = this.governor.frame(ms, {canDropDpr}); if (t) this.setTier(t); return t; }
  setSize(w, h, dpr = this.dpr){
    this.width = w; this.height = h; this.dpr = dpr; const W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
    if (!this.composer) return;
    this.composer.setPixelRatio(dpr); this.composer.setSize(w, h);
    const P = this.passes;
    if (P.fxaa) P.fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
    if (P.grade) P.grade.uniforms.aspect.value = W / H;
    if (P.dof) P.dof.uniforms.aspect.value = W / H;
    if (P.ao && P.ao.setSize) P.ao.setSize(W, H);
    this._depth();
  }
  // the grade of the moment (see gradeAt) and the renderer's exposure
  grade(g){ const P = this.passes; if (!P.grade) return;
    const u = P.grade.uniforms, cfg = TIER_PASSES[this.tier];
    u.exposure.value = this.renderer.toneMappingExposure;
    const set = (k, v) => { const x = u[k].value; if (x && x.set) x.set(v[0], v[1], v[2]); else if (Array.isArray(x)) { x[0] = v[0]; x[1] = v[1]; x[2] = v[2]; } else u[k].value = v; };
    set("balance", g.balance); set("shadows", g.shadows); set("highs", g.highs);
    u.sat.value = g.sat; u.contrast.value = g.contrast; u.lift.value = g.lift; u.vignette.value = g.vignette; u.grain.value = cfg.grain ? g.grain : 0;
  }
  // depth of field: focus distance (view space, m) and strength 0..1 (0: the pass is skipped)
  focus(d, k){ this._focus = {d, k}; const P = this.passes; if (!P.dof) return;
    P.dof.uniforms.focus.value = d; P.dof.uniforms.aperture.value = 0.045 * k; P.dof.uniforms.near.value = this.camera.near; P.dof.uniforms.far.value = this.camera.far;
    P.dof.enabled = k > 0.01 && !!P.dof.uniforms.tDepth.value; }
  render(dt = 0.016){
    this.time += dt;
    if (this.passes.grade) this.passes.grade.uniforms.time.value = this.time;
    if (this.active) {
      // without N8AO the scene depth sits in whichever composer buffer the RenderPass draws into this frame (they alternate)
      if (this.chain[0] === "render" && this.passes.dof && this.passes.dof.enabled) this.passes.dof.uniforms.tDepth.value = (this.composer.writeBuffer && this.composer.writeBuffer.depthTexture) || this.rt.depthTexture;
      try { this.composer.render(dt); return "composer"; }
      catch (e) { this.broken = String(e && e.stack || e); this.active = false; this.chain = []; if (this.onTier) this.onTier(this.tier, this.info()); }
    }
    this.renderer.render(this.scene, this.camera); return "direct";
  }
  info(){
    const cfg = TIER_PASSES[this.tier];
    return {tier:this.tier, active:this.active, chain:this.chain || [], ao:!!(this.active && this.chain.includes("ao")), aa:this.active ? (this.chain.includes("smaa") ? "smaa" : this.chain.includes("fxaa") ? "fxaa" : null) : "msaa",
      bloom:!!(this.active && this.chain.includes("bloom")), dof:!!(this.active && this.chain.includes("dof") && this.passes.dof && this.passes.dof.enabled), grain:!!(this.active && cfg.grain),
      shadow:cfg.shadow, shafts:cfg.shafts, env:cfg.env, hdr:this.hdr, rtType:this.rtType === this.THREE.HalfFloatType ? "half" : "byte",
      failed:{...this.failed}, broken:this.broken, width:this.width, height:this.height, dpr:this.dpr};
  }
  dispose(){ for (const p of Object.values(this.passes)) if (p && p.dispose) try { p.dispose(); } catch {} if (this.rt) this.rt.dispose(); this.composer = null; this.active = false; }
}
