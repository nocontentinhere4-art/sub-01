// The view out of SUB-01's window (#98 G7): a Tokyo lane seen from a second-floor room in Kichijōji.
//
// One plane sits on the glass (the GLB's SURF_window marker). Its fragment shader casts the view ray from the real camera
// through each pixel of the glass and intersects it with virtual card planes behind the window: the house across the lane
// (near), a row of apartment blocks (mid), the far skyline (far), the street plane (ground) and the sky at infinity. So the
// outside has true parallax from every camera in the room, and nothing of it exists outside the glass (no geometry floats
// behind the wall). The cards are drawn by room_build/window_cards.py (CC0, no brands, no text), under 200 KB together.
//
//   import { createWindowView } from "./room/window_view.js";
//   const view = createWindowView(THREE, {base:"room/window/"});
//   view.build(SURF.window, scene);        // the plane at the marker (c, w, h, ry), like the old sky plane
//   view.update(dt, hour);                 // every frame: Tokyo hour (0..24), the clock moves everything
//   view.setWeather("rain" | "overcast" | "clear" | null);   // null: back to the daily pattern
//   view.light.sun                         // 0..1: how much direct sun the weather lets through (for the room's lights)
//
// Sky: night, blue hour, golden hour and day from the sun's elevation; sun and moon cross the window; clouds drift; stars
// and the city's glow at night; birds by day; a train crosses the viaduct in the gap between the blocks; windows switch on
// and off in the evening (each has an id in the lights mask; a hash of id and time slot decides). Weather: there is no
// weather feed in the server (nothing in live_server.py or life.py fetches one), so the weather is a deterministic daily
// pattern (weatherAt: smooth noise over Tokyo time with autumn-Tokyo shares, about a fifth of the hours wet), never
// presented as real. Rain streaks and drops on the glass refract the view; rain falls outside; the far layers haze over.
//
// Budget: one draw call, ~10 texture reads per glass pixel at most, no per-frame JS beyond a few uniforms.

export const GROUND = -8.2;                  // the street, metres below the window's centre line (a third-floor room)
// the diorama: depth behind the glass (m), the card's width (m, it wraps) and its y range (m) — must match window_cards.py
export const LAYERS = {
  near:   {d: 14.0,  xm: 16.0,  y0: -9.0,  y1: 7.0},
  mid:    {d: 30.0,  xm: 48.0,  y0: -10.0, y1: 14.0},
  far:    {d: 100.0, xm: 280.0, y0: -9.0,  y1: 41.0},
  ground: {tile: 24.0},
};
// perspective gains: 1 = the geometry above. The vertical gain flattens steep views, and the view rays are lifted by a
// slope `pitch` plus `pitchK` per metre the camera stands above the window's centre (up to `pitchMax`): the room's high
// overview camera looks down through the window at ~25°, and would only ever see the street; with the lift the horizon
// follows the camera up and the sky still shows from there. Standing at the window nothing is lifted. A diorama cheat,
// like a parallax-interior shader's depth setting: the parallax itself stays true.
export const GAIN = {h: 0.7, v: 0.5, pitch: 0.12, pitchK: 0.06, pitchMax: 0.4};
export const TRAIN = {d: 44.0, y: GROUND + 8.5, h: 3.3, len: 72.0, every: 150.0, speed: 17.0};   // on the viaduct of the mid card

export function sunElevation(hour){            // Tokyo, autumn: up ~05:35, down ~17:45 (the room's lighting uses the same curve)
  return Math.sin(Math.PI * (hour - 5.6) / 12.2);
}

// how many homes have their lights on, by Tokyo hour (the shader shows them only once the sky is dark enough)
const LIT = [[0, 0.42], [1, 0.30], [2, 0.14], [4, 0.10], [5, 0.22], [6, 0.36], [7, 0.30], [9, 0.20], [16, 0.25], [17.5, 0.55], [19, 0.78], [22, 0.74], [23, 0.55], [24, 0.42]];
export function litProbability(hour){
  const h = ((hour % 24) + 24) % 24;
  for (let i = 1; i < LIT.length; i++) if (h <= LIT[i][0]) { const [a, pa] = LIT[i - 1], [b, pb] = LIT[i]; return pa + (pb - pa) * (h - a) / (b - a); }
  return LIT[LIT.length - 1][1];
}

// ---- the weather pattern: deterministic, smooth in time, the same for every viewer (no feed exists; see the header)
const fract = x => x - Math.floor(x);
const hash1 = x => fract(Math.sin(x * 127.1 + 311.7) * 43758.5453);
function vnoise1(x){ const i = Math.floor(x), f = x - i, t = f * f * (3 - 2 * f); return hash1(i) + (hash1(i + 1) - hash1(i)) * t; }
const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
export function weatherAt(dayKey, hour){
  const t = dayKey * 24 + hour;                                  // Tokyo hours since the epoch
  const n = 0.62 * vnoise1(t / 20.0 + 3.1) + 0.38 * vnoise1(t / 6.0 + 71.7);  // fronts over days, showers over hours
  const rain = sstep(0.42, 0.28, n);                             // shares calibrated in tests/js/window_view_check.js
  const cloud = Math.max(sstep(0.60, 0.42, n), rain);
  return {kind: rain > 0.5 ? "rain" : cloud > 0.5 ? "overcast" : "clear", cloud, rain, n};
}
export function tokyoDayKey(date = new Date()){ return Math.floor((date.getTime() / 1000 + 9 * 3600) / 86400); }

// ---- the shader
const VERT = /* glsl */`
  uniform vec3 uLift;                                             // pitch, per metre of camera height, max
  varying vec2 vUv; varying vec3 vWorld; varying vec3 vRight; varying vec3 vUp; varying vec3 vOut; varying float vPitch;
  void main(){
    vUv = uv; vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz;
    vRight = normalize(modelMatrix[0].xyz); vUp = normalize(modelMatrix[1].xyz); vOut = -normalize(modelMatrix[2].xyz);
    vPitch = uLift.x + clamp(uLift.y * (cameraPosition.y - modelMatrix[3].y), 0.0, uLift.z);
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;

const FRAG = /* glsl */`
  varying vec2 vUv; varying vec3 vWorld; varying vec3 vRight; varying vec3 vUp; varying vec3 vOut; varying float vPitch;
  uniform vec2 uSize; uniform vec2 uGain; uniform float uTime; uniform float uSun; uniform float uRain; uniform float uCloud; uniform float uLitP;
  uniform vec3 uSunDir; uniform vec3 uMoonDir; uniform float uTrain; uniform float uTrainDir;
  uniform sampler2D tNear; uniform sampler2D tNearL; uniform sampler2D tMid; uniform sampler2D tMidL; uniform sampler2D tFar; uniform sampler2D tFarL;
  uniform sampler2D tGround; uniform sampler2D tNoise;
  uniform vec4 uNear; uniform vec4 uMid; uniform vec4 uFar;     // depth, width, y0, y1
  uniform float uGroundTile; uniform float uGroundY; uniform vec4 uTrainP;   // depth, y, height, length

  float h1(float x){ return fract(sin(x * 127.1 + 311.7) * 43758.5453); }
  float h2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  // the card at depth D: metres on its plane -> its texture
  vec4 card(sampler2D t, vec4 L, vec2 g, vec2 slope){
    vec2 p = g + slope * L.x;
    vec2 uv = vec2(p.x / L.y + 0.5, (p.y - L.z) / (L.w - L.z));
    if (uv.y <= 0.0 || uv.y >= 1.0) return vec4(0.0);
    return texture2D(t, uv);
  }
  // a home's window: on or off by a hash of its id and the time slot; kinds 50 red blink, 100 warm always, 200 cool always
  vec3 lights(sampler2D t, vec4 L, vec2 g, vec2 slope, float dark){
    vec4 m = card(t, L, g, slope);
    if (m.r < 0.12 || dark < 0.01) return vec3(0.0);
    float id = floor(m.b / m.r * 255.0 + 0.5), kind = m.g / m.r * 255.0;   // id and kind are premultiplied by the pane coverage
    float slot = floor(uTime / 120.0 + h1(id) * 9.0);
    float on = step(h1(id * 3.17 + slot * 17.7), uLitP);
    vec3 c = mix(vec3(1.0, 0.68, 0.36), vec3(0.72, 0.84, 1.0), step(0.78, h1(id + 5.0)));
    if (kind > 40.0 && kind < 60.0) { on = step(0.5, fract(uTime * 0.6 + h1(id))); c = vec3(1.5, 0.06, 0.02); }
    else if (kind > 90.0 && kind < 110.0) { on = 1.0; c = vec3(1.3, 0.95, 0.6); }
    else if (kind > 190.0) { on = 1.0; c = vec3(0.95, 1.05, 1.25); }
    return c * on * m.r * (0.22 + 0.4 * h1(id + 9.0)) * dark;
  }

  void main(){
    vec3 d = normalize(vWorld - cameraPosition);
    float dz = max(dot(d, vOut), 0.03);
    float dx = dot(d, vRight) * uGain.x, dy = dot(d, vUp) * uGain.y + vPitch * dz;
    vec2 g = (vUv - 0.5) * uSize;                                  // where on the glass, metres from its centre

    // --- phases of the day from the sun's elevation (-1..1)
    float day = smoothstep(0.02, 0.35, uSun);
    float golden = exp(-pow((uSun - 0.04) / 0.11, 2.0));
    float blue = exp(-pow((uSun + 0.12) / 0.07, 2.0));
    float night = 1.0 - smoothstep(-0.24, -0.06, uSun);
    float dark = 1.0 - smoothstep(-0.02, 0.22, uSun);              // lit windows show from sunset on

    // --- rain on the glass: drops refract the view (two scales, sliding down slowly), streaks run
    float dropA = 0.0;
    if (uRain > 0.002) {
      vec4 n1 = texture2D(tNoise, vUv * vec2(1.9, 1.0) + vec2(0.0, uTime * 0.010));
      vec2 off = (n1.ba - 0.5) * 2.0;
      dropA = length(off);
      dx += off.x * 0.014 * uRain; dy += off.y * 0.014 * uRain;
    }
    vec2 slope = vec2(dx, dy) / dz;                                 // metres sideways and up per metre of depth
    vec3 dir = normalize(vec3(dx, dy, dz));                        // the sky direction (x right, y up, z out)

    // --- the sky
    float w = night + blue + golden + day + 1e-3;
    vec3 zen = (night * vec3(0.004, 0.006, 0.020) + blue * vec3(0.020, 0.045, 0.150) + golden * vec3(0.10, 0.19, 0.44) + day * vec3(0.08, 0.26, 0.74)) / w;
    vec3 hor = (night * vec3(0.040, 0.030, 0.050) + blue * vec3(0.16, 0.14, 0.30) + golden * vec3(0.95, 0.46, 0.20) + day * vec3(0.56, 0.70, 0.90)) / w;
    vec3 mid = (night * vec3(0.012, 0.016, 0.045) + blue * vec3(0.06, 0.08, 0.22) + golden * vec3(0.42, 0.33, 0.42) + day * vec3(0.24, 0.46, 0.86)) / w;
    float e = max(dir.y, 0.0);
    vec3 sky = mix(hor, mid, smoothstep(0.0, 0.10, e)); sky = mix(sky, zen, smoothstep(0.06, 0.45, e));
    vec3 horizonCol = mix(hor, mid, 0.45);                          // the haze's colour: the low sky, a little greyer
    // the sun: a warm glow around it, a disc; the moon at night
    float cs = dot(dir, uSunDir);
    float sunVis = smoothstep(-0.08, 0.04, uSun) * (1.0 - 0.92 * uCloud);
    vec3 sunCol = mix(vec3(1.0, 0.45, 0.15), vec3(1.0, 0.96, 0.88), smoothstep(0.0, 0.3, uSun));
    sky += sunCol * sunVis * (0.22 * pow(max(cs, 0.0), 5.0) * (0.6 + golden) + 0.9 * pow(max(cs, 0.0), 90.0) + 3.0 * smoothstep(0.9990, 0.9996, cs));
    float cm = dot(dir, uMoonDir);
    float moon = smoothstep(0.99955, 0.99975, cm) * (1.0 - 0.9 * smoothstep(0.99955, 0.99975, dot(dir, normalize(uMoonDir + vec3(0.012, 0.004, 0.0)))));
    sky += vec3(0.95, 0.97, 1.0) * night * moon * (1.0 - 0.9 * uCloud) + vec3(0.25, 0.30, 0.45) * night * 0.05 * pow(max(cm, 0.0), 40.0) * (1.0 - uCloud);
    // overcast: greyer, darker, no sun
    float lum = dot(sky, vec3(0.3, 0.5, 0.2));
    sky = mix(sky, vec3(lum) * vec3(0.92, 0.95, 1.0) * 0.8, uCloud * 0.7);
    // stars (a hash per cell of the flattened sky), the city's glow at the horizon
    vec2 sp = dir.xz / (dir.y + 0.25) * 90.0, cell = floor(sp), cf = fract(sp) - 0.5 - 0.3 * (vec2(h2(cell + 1.0), h2(cell + 2.0)) - 0.5);
    float st = step(0.975, h2(cell)) * smoothstep(0.16, 0.04, length(cf)) * night * smoothstep(0.08, 0.3, dir.y) * (0.55 + 0.45 * sin(uTime * 1.9 + h2(cell) * 40.0));
    sky += vec3(st) * 0.8 * (1.0 - uCloud);
    sky += vec3(0.34, 0.18, 0.08) * night * exp(-e * 7.0) * (0.45 + 0.35 * uCloud);
    // clouds drift across the flattened sky: the noise texture, thresholded by the cover
    vec2 cuv = vec2(dir.x, dir.z) / (dir.y + 0.18) * 0.09 + vec2(uTime * 0.004, 0.0);
    float cn = texture2D(tNoise, cuv).r;
    float cmask = smoothstep(0.58 - 0.34 * uCloud, 0.80 - 0.34 * uCloud, cn) * smoothstep(0.0, 0.2, dir.y);
    vec3 ccol = mix(vec3(0.03, 0.035, 0.06), vec3(0.95, 0.96, 1.0), day);
    ccol = mix(ccol, vec3(1.0, 0.62, 0.40), golden * 0.7); ccol = mix(ccol, vec3(0.12, 0.14, 0.22), blue * 0.6);
    ccol = mix(ccol, vec3(0.42, 0.44, 0.48) * (0.5 + 0.5 * day), uCloud);
    ccol *= 1.0 - 0.35 * smoothstep(0.55, 0.95, cn);                                  // thicker in the middle
    sky = mix(sky, ccol, cmask * 0.92);
    // birds, by day: four of them crossing, flapping
    if (day > 0.3 && dir.y > 0.05 && uRain < 0.3) {
      float az = atan(dir.x, dir.z), el = asin(clamp(dir.y, -1.0, 1.0));
      for (int i = 0; i < 4; i++) {
        float fi = float(i);
        float ph = fract(uTime * 0.011 + fi * 0.26);
        vec2 q = vec2(az - (ph * 1.7 - 0.85), el - (0.16 + 0.08 * sin(fi * 2.1 + uTime * 0.21) + 0.04 * fi));
        float flap = sin(uTime * (9.0 + fi) + fi * 1.7);
        float b = smoothstep(0.0022, 0.0009, abs(q.y - flap * 0.6 * abs(q.x))) * step(abs(q.x), 0.0075);
        sky = mix(sky, vec3(0.02, 0.02, 0.03), b * smoothstep(0.0, 0.1, ph) * smoothstep(1.0, 0.9, ph));
      }
    }

    // --- light on the cards by time of day: dusk warms, blue hour cools, night keeps a city-glow ambient
    vec3 tint = mix(vec3(0.030, 0.034, 0.060), vec3(1.0), day);
    tint = mix(tint, tint * vec3(0.55, 0.42, 0.40), golden * 0.7);
    tint = mix(tint, tint * vec3(0.55, 0.62, 0.90) + vec3(0.02, 0.025, 0.05), blue * 0.6);
    tint *= 1.0 - 0.38 * uCloud - 0.12 * uRain;
    float haze = 0.36 + 0.3 * uCloud + 0.12 * uRain;

    // --- the ground plane: where does the ray meet the street?
    float Dg = dy < -0.0005 ? (uGroundY - g.y) / slope.y : 1e9;
    vec3 ground = vec3(0.0);
    if (Dg < uFar.x) {
      vec2 gp = vec2(g.x + slope.x * Dg, Dg);
      vec3 gc = texture2D(tGround, vec2(gp.x / uGroundTile + 0.5, gp.y / uGroundTile)).rgb * tint;
      // a street lamp's pool at the lot's corner (the lamp is in the near card, every 16 m like it) and the vending machine's glow
      float lx = mod(gp.x - 2.6 + 8.0, 16.0) - 8.0;
      float pool = exp(-dot(vec2(lx, gp.y - uNear.x - 0.6), vec2(lx, gp.y - uNear.x - 0.6)) / 7.0);
      float vm = exp(-dot(vec2(lx + 0.8, gp.y - uNear.x - 0.2), vec2(lx + 0.8, gp.y - uNear.x - 0.2)) / 1.2);
      gc += (vec3(0.9, 0.7, 0.4) * pool * 0.35 + vec3(0.5, 0.6, 0.8) * vm * 0.3) * dark;
      gc = mix(gc, gc * 0.5 + horizonCol * 0.35, uRain * 0.85);                     // wet
      ground = mix(gc, horizonCol, smoothstep(15.0, 110.0, Dg) * (0.5 + 0.5 * haze));
    }

    vec3 col = sky;
    // far: the skyline in the haze
    vec4 f = card(tFar, uFar, g, slope);
    col = mix(col, mix(f.rgb * tint, horizonCol, haze) + lights(tFarL, uFar, g, slope, dark) * (1.0 - 0.5 * haze), f.a);
    if (Dg >= uTrainP.x && Dg < uFar.x) col = ground;
    // the train on the viaduct, between far and mid (alternating direction)
    if (uTrain > 0.5 && Dg > uTrainP.x) {
      vec2 tp = g + slope * uTrainP.x;
      float tx = tp.x * uTrainDir - uTrain;                    // uTrain: the train's tail, in its own direction of travel
      if (tp.y > uTrainP.y && tp.y < uTrainP.y + uTrainP.z && tx > 0.0 && tx < uTrainP.w) {
        float ry = (tp.y - uTrainP.y) / uTrainP.z;
        vec3 body = vec3(0.62, 0.64, 0.68) * tint;
        body = mix(body, vec3(0.85, 0.42, 0.10) * tint, step(0.33, ry) * step(ry, 0.45));                 // a plain colour band
        float win = step(0.52, ry) * step(ry, 0.80) * step(0.22, fract(tx / 1.5)) * step(0.15, fract(tx / 20.0)) * step(fract(tx / 20.0), 0.97);
        body = mix(body, vec3(0.12, 0.14, 0.18) * (0.6 + 0.4 * day) + vec3(1.0, 0.92, 0.7) * dark * 1.3, win);
        body = mix(body, horizonCol, haze * 0.5);
        col = body;
      }
    }
    if (Dg >= uMid.x && Dg < uTrainP.x) col = ground;
    // mid: the apartment blocks
    vec4 m = card(tMid, uMid, g, slope);
    col = mix(col, mix(m.rgb * tint, horizonCol, haze * 0.32) + lights(tMidL, uMid, g, slope, dark), m.a);
    if (Dg >= uNear.x && Dg < uMid.x) col = ground;
    // rain falling, in front of the blocks
    if (uRain > 0.002) {
      vec2 rp = g + slope * (uNear.x + 2.0);
      float r = texture2D(tNoise, vec2(rp.x * 0.33, rp.y * 0.045 + uTime * 0.85)).g;
      col = mix(col, horizonCol * 1.2 + vec3(0.08), smoothstep(0.35, 0.9, r) * uRain * 0.2);
    }
    // near: the house across the lane, the pole and its cables, the tree
    vec4 nr = card(tNear, uNear, g, slope);
    col = mix(col, mix(nr.rgb * tint, horizonCol, haze * 0.08) + lights(tNearL, uNear, g, slope, dark), nr.a);
    if (Dg < uNear.x) col = ground;

    // --- the glass: transmission, a faint sheen that grows at grazing angles, the rain's highlights
    float fres = pow(1.0 - dz, 3.0);
    col = col * vec3(0.93, 0.96, 0.95) + vec3(0.02, 0.022, 0.03) * (0.25 + 0.75 * day) * smoothstep(0.55, 1.0, vUv.y) + fres * 0.06 * (0.3 + 0.7 * day);
    if (uRain > 0.002) {
      float s = texture2D(tNoise, vec2(vUv.x * 2.2, vUv.y * 0.5 + uTime * 0.22)).g;
      col += (smoothstep(0.6, 0.95, s) * 0.10 + dropA * dropA * 0.22) * uRain * (0.15 + 0.85 * day) * (sky * 0.5 + 0.2);
    }
    gl_FragColor = vec4(col, 1.0);
    #include <colorspace_fragment>
  }`;

export function createWindowView(THREE, opts = {}){
  const base = opts.base ?? "room/window/";
  const loader = new THREE.TextureLoader();
  const tex = (name, srgb, aniso = 4) => {
    const t = loader.load(base + name + ".webp");
    t.wrapS = THREE.RepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping;
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = aniso; t.flipY = true;
    return t;
  };
  const tNear = tex("near", true), tNearL = tex("near_l", false), tMid = tex("mid", true), tMidL = tex("mid_l", false);
  const tFar = tex("far", true), tFarL = tex("far_l", false), tGround = tex("ground", true, 8), tNoise = tex("noise", false, 1);
  tGround.wrapT = THREE.RepeatWrapping; tNoise.wrapT = THREE.RepeatWrapping;
  const L = l => new THREE.Vector4(l.d, l.xm, l.y0, l.y1);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uSize: {value: new THREE.Vector2(1.5, 0.8)}, uGain: {value: new THREE.Vector2(GAIN.h, GAIN.v)}, uLift: {value: new THREE.Vector3(GAIN.pitch, GAIN.pitchK, GAIN.pitchMax)}, uTime: {value: 0}, uSun: {value: 0.5},
      uRain: {value: 0}, uCloud: {value: 0}, uLitP: {value: 0}, uSunDir: {value: new THREE.Vector3(0, 0.3, 1)}, uMoonDir: {value: new THREE.Vector3(0, 0.3, 1)},
      uTrain: {value: -1}, uTrainDir: {value: 1}, tNear: {value: tNear}, tNearL: {value: tNearL}, tMid: {value: tMid}, tMidL: {value: tMidL},
      tFar: {value: tFar}, tFarL: {value: tFarL}, tGround: {value: tGround}, tNoise: {value: tNoise},
      uNear: {value: L(LAYERS.near)}, uMid: {value: L(LAYERS.mid)}, uFar: {value: L(LAYERS.far)}, uGroundTile: {value: LAYERS.ground.tile},
      uGroundY: {value: GROUND}, uTrainP: {value: new THREE.Vector4(TRAIN.d, TRAIN.y, TRAIN.h, TRAIN.len)},
    },
    vertexShader: VERT, fragmentShader: FRAG, toneMapped: false,
  });
  const U = material.uniforms;
  const state = {hour: 12, sun: 0.5, weather: {kind: "clear", cloud: 0, rain: 0}, override: opts.weather ?? null, litP: 0, train: null, time: 0};
  const light = {sun: 1, cloud: 0, rain: 0};
  let mesh = null, cloud = 0, rain = 0;

  function build(surf, scene){
    mesh = new THREE.Mesh(new THREE.PlaneGeometry(surf.w, surf.h), material);
    mesh.position.set(...surf.c); mesh.rotation.y = surf.ry; mesh.name = "window_view";
    U.uSize.value.set(surf.w, surf.h);
    if (scene) scene.add(mesh);
    return mesh;
  }
  function target(){
    if (state.override) return state.override === "rain" ? {kind: "rain", cloud: 1, rain: 1} : state.override === "overcast" ? {kind: "overcast", cloud: 1, rain: 0} : {kind: "clear", cloud: 0, rain: 0};
    return weatherAt(tokyoDayKey(), state.hour);
  }
  function update(dt, hour){
    state.time += dt; state.hour = hour;
    const sunEl = sunElevation(hour); state.sun = sunEl;
    U.uTime.value = state.time; U.uSun.value = sunEl;
    // the sun crosses the window from the viewer's left to the right over the day, low in the morning and the evening
    const td = Math.min(1, Math.max(0, (hour - 5.6) / 12.2));
    const az = (-48 + 96 * td) * Math.PI / 180, el = (7 + 34 * Math.max(0, sunEl)) * Math.PI / 180;
    U.uSunDir.value.set(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el));
    const tn = (((hour - 17.8) / 12.2) % 1 + 1) % 1;
    const maz = (-40 + 80 * tn) * Math.PI / 180, mel = (10 + 28 * Math.sin(Math.PI * tn)) * Math.PI / 180;
    U.uMoonDir.value.set(Math.sin(maz) * Math.cos(mel), Math.sin(mel), Math.cos(maz) * Math.cos(mel));
    // weather eases towards its target (a front takes minutes to arrive, a debug switch about two seconds)
    const w = target(); state.weather = w;
    const k = 1 - Math.exp(-dt * (state.override ? 1.5 : 0.05));
    cloud += (w.cloud - cloud) * k; rain += (w.rain - rain) * k;
    U.uCloud.value = cloud; U.uRain.value = rain;
    light.cloud = cloud; light.rain = rain; light.sun = 1 - 0.85 * cloud;
    state.litP = U.uLitP.value = litProbability(hour);
    // the train: every TRAIN.every s one crosses the viaduct, alternating direction
    const cyc = Math.floor(state.time / TRAIN.every), ph = state.time - cyc * TRAIN.every, dir = cyc % 2 ? -1 : 1;
    const x = ph * TRAIN.speed - TRAIN.len - 40;                // its tail, from well off one side to well off the other
    const on = x < 40;
    U.uTrain.value = on ? x : -1; U.uTrainDir.value = dir;
    state.train = on ? {x, dir} : null;
  }
  function setWeather(kind){ state.override = kind || null; }
  return {material, get mesh(){ return mesh; }, build, update, setWeather, light, state: () => ({...state, cloud, rain}), LAYERS, GAIN};
}
