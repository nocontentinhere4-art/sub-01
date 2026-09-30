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
//   render()           RenderPass -> UnrealBloomPass (medium / high) -> one combined fx pass (glitch + warp + tint +
//                      dim + vignette + ACES / sRGB output). Low quality: no bloom, and the composer only runs while an
//                      effect is active (plain renderer.render otherwise) so phones keep 30 fps.
//   ?fxhold=1 (screenshots only) holds a glitch burst on; ?fxpost=0 disables the composer (debug); window.__sub01.fx
//   mirrors the effect state.
//   prefers-reduced-motion: glitch bursts are weak and short (no tearing / block displacement), warp and fov breathing
//                      are reduced, jitter is off.
// It is a model of brain activity, not a mind.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

export const RAIN_GAP = 0.6;                 // s between two rained messages (extra messages queue up, max RAIN_QUEUE)
export const RAIN_QUEUE = 8;
export const MAX_WORDS = 28, MAX_WORD_LEN = 16, MAX_GLYPHS = 150;   // per message
export const BURST_GAP = [0.4, 1.6];         // s between two glitch bursts (>= 0.4 s -> < 3 Hz), each 60..220 ms long
export const ORANGE = 0xff6a00;
// bloom (medium / high) works on the display-ready scene: only the bright cores of roads, words and towers glow
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
function makeAtlas() {
  const rows = Math.ceil(ATLAS_CHARS.length / COLS);
  const cv = document.createElement("canvas");
  cv.width = COLS * CELL_W; cv.height = rows * CELL_H;
  const x = cv.getContext("2d");
  x.clearRect(0, 0, cv.width, cv.height);
  x.font = `bold 27px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
  x.textAlign = "center"; x.textBaseline = "middle"; x.fillStyle = "#fff";
  [...ATLAS_CHARS].forEach((c, i) => x.fillText(c, (i % COLS) * CELL_W + CELL_W / 2, Math.floor(i / COLS) * CELL_H + CELL_H / 2 + 1));
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
    vec2 off = (position.xy * vec2(0.8, 1.0) + vec2(aWord.x, 0.0)) * px / resolution * 2.0;
    clip.xy += off * clip.w;
    gl_Position = clip;
    vUv = mix(aGlyph.xy, aGlyph.zw, uv); vAlpha = a; vMode = aMode;
  }`;
const GLYPH_FRAG = /* glsl */`
  uniform sampler2D atlas; uniform vec3 color; uniform vec3 ghost; uniform float level;
  varying vec2 vUv; varying float vAlpha; varying float vMode;
  void main() {
    float a = texture2D(atlas, vUv).a * vAlpha * level;
    if (a < 0.01) discard;
    vec3 c = mix(color, ghost, vMode);
    gl_FragColor = vec4(c * a, a);
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
// in display space (the scene pass already applied the renderer's tone mapping and output colour space)
const FX_SHADER = {
  uniforms: {
    tDiffuse: { value: null }, time: { value: 0 }, resolution: { value: new THREE.Vector2(1, 1) },
    glitch: { value: 0 }, seed: { value: 0 }, split: { value: 0 }, tear: { value: 1 }, blocks: { value: 1 },
    jitter: { value: 0 }, warp: { value: 0 }, dim: { value: 0 }, pump: { value: 0 }, vignette: { value: 0.35 },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse; uniform float time; uniform vec2 resolution;
    uniform float glitch, seed, split, tear, blocks, jitter, warp, dim, pump, vignette;
    varying vec2 vUv;
    float hash(float n) { return fract(sin(n * 127.1 + 311.7) * 43758.5453); }
    void main() {
      vec2 uv = vUv;
      if (warp > 0.001) {                                                       // REM: the world breathes and bends
        vec2 c = uv - 0.5; float r = length(c);
        float breathe = 1.0 - warp * 0.05 * (0.5 + 0.5 * sin(time * 0.8));
        uv = 0.5 + c * (breathe + warp * 0.10 * r * r * sin(time * 0.5 + r * 7.0));
        uv += warp * 0.010 * vec2(sin(uv.y * 7.0 + time * 0.9), cos(uv.x * 6.0 - time * 0.7));
      }
      if (jitter > 0.001) uv += jitter * 0.0015 * vec2(hash(floor(time * 24.0)) - 0.5, hash(floor(time * 24.0) + 7.0) - 0.5);
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
      col += warp * 0.02 * vec3(1.0, 0.5, 0.2) * (0.5 + 0.5 * sin(time * 0.3 + uv.y * 3.0));
      float vg = smoothstep(1.25, 0.35, length(vUv - 0.5) * 1.45);
      col *= mix(1.0, vg, vignette);
      gl_FragColor = vec4(col, 1.0);
    }`,
};

// ---------------------------------------------------------------------------------------------------------------------
export function createFx(renderer, scene, camera, data, quality) {
  const q = quality && typeof quality === "object" ? quality : { name: quality || "medium", post: true, bloom: true };
  const low = q.name === "low" || !q.post;
  const reduced = (() => { try { return !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches; } catch { return false; } })();
  // ?fxhold=1 (screenshots only): keeps a glitch burst on instead of the random short bursts
  const urlq = (() => { try { return new URLSearchParams(location.search); } catch { return new URLSearchParams(); } })();
  const hold = urlq.get("fxhold") === "1";
  const noPost = urlq.get("fxpost") === "0";           // ?fxpost=0: never use the composer (debug / comparison)
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
      color: { value: new THREE.Color(ORANGE).multiplyScalar(1.6) }, ghost: { value: new THREE.Color(0xffe2c0) },
      level: { value: 1 } },
    vertexShader: GLYPH_VERT, fragmentShader: GLYPH_FRAG,
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, fog: false,   // words are light: never hidden by a tower
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
    const phase = rng() * 6.283, half = (word.length - 1) * 0.4;
    for (let k = 0; k < word.length; k++) {
      const i = free.pop();
      aStart.setXYZ(i, start.x, start.y, start.z); aEnd.setXYZ(i, end.x, end.y, end.z);
      aTime.setXY(i, t0, dur);
      glyphRect(word[k], rect); aGlyph.setXYZW(i, rect[0], rect[1], rect[2], rect[3]);
      aWord.setXYZ(i, k * 0.8 - half, sizePx, phase); aMode.setX(i, mode);
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
  const lineCv = document.createElement("canvas"); lineCv.width = 1024; lineCv.height = 168;
  const lineTex = new THREE.CanvasTexture(lineCv); lineTex.colorSpace = THREE.SRGBColorSpace;
  const lineMat = new THREE.SpriteMaterial({ map: lineTex, transparent: true, opacity: 0, depthWrite: false, depthTest: false,
    toneMapped: false, sizeAttenuation: false, fog: false });
  const line = new THREE.Sprite(lineMat); line.renderOrder = 30; line.visible = false; root.add(line);
  line.scale.set(0.12 * lineCv.width / lineCv.height, 0.12, 1);
  let lineUntil = -1, lineStart = 0, lineAnchor = null;
  function drawLine(text, label) {
    const x = lineCv.getContext("2d");
    x.clearRect(0, 0, lineCv.width, lineCv.height);
    x.textAlign = "center"; x.textBaseline = "middle";
    let fs = 40; x.font = `italic ${fs}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
    while (fs > 22 && x.measureText(text).width > lineCv.width - 60) { fs -= 2; x.font = `italic ${fs}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`; }
    x.shadowColor = "rgba(255,106,0,0.95)"; x.shadowBlur = 22;
    x.fillStyle = "#ffe6cf"; x.fillText(text, lineCv.width / 2, 74, lineCv.width - 40);
    x.shadowBlur = 0; x.shadowColor = "transparent";
    x.font = `20px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
    x.fillStyle = "rgba(255,180,120,0.9)"; x.fillText(label, lineCv.width / 2, 128);
    lineTex.needsUpdate = true;
  }

  // ---------------- post-processing ----------------
  let composer = null, bloom = null, fxPass = null;
  function ensureComposer() {
    if (composer || noPost) return composer;
    composer = new EffectComposer(renderer);
    // The scene is rendered into the composer's targets exactly as it would be onto the canvas (the renderer applies its
    // tone mapping and output colour space when the target is flagged like an XR target), so the construct looks the
    // same with and without post-processing; bloom and the fx pass then work in display space.
    for (const rt of [composer.renderTarget1, composer.renderTarget2]) { rt.isXRRenderTarget = true; rt.texture.colorSpace = renderer.outputColorSpace; }
    composer.addPass(new RenderPass(scene, camera));
    if (!low && q.bloom !== false) {
      bloom = new UnrealBloomPass(resolution.clone(), BLOOM.strength, BLOOM.radius, BLOOM.threshold);
      composer.addPass(bloom);
    }
    fxPass = new ShaderPass(FX_SHADER);
    fxPass.material.toneMapped = false;                 // the input is already display-ready (see above)
    fxPass.uniforms.resolution.value = resolution;
    fxPass.uniforms.vignette.value = low ? 0.25 : 0.35;
    fxPass.uniforms.tear.value = reduced ? 0 : 1;
    fxPass.uniforms.blocks.value = reduced ? 0 : 1;
    composer.addPass(fxPass);
    composer.setSize(size.x, size.y);
    return composer;
  }
  if (!low) ensureComposer();

  // ---------------- state ----------------
  let fxTime = 0, wall = 0, speed = 1;
  const target = { pump: 0, glitch: 0, jitter: 0, warp: 0, dim: 0 };
  const cur = { pump: 0, glitch: 0, jitter: 0, warp: 0, dim: 0 };
  const burster = createBurster(rng);
  const queue = []; let nextRain = 0;
  let lastReplaySeq = -1, baseFov = null, stage = "AWAKE", view = "first";
  const fwd = new THREE.Vector3(), rightV = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();

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
    const sizePx = (low ? 17 : 19) * pr;
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
    const text = speech.text.trim().slice(0, 140);
    const label = speech.kind === "llm" ? "inner speech (generated)" : "inner speech (rule)";
    drawLine(text, label);
    lineStart = wall; lineUntil = wall + Math.min(9, 3.5 + text.length * 0.05);
    const chatRegions = speech.chat ? regionsOf(speech.chat) : null;
    lineAnchor = chatRegions ? data.districts[chatRegions[0]].pos : homePos;
    line.visible = true;
  }

  function weather(market) { Object.assign(target, marketTargets(market, reduced)); }

  // ---------------- per frame ----------------
  function update(dt, env) {
    dt = Math.min(0.1, Math.max(0, +dt || 0));
    wall += dt;
    stage = env?.stage || "AWAKE"; view = env?.view || view;
    speed = stage === "NREM" ? 0.45 : stage === "REM" ? 0.8 : 1;
    fxTime += dt * speed;

    // sleep targets
    target.dim = stage === "NREM" ? 1 : stage === "REM" ? 0.25 : 0;
    target.warp = stage === "REM" ? (reduced ? 0.3 : 1) : 0;
    const k = 1 - Math.exp(-dt * 1.5);
    for (const key of Object.keys(cur)) cur[key] += (target[key] - cur[key]) * k;

    // rain queue (rate-limited) and landings
    if (queue.length && wall >= nextRain) { nextRain = wall + RAIN_GAP; dropMessage(queue.shift()); }
    while (pendingSplash.length && pendingSplash[0].t <= fxTime) { const s = pendingSplash.shift(); splashAt(s.x, s.y, s.z, s.r); }
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
    const active = glitchNow > 0.01 || cur.warp > 0.01 || cur.dim > 0.01 || cur.pump > 0.01 || cur.jitter > 0.01;
    if (active && !composer) ensureComposer();
    if (fxPass) {
      const u = fxPass.uniforms;
      u.time.value = wall; u.glitch.value = glitchNow; u.seed.value = burster.seed;
      u.split.value = (reduced ? 2 : 4.5) * pr; u.jitter.value = cur.jitter; u.warp.value = cur.warp; u.dim.value = cur.dim;
      u.pump.value = cur.pump;
    }
    if (bloom) bloom.strength = BLOOM.strength * (1 + cur.pump * 0.6 * (0.5 + 0.5 * Math.sin(wall * 1.1)) - cur.dim * 0.5);

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
      else { camera.getWorldDirection(fwd); line.position.copy(camera.position).addScaledVector(fwd, 150).y += 14; }
    }
  }

  function driftMessage(text) {
    const words = splitWords(text, { maxWords: 12, maxLen: MAX_WORD_LEN, maxGlyphs: 80 });
    if (!words.length) return;
    camera.getWorldDirection(fwd); rightV.crossVectors(fwd, camera.up).normalize();
    const sizePx = (low ? 18 : 21) * pr;
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
    const useComposer = composer && (!low || fxPass.uniforms.glitch.value > 0.01 || cur.warp > 0.01 || cur.dim > 0.01
      || cur.pump > 0.01 || cur.jitter > 0.01);
    if (useComposer) composer.render();
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
    if (baseFov !== null) { camera.fov = baseFov; camera.updateProjectionMatrix(); baseFov = null; }
    gg.dispose(); glyphMat.dispose(); sg.dispose(); splashMat.dispose(); wave.geometry.dispose(); waveMat.dispose();
    lineTex.dispose(); lineMat.dispose(); atlas.tex.dispose();
    if (composer) { for (const p of composer.passes) p.dispose?.(); composer.dispose(); composer = null; bloom = null; fxPass = null; }
  }

  const api = { rain, innerLine, weather, update, render, resize, dispose,
    get state() { return { ...cur, burst: burster.seed, queued: queue.length, free: free.length, composer: !!composer, reduced, hold }; } };
  try { if (window.__sub01) Object.defineProperty(window.__sub01, "fx", { configurable: true, enumerable: true, get: () => api.state }); } catch { /* debug only */ }
  return api;
}
