// FX stream: effects and post-processing of the construct. Own orange/neon style: warm words, warm light, deep blue-black.
//
// createFx(renderer, scene, camera, data, quality) ->
//   {rain(msg), innerLine(speech), weather(market), update(dt, env), render(), resize(w, h), dispose()}
//   rain(msg)          an accepted chat message ({text, regions, ...}): its own words fall as orange rain from the sky and
//                      land on the districts in msg.regions (brain region indices; data.districts[i].pos), each word ends
//                      in a landing splash. Words are glyph quads from a canvas atlas (one instanced draw call), never
//                      HTML. Rate-limited (one message per RAIN_GAP s, short queue) and pooled (no per-frame allocation).
//   innerLine(speech)  {text, kind: "rule"|"llm", about, chat} shown in-world for a few seconds: near the horizon in
//                      first person, above the district where the words landed (or home) in the overview; labelled
//                      "inner speech (generated)" / "inner speech (rule)".
//   weather(market)    "pumping": warm pulses roll across the city (ground wave + screen tint waves + bloom breathing)
//                      "dumping": glitches (RGB split, scanline tearing, brief block displacement) in short bursts
//                      < 3 Hz, never a full-screen strobe; "choppy": light jitter; "calm": nothing.
//   update(dt, env)    NREM: global dim + slow (rain / pulses at half speed). REM: the world warps (screen-space warp +
//                      fov breathing) and the day's messages drift through the city as translucent words (déjà vu,
//                      from env.replays [{text, t, seq}]).
//   render()           RenderPass (into a multisampled half-float target: quality.msaa samples, so medium / high keep
//                      antialiasing through the composer) -> OutputPass (ACES + sRGB, so the frame is display-ready and
//                      bounded) -> UnrealBloomPass (medium / high; full at night, gentler by day) -> one combined fx pass
//                      (glitch + warp + tint + dim + vignette). Low quality: no bloom, no msaa, and the composer only runs
//                      while an effect is active (plain renderer.render otherwise, the vignette fades with the effect
//                      level so the switch is invisible) so phones keep 30 fps.
//   Debug / screenshot URL params (harmless: clamped, no state beyond this module): ?fxhold=1 keeps a glitch burst on
//   while the market dumps; ?fxspeed=N (0.1..10) scales the fx clock so rain lands sooner (e2e uses fxspeed=3 and waits
//   on window.__sub01.fx.pending == 0); ?fxpost=0 disables the composer. window.__sub01.fx mirrors the effect state.
//   prefers-reduced-motion (read live via matchMedia "change"): glitch bursts are weak and short (no tearing / block
//                      displacement), REM shows a static warm tint instead of the warp / fov breathing, jitter is off.
// It is a model of brain activity, not a mind.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export const RAIN_GAP = 0.6;                 // s between two rained messages (extra messages queue up, max RAIN_QUEUE)
export const RAIN_QUEUE = 8;
export const MAX_WORDS = 28, MAX_WORD_LEN = 16, MAX_GLYPHS = 150;   // per message
export const BURST_GAP = [0.4, 1.6];         // s between two glitch bursts (>= 0.4 s -> < 3 Hz), each 60..220 ms long
export const ORANGE = 0xff6a00;
// bloom (medium / high) works on the display-ready (tone-mapped, bounded) frame: only the bright cores of roads, words
// and towers glow, and the daytime sky cannot blow the frame out
export const BLOOM = { strength: 0.35, radius: 0.3, threshold: 0.8 };

// ---------------------------------------------------------------------------------------------------------------------
// pure helpers (also used by the node tests)
// ---------------------------------------------------------------------------------------------------------------------
const ATLAS_CHARS = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
  + "àáâäèéêëìíîïòóôöùúûüçñÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜÇÑ€£…’‘“”«»–—°·";
const CHAR_INDEX = new Map([...ATLAS_CHARS].map((c, i) => [c, i]));

/** The words of a message that can be rained: split on whitespace, unknown glyphs dropped, capped in count and length. */
export function splitWords(text, { maxWords = MAX_WORDS, maxLen = MAX_WORD_LEN, maxGlyphs = MAX_GLYPHS } = {}) {
  const out = [];
  let glyphs = 0;
  for (const raw of String(text ?? "").split(/\s+/)) {
    const w = [...raw].filter(c => CHAR_INDEX.has(c) && c !== " ").slice(0, maxLen).join("");
    if (!w) continue;
    if (out.length >= maxWords || glyphs + w.length > maxGlyphs) break;
    out.push(w); glyphs += w.length;
  }
  return out;
}

/**
 * Wrap text into at most maxLines lines at word boundaries. fits(str) -> bool says whether a line fits (canvas
 * measureText in the page, a length check in the tests). A word longer than a line is cut. When the text does not fit
 * in maxLines, the last line ends in an ellipsis at a word boundary (never mid-word, never squeezed).
 */
export function wrapText(text, fits, maxLines = 2) {
  const words = String(text ?? "").trim().split(/\s+/).filter(Boolean);
  const lines = [];
  let cur = "";
  for (let i = 0; i < words.length; i++) {
    let w = words[i];
    while (!fits(w)) w = w.slice(0, -1);                     // an overlong word: cut it
    const cand = cur ? cur + " " + w : w;
    if (fits(cand)) { cur = cand; continue; }
    lines.push(cur); cur = w;
    if (lines.length === maxLines) {                          // no room for the rest: ellipsis on the last line
      let last = lines[maxLines - 1] + "…";
      while (!fits(last) && last.length > 1) { last = last.replace(/…$/, "").replace(/\s*\S*$/, "") + "…"; }
      lines[maxLines - 1] = last;
      return lines;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

const CUR_KEYS = ["pump", "glitch", "jitter", "warp", "dim", "rem"];   // smoothed effect levels (no per-frame Object.keys)

/** True when the renderer's GL context is a software rasterizer (same test as quality.js autoPick, on the live context). */
export function softwareGL(renderer) {
  try {
    const gl = renderer.getContext();
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const r = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    return /swiftshader|llvmpipe|software|basic render/i.test(r);
  } catch { return false; }
}

/** Weather targets per market mood (0..1 each). reduced = prefers-reduced-motion. */
export function marketTargets(market, reduced = false) {
  const m = String(market || "calm").toLowerCase();
  if (m === "pumping") return { pump: 1, glitch: 0, jitter: 0 };
  if (m === "dumping") return { pump: 0, glitch: reduced ? 0.35 : 1, jitter: 0 };
  if (m === "choppy") return { pump: 0, glitch: reduced ? 0 : 0.15, jitter: reduced ? 0 : 1 };
  return { pump: 0, glitch: 0, jitter: 0 };
}

/**
 * Glitch burst scheduler: bursts of 60..220 ms, at least BURST_GAP[0] s apart (< 3 Hz), strength scaled by the level.
 * tick(t, level) -> current burst strength (0 outside a burst). Pure apart from the injected rng.
 */
export function createBurster(rng = Math.random) {
  let next = 0, end = 0, strength = 0, seed = 0;
  return {
    tick(t, level) {
      if (t >= end) strength = 0;
      if (level > 0.02 && t >= next) {
        strength = level * (0.35 + 0.65 * rng());
        seed = rng();
        end = t + 0.06 + 0.16 * rng();
        next = t + BURST_GAP[0] + (BURST_GAP[1] - BURST_GAP[0]) * rng();
      }
      return strength;
    },
    get seed() { return seed; },
  };
}

// ---------------------------------------------------------------------------------------------------------------------
// glyph atlas (canvas -> texture, alpha only; the colour comes from the shader)
// ---------------------------------------------------------------------------------------------------------------------
const CELL_W = 32, CELL_H = 40, COLS = 16;
const ADVANCE = 0.55;   // glyph advance in cells: a bold 26px monospace glyph fills ~half of the 32px cell (+ its outline)
function makeAtlas() {
  const rows = Math.ceil(ATLAS_CHARS.length / COLS);
  const cv = document.createElement("canvas");
  cv.width = COLS * CELL_W; cv.height = rows * CELL_H;
  const x = cv.getContext("2d");
  x.clearRect(0, 0, cv.width, cv.height);
  x.font = `bold 26px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
  x.textAlign = "center"; x.textBaseline = "middle";
  x.lineJoin = "round"; x.lineWidth = 5; x.strokeStyle = "#000"; x.fillStyle = "#fff";
  // black stroke under a white fill: alpha = coverage of ink + outline, red = ink only (the shader colours the ink and
  // keeps the outline dark, so the words stay legible on the bright daytime city as well as at night)
  [...ATLAS_CHARS].forEach((c, i) => {
    const cx = (i % COLS) * CELL_W + CELL_W / 2, cy = Math.floor(i / COLS) * CELL_H + CELL_H / 2 + 1;
    x.strokeText(c, cx, cy); x.fillText(c, cx, cy);
  });
  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter; tex.generateMipmaps = false;
  return { tex, cols: COLS, rows, w: cv.width, h: cv.height };
}

// ---------------------------------------------------------------------------------------------------------------------
// shaders
// ---------------------------------------------------------------------------------------------------------------------
const GLYPH_VERT = /* glsl */`
  uniform float time; uniform vec2 resolution;
  attribute vec3 aStart; attribute vec3 aEnd; attribute vec2 aTime; attribute vec4 aGlyph; attribute vec3 aWord; attribute float aMode;
  varying vec2 vUv; varying float vAlpha; varying float vMode;
  void main() {
    float u = (time - aTime.x) / aTime.y;
    if (aTime.y <= 0.0 || u < 0.0 || u > 1.6) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vAlpha = 0.0; vUv = vec2(0.0); vMode = 0.0; return; }
    float uc = clamp(u, 0.0, 1.0);
    vec3 p; float a;
    if (aMode < 0.5) {                                   // rain: accelerating fall, sway, then fade after landing
      p = mix(aStart, aEnd, pow(uc, 1.7));
      p.x += sin(time * 2.0 + aWord.z) * 1.5 * (1.0 - uc);
      float after = max(0.0, u - 1.0) / 0.6;
      a = 1.0 - after;
    } else {                                             // déjà vu: slow drift, fade in / out
      p = mix(aStart, aEnd, uc);
      p.y += sin(time * 0.6 + aWord.z) * 2.5;
      a = u > 1.0 ? 0.0 : 0.65 * sin(3.14159 * uc);
    }
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vec4 clip = projectionMatrix * mv;
    float px = aWord.y * clamp(sqrt(200.0 / max(-mv.z, 1.0)), 0.85, 1.5);   // ~constant pixel size, a little bigger up close
    // quad = one 32x40 atlas cell (aspect 0.8); the glyph ink fills ~half of it, so aWord.x (the advance) is ADVANCE cells
    vec2 off = (position.xy * vec2(0.8, 1.0) + vec2(aWord.x, 0.0)) * px / resolution * 2.0;
    clip.xy += off * clip.w;
    gl_Position = clip;
    vUv = mix(aGlyph.xy, aGlyph.zw, uv); vAlpha = a; vMode = aMode;
  }`;
const GLYPH_FRAG = /* glsl */`
  uniform sampler2D atlas; uniform vec3 color; uniform vec3 ghost; uniform float level;
  varying vec2 vUv; varying float vAlpha; varying float vMode;
  void main() {
    vec4 t = texture2D(atlas, vUv);
    float a = t.a * vAlpha * level;
    if (a < 0.01) discard;
    vec3 ink = mix(color, ghost, vMode);
    vec3 c = mix(vec3(0.02, 0.01, 0.0), ink, t.r);            // dark outline around the coloured ink
    gl_FragColor = vec4(c, a * mix(1.0, 0.75, vMode));
  }`;

const SPLASH_VERT = /* glsl */`
  uniform float time;
  attribute vec3 aPos; attribute vec2 aT;
  varying vec2 vC; varying float vA;
  void main() {
    float u = (time - aT.x) / 1.3;
    if (aT.y <= 0.0 || u < 0.0 || u > 1.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vC = vec2(0.0); vA = 0.0; return; }
    float r = aT.y * mix(0.15, 1.0, 1.0 - (1.0 - u) * (1.0 - u));
    vec3 p = aPos + vec3(position.x * r, 0.35, position.z * r);
    vC = position.xz * 2.0; vA = 1.0 - u;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const SPLASH_FRAG = /* glsl */`
  uniform vec3 color; uniform float level;
  varying vec2 vC; varying float vA;
  void main() {
    float d = length(vC);
    float ring = smoothstep(0.7, 0.88, d) * (1.0 - smoothstep(0.92, 1.0, d));
    float glow = (1.0 - d) * 0.35;
    float a = (ring + max(0.0, glow)) * vA * level;
    if (a < 0.01) discard;
    gl_FragColor = vec4(color * a, a);
  }`;

// warm pulses rolling over the city (pumping): one big additive plane on the ground
const WAVE_VERT = /* glsl */`
  varying vec2 vP;
  void main() { vP = position.xz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const WAVE_FRAG = /* glsl */`
  uniform float time; uniform float amount; uniform vec2 center; uniform float radius; uniform vec3 color;
  varying vec2 vP;
  void main() {
    float d = length(vP - center);
    float ph = fract(d / (radius * 0.9) - time * 0.16);
    float wave = pow(1.0 - abs(ph - 0.15) / 0.15, 3.0) * step(abs(ph - 0.15), 0.15);
    float fade = 1.0 - smoothstep(radius * 0.9, radius * 1.3, d);
    float a = wave * fade * amount * 0.5;
    if (a < 0.003) discard;
    gl_FragColor = vec4(color * a, a);
  }`;

// the combined screen pass: glitch (dump) + jitter (choppy) + warp (REM) + warm tint (pump) + dim (NREM) + vignette,
// in display space (the OutputPass right after the scene pass already applied tone mapping and the output colour space)
const FX_SHADER = {
  uniforms: {
    tDiffuse: { value: null }, time: { value: 0 }, resolution: { value: new THREE.Vector2(1, 1) },
    glitch: { value: 0 }, seed: { value: 0 }, split: { value: 0 }, tear: { value: 1 }, blocks: { value: 1 },
    jitter: { value: 0 }, warp: { value: 0 }, rem: { value: 0 }, dim: { value: 0 }, pump: { value: 0 }, vignette: { value: 0.35 },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform float time; uniform vec2 resolution;
    uniform float glitch, seed, split, tear, blocks, jitter, warp, rem, dim, pump, vignette;
    varying vec2 vUv;
    float hash(float n) { return fract(sin(n * 127.1 + 311.7) * 43758.5453); }
    void main() {
      vec2 uv = vUv;
      if (warp > 0.001) {                                                       // REM: the world breathes and bends
        vec2 c = uv - 0.5; float r = length(c);
        float breathe = 1.0 - warp * 0.06 * (0.5 + 0.5 * sin(time * 0.8));
        uv = 0.5 + c * (breathe + warp * 0.16 * r * r * sin(time * 0.5 + r * 7.0));
        uv += warp * 0.014 * vec2(sin(uv.y * 7.0 + time * 0.9), cos(uv.x * 6.0 - time * 0.7));
      }
      if (jitter > 0.001) {                                                     // choppy: a smooth ~7 Hz wander, not a vibration
        float jt = time * 7.0, jf = floor(jt), jr = smoothstep(0.0, 1.0, fract(jt));
        vec2 n = mix(vec2(hash(jf), hash(jf + 7.0)), vec2(hash(jf + 1.0), hash(jf + 8.0)), jr) - 0.5;
        uv += jitter * 0.0015 * n;
      }
      vec2 guv = uv;
      float g = glitch;
      if (g > 0.001) {                                                          // dump: tearing + block displacement
        float row = floor(uv.y * 28.0);
        float tr = hash(row + seed * 97.0);
        float amt = step(1.0 - 0.32 * g * tear, tr) * (hash(row * 3.1 + seed * 13.0) - 0.5) * 0.10 * g;
        guv.x += amt;
        vec2 bl = floor(uv * vec2(9.0, 6.0));
        float br = hash(bl.x * 12.9 + bl.y * 78.2 + seed * 5.0);
        if (br > 1.0 - 0.16 * g * blocks) guv += (vec2(hash(br * 3.0), hash(br * 9.0)) - 0.5) * 0.06 * g;
        guv = clamp(guv, 0.0, 1.0);
      }
      float sp = split * g / resolution.x;
      vec3 col;
      col.r = texture2D(tDiffuse, guv + vec2(sp, 0.0)).r;
      col.g = texture2D(tDiffuse, guv).g;
      col.b = texture2D(tDiffuse, guv - vec2(sp, 0.0)).b;
      if (g > 0.001) {                                                          // faint scanlines while it glitches
        col *= 1.0 - 0.12 * g * (0.5 + 0.5 * sin(gl_FragCoord.y * 1.6 + time * 30.0));
        col += vec3(0.45, 0.10, 0.02) * g * 0.10;
      }
      if (pump > 0.001) {                                                       // pump: warm waves across the screen
        float w = pow(0.5 + 0.5 * sin(uv.x * 2.4 - uv.y * 1.6 - time * 1.1), 6.0);
        col += vec3(1.0, 0.42, 0.10) * w * pump * 0.14;
        col *= 1.0 + pump * 0.04 * sin(time * 1.1);
      }
      if (dim > 0.001) {                                                        // NREM: darker, cooler, less saturated
        float l = dot(col, vec3(0.30, 0.59, 0.11));
        col = mix(col, vec3(l) * vec3(0.55, 0.62, 0.85), dim * 0.45) * (1.0 - 0.45 * dim);
      }
      col += rem * 0.025 * vec3(1.0, 0.5, 0.2) * (0.6 + 0.4 * sin(time * 0.3 + uv.y * 3.0));   // REM: a warm dream tint (also the
                                                                                            // whole REM look under reduced motion)
      float vg = smoothstep(1.25, 0.35, length(vUv - 0.5) * 1.45);
      col *= mix(1.0, vg, vignette);
      gl_FragColor = vec4(col, 1.0);
    }`,
};

// ---------------------------------------------------------------------------------------------------------------------
export function createFx(renderer, scene, camera, data, quality) {
  const q = quality && typeof quality === "object" ? quality : { name: quality || "medium", post: true, bloom: true };
  const low = q.name === "low" || !q.post;
  // prefers-reduced-motion, kept live: a setting changed mid-session is picked up on the next frame
  const motionMq = (() => { try { return window.matchMedia?.("(prefers-reduced-motion: reduce)") || null; } catch { return null; } })();
  let reduced = !!motionMq?.matches;
  let market = "calm";
  const onMotionChange = e => { reduced = !!e.matches; applyReduced(); };
  try { motionMq?.addEventListener?.("change", onMotionChange); } catch { /* old browsers: read once */ }
  // ?fxhold=1 (screenshots only): keeps a glitch burst on instead of the random short bursts
  const urlq = (() => { try { return new URLSearchParams(location.search); } catch { return new URLSearchParams(); } })();
  const hold = urlq.get("fxhold") === "1";
  const noPost = urlq.get("fxpost") === "0";           // ?fxpost=0: never use the composer (debug / comparison)
  const clockScale = Math.min(10, Math.max(0.1, +urlq.get("fxspeed") || 1));   // ?fxspeed=N: screenshots only
  const rng = Math.random;
  const R = data.radius || 400;
  const root = new THREE.Group(); root.name = "fx"; scene.add(root);
  const pr = renderer.getPixelRatio();
  const size = renderer.getSize(new THREE.Vector2());
  const resolution = new THREE.Vector2(Math.max(1, size.x * pr), Math.max(1, size.y * pr));

  // ---------------- rain / déjà vu glyphs (one instanced draw call) ----------------
  const atlas = makeAtlas();
  const POOL = low ? 700 : 1400;
  const quad = new THREE.PlaneGeometry(1, 1);
  const gg = new THREE.InstancedBufferGeometry();
  gg.index = quad.index; gg.setAttribute("position", quad.attributes.position); gg.setAttribute("uv", quad.attributes.uv);
  const aStart = new THREE.InstancedBufferAttribute(new Float32Array(POOL * 3), 3);
  const aEnd = new THREE.InstancedBufferAttribute(new Float32Array(POOL * 3), 3);
  const aTime = new THREE.InstancedBufferAttribute(new Float32Array(POOL * 2), 2);
  const aGlyph = new THREE.InstancedBufferAttribute(new Float32Array(POOL * 4), 4);
  const aWord = new THREE.InstancedBufferAttribute(new Float32Array(POOL * 3), 3);
  const aMode = new THREE.InstancedBufferAttribute(new Float32Array(POOL), 1);
  for (const a of [aStart, aEnd, aTime, aGlyph, aWord, aMode]) { a.setUsage(THREE.DynamicDrawUsage); }
  gg.setAttribute("aStart", aStart); gg.setAttribute("aEnd", aEnd); gg.setAttribute("aTime", aTime);
  gg.setAttribute("aGlyph", aGlyph); gg.setAttribute("aWord", aWord); gg.setAttribute("aMode", aMode);
  gg.instanceCount = POOL;
  const glyphMat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, resolution: { value: resolution }, atlas: { value: atlas.tex },
      color: { value: new THREE.Color(0xff8a2a).multiplyScalar(1.5) }, ghost: { value: new THREE.Color(0xffe2c0) },
      level: { value: 1 } },
    vertexShader: GLYPH_VERT, fragmentShader: GLYPH_FRAG,
    transparent: true, depthWrite: false, depthTest: false, fog: false,   // words are light: never hidden by a tower
  });
  const glyphs = new THREE.Mesh(gg, glyphMat); glyphs.frustumCulled = false; glyphs.renderOrder = 20; root.add(glyphs);
  const expires = new Float32Array(POOL);             // fx time after which the slot is free
  const free = []; for (let i = POOL - 1; i >= 0; i--) free.push(i);
  let glyphsDirty = false, sweepAt = 0;

  function glyphRect(ch, out) {
    const k = CHAR_INDEX.get(ch) ?? 0, cx = k % atlas.cols, cy = Math.floor(k / atlas.cols);
    out[0] = (cx * CELL_W) / atlas.w; out[1] = 1 - ((cy + 1) * CELL_H) / atlas.h;
    out[2] = ((cx + 1) * CELL_W) / atlas.w; out[3] = 1 - (cy * CELL_H) / atlas.h;
    return out;
  }
  const rect = [0, 0, 0, 0];
  /** Lay one word (string) down as glyph instances. mode 0 rain (start -> end, dur), 1 drift. Returns false if the pool is full. */
  function putWord(word, start, end, t0, dur, mode, sizePx) {
    if (free.length < word.length) return false;
    const phase = rng() * 6.283, half = (word.length - 1) * ADVANCE * 0.5;
    for (let k = 0; k < word.length; k++) {
      const i = free.pop();
      aStart.setXYZ(i, start.x, start.y, start.z); aEnd.setXYZ(i, end.x, end.y, end.z);
      aTime.setXY(i, t0, dur);
      glyphRect(word[k], rect); aGlyph.setXYZW(i, rect[0], rect[1], rect[2], rect[3]);
      aWord.setXYZ(i, k * ADVANCE - half, sizePx, phase); aMode.setX(i, mode);
      expires[i] = t0 + dur * 1.6 + 0.1;
    }
    glyphsDirty = true;
    return true;
  }
  function sweep(t) {                                   // free the slots whose words are gone (every 0.25 s)
    if (t < sweepAt) return;
    sweepAt = t + 0.25;
    for (let i = 0; i < POOL; i++) if (aTime.getY(i) > 0 && t > expires[i]) { aTime.setXY(i, 0, 0); free.push(i); glyphsDirty = true; }
  }
  function flushGlyphs() {
    if (!glyphsDirty) return;
    for (const a of [aStart, aEnd, aTime, aGlyph, aWord, aMode]) a.needsUpdate = true;
    glyphsDirty = false;
  }

  // ---------------- landing splashes ----------------
  const SPLASHES = 96;
  const sg = new THREE.InstancedBufferGeometry();
  sg.setAttribute("position", new THREE.Float32BufferAttribute([-0.5, 0, -0.5, 0.5, 0, -0.5, 0.5, 0, 0.5, -0.5, 0, 0.5], 3));
  sg.setIndex([0, 2, 1, 0, 3, 2]);
  const aPos = new THREE.InstancedBufferAttribute(new Float32Array(SPLASHES * 3), 3).setUsage(THREE.DynamicDrawUsage);
  const aT = new THREE.InstancedBufferAttribute(new Float32Array(SPLASHES * 2), 2).setUsage(THREE.DynamicDrawUsage);
  sg.setAttribute("aPos", aPos); sg.setAttribute("aT", aT); sg.instanceCount = SPLASHES;
  const splashMat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, color: { value: new THREE.Color(0xffa040) }, level: { value: 1 } },
    vertexShader: SPLASH_VERT, fragmentShader: SPLASH_FRAG,
    transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, fog: false,
  });
  const splashes = new THREE.Mesh(sg, splashMat); splashes.frustumCulled = false; splashes.renderOrder = 19; root.add(splashes);
  let splashHead = 0;
  const pendingSplash = [];                             // [{t, x, y, z, r}] splashes to fire when their word lands
  function splashAt(x, y, z, r) {
    const i = splashHead; splashHead = (splashHead + 1) % SPLASHES;
    aPos.setXYZ(i, x, y, z); aT.setXY(i, fxTime, r); aPos.needsUpdate = true; aT.needsUpdate = true;
  }

  // ---------------- warm pulses over the city (pumping) ----------------
  const home = data.districtOf?.("home");
  const homePos = home != null ? data.districts[home].pos : new THREE.Vector3();
  const waveMat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, amount: { value: 0 }, center: { value: new THREE.Vector2(homePos.x, homePos.z) }, radius: { value: R },
      color: { value: new THREE.Color(0xff7a20) } },
    vertexShader: WAVE_VERT, fragmentShader: WAVE_FRAG,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
  });
  const wave = new THREE.Mesh(new THREE.PlaneGeometry(R * 2.8, R * 2.8).rotateX(-Math.PI / 2), waveMat);
  wave.position.y = 0.6; wave.visible = false; wave.renderOrder = 5; root.add(wave);

  // ---------------- inner line (one canvas, one sprite, reused) ----------------
  const lineCv = document.createElement("canvas"); lineCv.width = 1024; lineCv.height = 192;
  const lineTex = new THREE.CanvasTexture(lineCv); lineTex.colorSpace = THREE.SRGBColorSpace;
  const lineMat = new THREE.SpriteMaterial({ map: lineTex, transparent: true, opacity: 0, depthWrite: false, depthTest: false,
    sizeAttenuation: false, fog: false });      // tone-mapped like the rest so it looks the same with and without the composer
  const line = new THREE.Sprite(lineMat); line.renderOrder = 30; line.visible = false; root.add(line);
  line.scale.set(0.135 * lineCv.width / lineCv.height, 0.135, 1);
  let lineUntil = -1, lineStart = 0, lineAnchor = null;
  const MONO = `ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
  function roundRect(x, l, t, w, h, r) {
    x.beginPath(); x.moveTo(l + r, t); x.arcTo(l + w, t, l + w, t + h, r); x.arcTo(l + w, t + h, l, t + h, r);
    x.arcTo(l, t + h, l, t, r); x.arcTo(l, t, l + w, t, r); x.closePath();
  }
  /** The inner line: up to two lines wrapped at word boundaries (ellipsis if longer), on a dark translucent backing so it
   *  stays legible on the bright daytime horizon and is bloom-safe; the provenance label is big enough to read on a phone. */
  function drawLine(text, label) {
    const x = lineCv.getContext("2d");
    const W = lineCv.width, H = lineCv.height, pad = 36;
    x.clearRect(0, 0, W, H);
    x.textAlign = "center"; x.textBaseline = "middle";
    let fs = 40; x.font = `italic ${fs}px ${MONO}`;
    let lines = wrapText(text, s => x.measureText(s).width <= W - 2 * pad, 1);
    if (lines.length !== 1 || lines[0] !== text.trim().split(/\s+/).join(" ")) {   // not on one line: two smaller lines
      fs = 32; x.font = `italic ${fs}px ${MONO}`;
      lines = wrapText(text, s => x.measureText(s).width <= W - 2 * pad, 2);
    }
    const lh = fs + 8, textH = lines.length * lh, labelH = 34;
    const top = Math.max(6, (H - textH - labelH - 10) / 2), boxW = Math.min(W - 8, Math.max(...lines.map(s => x.measureText(s).width), 0) + 2 * pad);
    x.font = `30px ${MONO}`;
    const boxW2 = Math.min(W - 8, Math.max(boxW, x.measureText(label).width + 2 * pad));
    x.fillStyle = "rgba(6, 3, 10, 0.62)"; roundRect(x, (W - boxW2) / 2, top - 6, boxW2, textH + labelH + 18, 18); x.fill();
    x.strokeStyle = "rgba(255,106,0,0.35)"; x.lineWidth = 2; x.stroke();
    x.font = `italic ${fs}px ${MONO}`;
    x.shadowColor = "rgba(255,106,0,0.9)"; x.shadowBlur = 16;
    x.fillStyle = "#ffe6cf";
    lines.forEach((s, i) => x.fillText(s, W / 2, top + lh * (i + 0.5)));
    x.shadowBlur = 0; x.shadowColor = "transparent";
    x.font = `30px ${MONO}`;
    x.fillStyle = "rgba(255,180,120,0.95)"; x.fillText(label, W / 2, top + textH + 6 + labelH / 2);
    lineTex.needsUpdate = true;
  }

  // ---------------- state ----------------
  let fxTime = 0, wall = 0, speed = 1;
  const target = { pump: 0, glitch: 0, jitter: 0, warp: 0, dim: 0, rem: 0 };
  const cur = { pump: 0, glitch: 0, jitter: 0, warp: 0, dim: 0, rem: 0 };
  let active = false;                                   // any smoothed effect above threshold (composer needed on low)
  const burster = createBurster(rng);
  const queue = []; let nextRain = 0;
  let lastReplaySeq = -1, baseFov = null, stage = "AWAKE", view = "first";
  const fwd = new THREE.Vector3(), rightV = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();

  // ---------------- post-processing ----------------
  let composer = null, bloom = null, fxPass = null;
  function ensureComposer() {
    if (composer || noPost) return composer;
    // RenderPass (linear, half-float target) -> OutputPass (the renderer's ACES tone mapping + sRGB output, exactly as
    // a direct render would apply them, so the construct looks the same with and without the composer and low quality
    // can toggle it per frame) -> UnrealBloomPass (medium / high) -> fx pass. Bloom and the fx pass see bounded display
    // values: a bright daytime sky cannot blow the frame out through the bloom mip chain.
    // The scene pass renders into an explicit multisampled target (quality.msaa samples on medium / high, 0 on low), so the
    // renderer's antialiasing is not lost behind the composer: the one-pixel fibre roads and district edges would
    // otherwise stair-step and shimmer while the camera walks. EffectComposer clones it for its second target and
    // setSize resizes both; the composer.setSize below (CSS size) also fixes its width/height bookkeeping, which the
    // constructor reads from the target in device pixels.
    // (A software GL renderer - SwiftShader / llvmpipe in headless captures - gets 0 samples: 4x MSAA there costs ~5x per
    // frame for no visible gain, and quality.js auto-picks low on such devices anyway.)
    const samples = low || q.antialias === false || softwareGL(renderer) ? 0 : (q.msaa | 0);
    const rt = new THREE.WebGLRenderTarget(Math.max(1, Math.round(size.x * pr)), Math.max(1, Math.round(size.y * pr)),
      { type: THREE.HalfFloatType, samples });
    composer = new EffectComposer(renderer, rt);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new OutputPass());
    if (!low && q.bloom !== false) {
      bloom = new UnrealBloomPass(resolution.clone(), BLOOM.strength, BLOOM.radius, BLOOM.threshold);
      composer.addPass(bloom);
    }
    fxPass = new ShaderPass(FX_SHADER);
    fxPass.uniforms.resolution.value = resolution;
    fxPass.uniforms.vignette.value = low ? 0 : 0.35;     // low: faded in with the effect level (see update)
    composer.addPass(fxPass);
    applyReduced();
    composer.setSize(size.x, size.y);
    return composer;
  }
  function applyReduced() {
    if (fxPass) { fxPass.uniforms.tear.value = reduced ? 0 : 1; fxPass.uniforms.blocks.value = reduced ? 0 : 1; }
    Object.assign(target, marketTargets(market, reduced));
  }
  if (!low) ensureComposer();


  const validRegion = i => Number.isInteger(i) && i >= 0 && i < data.districts.length;
  function regionsOf(msg) {
    const r = (Array.isArray(msg?.regions) ? msg.regions : []).filter(validRegion).slice(0, 8);
    if (r.length) return r;
    const lang = data.groupRegions?.language;
    if (lang && lang.length) return lang.slice(0, 4);
    return home != null ? [home] : [0];
  }

  /** Drop the words of one message on its districts (called from update, rate-limited). */
  function dropMessage(msg) {
    const words = splitWords(msg.text);
    if (!words.length) return;
    const regions = regionsOf(msg), n = regions.length;
    const sizePx = (low ? 20 : 23) * pr;
    for (let k = 0; k < words.length; k++) {
      const d = data.districts[regions[k % n]];
      const ang = rng() * 6.283, rad = 4 + rng() * 11;
      tmp.set(d.pos.x + Math.cos(ang) * rad, d.pos.y + 1.5, d.pos.z + Math.sin(ang) * rad);                     // landing point
      tmp2.set(tmp.x + (rng() - 0.5) * 30, tmp.y + 260 + rng() * 180, tmp.z + (rng() - 0.5) * 30);              // from the sky
      const t0 = fxTime + k * 0.11, dur = 2.4 + rng() * 0.9;
      if (!putWord(words[k], tmp2, tmp, t0, dur, 0, sizePx)) break;
      if (pendingSplash.length < 200) pendingSplash.push({ t: t0 + dur, x: tmp.x, y: tmp.y - 1.2, z: tmp.z, r: 10 + words[k].length * 1.2 });
    }
  }
  function rain(msg) {
    if (!msg || typeof msg.text !== "string" || !msg.text.trim()) return;
    if (queue.length >= RAIN_QUEUE) queue.shift();
    queue.push(msg);
  }

  function innerLine(speech) {
    if (!speech || typeof speech.text !== "string" || !speech.text.trim()) return;
    const text = speech.text.trim().slice(0, 220);       // wrapText cuts the rest at a word boundary with an ellipsis
    const label = speech.kind === "llm" ? "inner speech (generated)" : "inner speech (rule)";
    drawLine(text, label);
    lineStart = wall; lineUntil = wall + Math.min(9, 3.5 + text.length * 0.05);
    const chatRegions = speech.chat ? regionsOf(speech.chat) : null;
    lineAnchor = chatRegions ? data.districts[chatRegions[0]].pos : homePos;
    line.visible = true;
  }

  function weather(m) { market = m; Object.assign(target, marketTargets(market, reduced)); }

  // ---------------- per frame ----------------
  function update(dt, env) {
    dt = Math.min(0.1, Math.max(0, +dt || 0)) * clockScale;
    wall += dt;
    stage = env?.stage || "AWAKE"; view = env?.view || view;
    speed = stage === "NREM" ? 0.45 : stage === "REM" ? 0.8 : 1;
    fxTime += dt * speed;

    // sleep targets
    target.dim = stage === "NREM" ? 1 : stage === "REM" ? 0.25 : 0;
    target.rem = stage === "REM" ? 1 : 0;                               // warm dream tint (the whole REM look when reduced)
    target.warp = stage === "REM" && !reduced ? 1 : 0;                  // reduced motion: no screen swim at all
    const k = 1 - Math.exp(-dt * 1.5);
    for (let i = 0; i < CUR_KEYS.length; i++) { const key = CUR_KEYS[i]; cur[key] += (target[key] - cur[key]) * k; }

    // rain queue (rate-limited) and landings (landing times are not monotonic: scan, swap-remove, no allocation)
    if (queue.length && wall >= nextRain) { nextRain = wall + RAIN_GAP; dropMessage(queue.shift()); }
    for (let i = pendingSplash.length - 1; i >= 0; i--) {
      const s = pendingSplash[i];
      if (s.t > fxTime) continue;
      splashAt(s.x, s.y, s.z, s.r);
      pendingSplash[i] = pendingSplash[pendingSplash.length - 1]; pendingSplash.pop();
    }
    sweep(fxTime);

    // déjà vu: replayed messages drift through the city during REM
    const replays = Array.isArray(env?.replays) ? env.replays : [];
    if (replays.length) {
      if (lastReplaySeq < 0) lastReplaySeq = Math.max(-1, (replays[replays.length - 1].seq ?? replays.length) - 2);
      for (const r of replays) {
        const seq = r.seq ?? 0;
        if (seq <= lastReplaySeq) continue;
        lastReplaySeq = seq;
        if (stage === "REM" && r.text) driftMessage(r.text);
      }
    }

    // glitch bursts (dump / choppy), never more than one burst per BURST_GAP[0] s
    const burst = hold ? cur.glitch * 0.8 : burster.tick(wall, cur.glitch);
    const glitchNow = burst + cur.glitch * 0.06;
    // "active" follows the smoothed levels (not the bursts), so on low the composer stays on through a whole dump and
    // fades out once, instead of toggling with every burst
    const level = Math.max(cur.glitch, cur.warp, cur.dim, cur.pump, cur.jitter, cur.rem);
    active = level > 0.01;
    if (active && !composer) ensureComposer();
    if (fxPass) {
      const u = fxPass.uniforms;
      u.time.value = wall; u.glitch.value = glitchNow; u.seed.value = burster.seed;
      u.split.value = (reduced ? 2 : 4.5) * pr; u.jitter.value = cur.jitter; u.warp.value = cur.warp; u.rem.value = cur.rem;
      u.dim.value = cur.dim; u.pump.value = cur.pump;
      if (low) u.vignette.value = 0.25 * Math.min(1, Math.max(0, (level - 0.01) / 0.12));   // fades with the effect: no pop
    }
    if (bloom) {
      const dayK = Math.max(0, Math.min(1, +env?.dayK || 0));
      bloom.strength = BLOOM.strength * (1 - 0.6 * dayK) * (1 + cur.pump * 0.6 * (0.5 + 0.5 * Math.sin(wall * 1.1)) - cur.dim * 0.5);
    }

    // pump waves on the ground
    wave.visible = cur.pump > 0.01;
    waveMat.uniforms.time.value = fxTime; waveMat.uniforms.amount.value = cur.pump;

    // REM fov breathing (restored afterwards)
    if (cur.warp > 0.01 && !reduced) {
      if (baseFov === null) baseFov = camera.fov;
      camera.fov = baseFov + cur.warp * 3.5 * Math.sin(wall * 0.7); camera.updateProjectionMatrix();
    } else if (baseFov !== null) { camera.fov = baseFov; camera.updateProjectionMatrix(); baseFov = null; }

    // materials
    const lvl = stage === "NREM" ? 0.5 : 1;
    glyphMat.uniforms.time.value = fxTime; glyphMat.uniforms.level.value = lvl;
    splashMat.uniforms.time.value = fxTime; splashMat.uniforms.level.value = lvl;
    flushGlyphs();

    // inner line placement + fade
    if (line.visible) {
      const a = Math.min(1, (wall - lineStart) / 0.4) * Math.min(1, Math.max(0, (lineUntil - wall) / 0.5));
      lineMat.opacity = a;
      if (wall > lineUntil) line.visible = false;
      else if (view === "orbit" && lineAnchor) line.position.set(lineAnchor.x, lineAnchor.y + 105, lineAnchor.z);
      else { camera.getWorldDirection(fwd); line.position.copy(camera.position).addScaledVector(fwd, 150).y += 20; }   // above the horizon band
    }
  }

  function driftMessage(text) {
    const words = splitWords(text, { maxWords: 12, maxLen: MAX_WORD_LEN, maxGlyphs: 80 });
    if (!words.length) return;
    camera.getWorldDirection(fwd); rightV.crossVectors(fwd, camera.up).normalize();
    const sizePx = (low ? 20 : 23) * pr;
    for (let k = 0; k < words.length; k++) {
      if (view === "orbit") {
        const ang = rng() * 6.283, rad = rng() * R * 0.85;
        tmp.set(Math.cos(ang) * rad, 40 + rng() * 90, Math.sin(ang) * rad);
      } else {
        tmp.copy(camera.position).addScaledVector(fwd, 40 + rng() * 130).addScaledVector(rightV, (rng() - 0.5) * 140);
        tmp.y = camera.position.y + 3 + rng() * 40;
      }
      tmp2.set(tmp.x + (rng() - 0.5) * 40, tmp.y + 6 + rng() * 10, tmp.z + (rng() - 0.5) * 40);
      if (!putWord(words[k], tmp, tmp2, fxTime + k * 0.5, 10 + rng() * 6, 1, sizePx)) break;
    }
  }

  function render() {
    if (composer && (!low || active)) composer.render();
    else renderer.render(scene, camera);
  }

  function resize(w, h) {
    if (!(w > 0 && h > 0)) return;
    size.set(w, h);
    const p = renderer.getPixelRatio();
    resolution.set(Math.max(1, w * p), Math.max(1, h * p));
    composer?.setSize(w, h);
  }

  function dispose() {
    scene.remove(root);
    try { motionMq?.removeEventListener?.("change", onMotionChange); } catch { /* ignore */ }
    if (baseFov !== null) { camera.fov = baseFov; camera.updateProjectionMatrix(); baseFov = null; }
    gg.dispose(); glyphMat.dispose(); sg.dispose(); splashMat.dispose(); wave.geometry.dispose(); waveMat.dispose();
    lineTex.dispose(); lineMat.dispose(); atlas.tex.dispose();
    if (composer) { for (const p of composer.passes) p.dispose?.(); composer.dispose(); composer = null; bloom = null; fxPass = null; }
  }

  const api = { rain, innerLine, weather, update, render, resize, dispose,
    get state() { return { ...cur, burst: burster.seed, queued: queue.length, free: free.length, pending: pendingSplash.length, time: fxTime,
      composer: !!composer, active, reduced, hold, msaa: composer ? (composer.renderTarget1.samples | 0) : 0 }; } };
  try { if (window.__sub01) Object.defineProperty(window.__sub01, "fx", { configurable: true, enumerable: true, get: () => api.state }); } catch { /* debug only */ }
  return api;
}
