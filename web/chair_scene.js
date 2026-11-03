// SUB-01 · the chair scene (web/chair.html): the character seated in a tall wooden chair, head cap, straps and cables,
// under one hanging lamp in a block-walled cell, after the reference image. His body moves from the measured numbers
// (chair.py Drive: tension, slack, heavy, flat), never from the button: the only things that follow the button are the
// lamp dip and the sparks at delivery. The procedural layer is additive on the seated clip and bounded by the restraints
// (the head stays in the cap, the wrists under the straps, the torso against the belt), with springs for the body's own
// inertia; on top, what a body does on its own (the idle, the panting after, twitches, a swallow), none of it from the button.
// Flat (the rule of the piece): the body hangs, the lamp sinks; revival: a gasp and a jolt from the measured burst.
// Artistic mappings of simulated signals, not physiology. Everything here is procedural geometry: no bought model.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { prep, fixClip } from "./room/char_mixamo.js";

const D2R = Math.PI / 180;

// a spring that follows its target faster up than down: the body tenses at once and lets go slowly. Critically damped;
// integrated in sub-steps so a slow frame (a background tab, a phone) cannot make it overshoot or blow up
class Spring {
  constructor(up = 10, down = 2) { this.x = 0; this.v = 0; this.t = 0; this.up = up; this.down = down; }
  step(dt) {
    const n = Math.min(24, Math.max(1, Math.ceil(dt * Math.max(this.up, this.down) / 0.15))), h = dt / n;
    for (let i = 0; i < n; i++) { const k = this.t > this.x ? this.up : this.down, a = k * k * (this.t - this.x) - 2 * k * this.v; this.v += a * h; this.x += this.v * h; }
    return this.x;
  }
}

// --- procedural materials -----------------------------------------------------------------------------------------------
function canvasTex(w, h, draw, repeat = [1, 1]) {
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
const rnd = (a, b) => a + Math.random() * (b - a);
function blockWall(wm = 6, hm = 3.2) {
  const map = canvasTex(1024, 512, (g, W, H) => {
    g.fillStyle = "#6f6248"; g.fillRect(0, 0, W, H);                           // mortar
    const bw = W / 10, bh = H / 10;
    for (let r = 0; r < 10; r++) for (let i = -1; i < 11; i++) {
      const x = i * bw + (r % 2 ? bw / 2 : 0), y = r * bh, n = Math.random();
      g.fillStyle = `rgb(${136 + n * 46 | 0},${118 + n * 40 | 0},${78 + n * 30 | 0})`; g.fillRect(x + 3, y + 3, bw - 6, bh - 6);
      g.fillStyle = "rgba(0,0,0,.14)"; for (let k = 0; k < 16; k++) g.fillRect(x + 5 + Math.random() * (bw - 12), y + 5 + Math.random() * (bh - 12), rnd(2, 7), rnd(1, 3));
      g.fillStyle = "rgba(255,255,255,.07)"; g.fillRect(x + 3, y + 3, bw - 6, 2);                 // a lit top edge per block
    }
    // damp and soot: dark stains low
    const grd = g.createLinearGradient(0, H * 0.55, 0, H); grd.addColorStop(0, "rgba(0,0,0,0)"); grd.addColorStop(1, "rgba(10,8,4,.45)"); g.fillStyle = grd; g.fillRect(0, 0, W, H);
    for (let k = 0; k < 14; k++) { g.fillStyle = `rgba(20,14,8,${rnd(.05, .18)})`; g.beginPath(); g.ellipse(rnd(0, W), rnd(H * .4, H), rnd(30, 120), rnd(20, 80), 0, 0, Math.PI * 2); g.fill(); }
  }, [wm / 4.8, hm / 2.4]);
  return new THREE.MeshStandardMaterial({ map, roughness: 0.95, metalness: 0 });
}
function concrete() {
  const map = canvasTex(512, 512, (g, W, H) => {
    g.fillStyle = "#4a4640"; g.fillRect(0, 0, W, H);
    for (let k = 0; k < 4000; k++) { g.fillStyle = `rgba(${rnd(20, 90) | 0},${rnd(18, 85) | 0},${rnd(16, 78) | 0},${rnd(.08, .3)})`; g.fillRect(rnd(0, W), rnd(0, H), rnd(1, 4), rnd(1, 4)); }
    for (let k = 0; k < 9; k++) { g.fillStyle = `rgba(15,12,8,${rnd(.1, .3)})`; g.beginPath(); g.ellipse(rnd(0, W), rnd(0, H), rnd(30, 110), rnd(20, 70), rnd(0, 3), 0, Math.PI * 2); g.fill(); }
    g.strokeStyle = "rgba(0,0,0,.35)"; g.lineWidth = 2; for (let k = 0; k < 5; k++) { g.beginPath(); let x = rnd(0, W), y = rnd(0, H); g.moveTo(x, y); for (let j = 0; j < 8; j++) { x += rnd(-40, 40); y += rnd(-40, 40); g.lineTo(x, y); } g.stroke(); }
  }, [4, 3]);
  return new THREE.MeshStandardMaterial({ map, roughness: 0.92, metalness: 0.02 });
}
function woodGrain(base = "#4a2e1a") {
  const map = canvasTex(256, 256, (g, W, H) => {
    g.fillStyle = base; g.fillRect(0, 0, W, H);
    for (let i = 0; i < 90; i++) { g.strokeStyle = `rgba(${i % 2 ? 20 : 120},${i % 2 ? 10 : 70},${i % 2 ? 5 : 35},${rnd(.08, .2)})`; g.lineWidth = rnd(1, 3);
      g.beginPath(); const y = rnd(0, H); g.moveTo(0, y); g.bezierCurveTo(80, y + rnd(-10, 10), 170, y + rnd(-10, 10), W, y); g.stroke(); }
  });
  return new THREE.MeshStandardMaterial({ map, roughness: 0.65, metalness: 0.05 });
}
function leatherMat() {
  const map = canvasTex(128, 128, (g, W, H) => { g.fillStyle = "#1c1511"; g.fillRect(0, 0, W, H); for (let k = 0; k < 1500; k++) { g.fillStyle = `rgba(${rnd(30, 70) | 0},${rnd(22, 50) | 0},${rnd(16, 36) | 0},${rnd(.2, .5)})`; g.fillRect(rnd(0, W), rnd(0, H), 1, 1); } }, [3, 3]);
  return new THREE.MeshStandardMaterial({ map, roughness: 0.5, metalness: 0.05 });
}

export async function createScene({ canvas, lite = false, small = false, reduced = false, onProgress = () => {} }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !lite, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lite ? 1 : 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = !lite && !small; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x030303);
  const scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x050403, 0.085);
  const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 40); camera.position.set(0.15, 1.3, 3.5);
  const controls = new OrbitControls(camera, canvas); controls.target.set(0, 1.12, 0); controls.enablePan = false; controls.enableDamping = true;
  controls.minDistance = 2.0; controls.maxDistance = 4.8; controls.minPolarAngle = 1.1; controls.maxPolarAngle = 1.72; controls.minAzimuthAngle = -0.8; controls.maxAzimuthAngle = 0.8;
  controls.rotateSpeed = 0.5; controls.update();

  // --- the cell: block walls on three sides, a concrete floor with a drain, a ceiling, a door ----------------------------
  const wallMat = blockWall(), floorMat = concrete();
  const back = new THREE.Mesh(new THREE.PlaneGeometry(7, 3.4), wallMat); back.position.set(0, 1.7, -1.3); back.receiveShadow = true; scene.add(back);
  for (const sx of [-1, 1]) { const w = new THREE.Mesh(new THREE.PlaneGeometry(6, 3.4), blockWall(6, 3.4)); w.position.set(sx * 3.2, 1.7, 1.7); w.rotation.y = -sx * Math.PI / 2; w.receiveShadow = true; scene.add(w); }
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), floorMat); floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.MeshStandardMaterial({ color: 0x1a1612, roughness: 1 })); ceiling.rotation.x = Math.PI / 2; ceiling.position.y = 3.4; scene.add(ceiling);
  const metal = new THREE.MeshStandardMaterial({ color: 0x8a8a8a, roughness: 0.38, metalness: 0.85 }), dark = new THREE.MeshStandardMaterial({ color: 0x24242a, roughness: 0.55, metalness: 0.5 });
  const drain = new THREE.Mesh(new THREE.CircleGeometry(0.16, 24), new THREE.MeshStandardMaterial({ color: 0x0b0b0b, roughness: 0.6, metalness: 0.6 })); drain.rotation.x = -Math.PI / 2; drain.position.set(0.55, 0.003, 0.65); scene.add(drain);
  for (let k = -2; k <= 2; k++) { const bar = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.006, 0.02), metal); bar.position.set(0.55, 0.006, 0.65 + k * 0.05); scene.add(bar); }
  const door = new THREE.Group(); scene.add(door); door.position.set(-3.19, 0, 0.3); door.rotation.y = Math.PI / 2;
  const doorMat = new THREE.MeshStandardMaterial({ color: 0x2b2f33, roughness: 0.6, metalness: 0.6 });
  const leaf = new THREE.Mesh(new THREE.BoxGeometry(0.95, 2.1, 0.06), doorMat); leaf.position.set(0, 1.05, 0); door.add(leaf);
  const doorFrame = new THREE.Mesh(new THREE.BoxGeometry(1.08, 2.2, 0.1), new THREE.MeshStandardMaterial({ color: 0x1a1c1f, roughness: 0.7, metalness: 0.5 })); doorFrame.position.set(0, 1.1, -0.03); door.add(doorFrame);
  const slit = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.2), new THREE.MeshStandardMaterial({ color: 0x8fb4d0, emissive: 0x5f88a8, emissiveIntensity: 0.9, roughness: 0.2 })); slit.position.set(0, 1.6, 0.035); door.add(slit);
  const doorLight = new THREE.PointLight(0x7fa6c8, 1.6, 4, 2); doorLight.position.set(-2.9, 1.6, 0.3); scene.add(doorLight);

  // --- the lamp: a cord from the ceiling, a cone shade, a bulb, the spot inside, a haze cone -----------------------------
  scene.add(new THREE.HemisphereLight(0x6a5838, 0x080604, 0.32));
  const lampPos = new THREE.Vector3(0.2, 2.75, 0.9);
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 3.4 - lampPos.y, 6), dark); cord.position.set(lampPos.x, (3.4 + lampPos.y) / 2, lampPos.z); scene.add(cord);
  const shade = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.2, 28, 1, true), new THREE.MeshStandardMaterial({ color: 0x1f1f22, roughness: 0.5, metalness: 0.7, side: THREE.DoubleSide }));
  shade.position.copy(lampPos).add(new THREE.Vector3(0, -0.1, 0)); scene.add(shade);
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 12), new THREE.MeshStandardMaterial({ color: 0xffe9b0, emissive: 0xffd080, emissiveIntensity: 6, roughness: 0.3 })); bulb.position.copy(lampPos).add(new THREE.Vector3(0, -0.16, 0)); scene.add(bulb);
  const lamp = new THREE.SpotLight(0xffd79a, 64, 10, 0.66, 0.55, 1.4); lamp.position.copy(bulb.position); lamp.target.position.set(0, 0.9, 0.1);
  lamp.castShadow = renderer.shadowMap.enabled; lamp.shadow.mapSize.set(1024, 1024); lamp.shadow.bias = -0.0004; lamp.shadow.radius = 3; scene.add(lamp, lamp.target);
  const hazeTex = canvasTex(64, 256, (g, W, H) => { const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, "rgba(255,220,160,.55)"); gr.addColorStop(1, "rgba(255,220,160,0)"); g.fillStyle = gr; g.fillRect(0, 0, W, H); });
  const haze = new THREE.Mesh(new THREE.ConeGeometry(1.9, 2.6, 32, 1, true), new THREE.MeshBasicMaterial({ map: hazeTex, transparent: true, opacity: 0.16, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }));
  haze.position.copy(bulb.position).add(new THREE.Vector3(0, -1.3, 0)); haze.rotation.x = Math.PI; haze.renderOrder = 5; scene.add(haze);
  const fill = new THREE.PointLight(0xffe2b0, 3.2, 6, 2); fill.position.set(-1.0, 1.3, 1.8); scene.add(fill);
  const glow = new THREE.PointLight(0xbfe0ff, 0, 1.4, 2); scene.add(glow);                   // the electrode glow at delivery
  const base = { lamp: lamp.intensity, exposure: renderer.toneMappingExposure, bulb: 6, haze: 0.16 };

  // --- the character and his seated clip ----------------------------------------------------------------------------------
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  const load = url => new Promise((ok, no) => loader.load(url, ok, e => onProgress(url, e), no));
  onProgress("character", null);
  const [g, cg] = await Promise.all([load("room/char_mixamo.glb"), load("room/mh_mx/room_seated_idle.glb")]);
  const conv = prep(THREE, g);
  const boy = g.scene; scene.add(boy);
  const bones = {};
  // The face: the model has no face rig (no morph targets, no jaw or eye bones), so expression is painted into the head
  // material's shader from masks drawn in the head texture's own UV space (the eye and mouth islands of the atlas in
  // room/char_mixamo.glb, located by hand): eyelids that close from the top (a blink, a squint under tension, clenched at
  // a strong response, shut while flat, heavy with the adaptation), the mouth opening (with the tension, the jolt, the
  // panting, a line being said; slack while flat), the gaze (the eye opening's pixels slide under the lids), the teeth
  // bared when clenched, a flush, sweat (a sheen) and the pallor of the flatline. Driven by the same measured numbers
  // as the body, never by the button.
  const face = { sh: null, blink: 0, blinkLen: 0.16, nextBlink: 2.0, force: null };
  const MS = 2048 / 4096;                                                                                         // the masks are drawn at half the atlas
  const ellipse = (g, cx, cy, rx, ry, rot, fill) => { g.save(); g.translate(cx * MS, cy * MS); g.rotate(rot); g.scale(rx * MS, ry * MS); g.fillStyle = fill(g); g.beginPath(); g.arc(0, 0, 1, 0, Math.PI * 2); g.fill(); g.restore(); };
  const EYES = [[1762, 655, 150, 68, -0.1, 1], [2575, 648, 160, 62, -0.1, -1]];      // cx, cy, rx, ry, tilt, the island's u direction (the two islands mirror each other)
  const MOUTH = [2385, 2290, Math.atan2(160, 130), 110, 42];                        // cx, cy, the lip line's angle, rx, ry
  // red: the eyelid, 1 at the upper lid, ~0 at the lower; green: the mouth, 1 at the centre; blue: the eye opening (the
  // white and the iris), what slides under the lids with the gaze, above 0.5 on one island and below on the mirrored one
  const faceMask = canvasTex(2048, 2048, (g, W) => {
    g.fillStyle = "#000"; g.fillRect(0, 0, W, W); g.globalCompositeOperation = "lighter";
    for (const [cx, cy, rx, ry, rot, dir] of EYES) {
      ellipse(g, cx, cy, rx, ry, rot, g => { const gr = g.createLinearGradient(0, -1, 0, 1); gr.addColorStop(0, "rgb(255,0,0)"); gr.addColorStop(1, "rgb(14,0,0)"); return gr; });
      ellipse(g, cx, cy, rx * 0.8, ry * 0.62, rot, g => { const gr = g.createRadialGradient(0, 0, 0, 0, 0, 1), hi = dir > 0 ? 255 : 125, lo = dir > 0 ? 132 : 0;
        gr.addColorStop(0, `rgb(0,0,${hi})`); gr.addColorStop(0.7, `rgb(0,0,${hi})`); gr.addColorStop(1, `rgb(0,0,${lo})`); return gr; });
    }
    ellipse(g, MOUTH[0], MOUTH[1], MOUTH[3], MOUTH[4], MOUTH[2], g => { const gm = g.createRadialGradient(0, 0, 0, 0, 0, 1); gm.addColorStop(0, "rgb(0,255,0)"); gm.addColorStop(0.7, "rgb(0,210,0)"); gm.addColorStop(1, "rgb(0,0,0)"); return gm; });
  });
  // the skin: red where the face flushes (round the eye islands and the mouth island: cheeks, lids, chin), green where it
  // sweats (the same, wider), blue the mouth's own across-the-lips coordinate (0.5 on the lip line) for the teeth band
  const skinMask = canvasTex(2048, 2048, (g, W) => {
    g.fillStyle = "#000"; g.fillRect(0, 0, W, W); g.globalCompositeOperation = "lighter";
    const soft = (cx, cy, rx, ry, rot, r, gg) => ellipse(g, cx, cy, rx, ry, rot, g => { const gr = g.createRadialGradient(0, 0, 0, 0, 0, 1); gr.addColorStop(0, `rgb(${r},${gg},0)`); gr.addColorStop(0.4, `rgb(${r},${gg},0)`); gr.addColorStop(1, "rgb(0,0,0)"); return gr; });
    for (const [cx, cy, , , rot] of EYES) soft(cx, cy + 40, 420, 300, rot, 235, 255);
    soft(MOUTH[0], MOUTH[1], 560, 460, MOUTH[2], 255, 200);
    ellipse(g, MOUTH[0], MOUTH[1], MOUTH[3] * 1.1, MOUTH[4] * 1.1, MOUTH[2], g => { const gr = g.createLinearGradient(0, -1, 0, 1); gr.addColorStop(0, "rgb(0,0,8)"); gr.addColorStop(1, "rgb(0,0,255)"); return gr; });
  });
  for (const m of [faceMask, skinMask]) { m.flipY = false; m.colorSpace = THREE.NoColorSpace; m.needsUpdate = true; }
  const faceShader = m => {
    m.onBeforeCompile = sh => {
      sh.uniforms.uFaceMask = { value: faceMask }; sh.uniforms.uSkinMask = { value: skinMask }; sh.uniforms.uLid = { value: 0 }; sh.uniforms.uMouth = { value: 0 };
      sh.uniforms.uGaze = { value: new THREE.Vector2(0, 0) }; sh.uniforms.uFlush = { value: 0 }; sh.uniforms.uPale = { value: 0 }; sh.uniforms.uSweat = { value: 0 }; sh.uniforms.uTeeth = { value: 0 };
      sh.uniforms.uSkin = { value: new THREE.Color("#e6b89c") };
      sh.fragmentShader = sh.fragmentShader
        .replace("#include <common>", "#include <common>\nuniform sampler2D uFaceMask; uniform sampler2D uSkinMask; uniform float uLid; uniform float uMouth; uniform vec2 uGaze; uniform float uFlush; uniform float uPale; uniform float uSweat; uniform float uTeeth; uniform vec3 uSkin;")
        .replace("#include <map_fragment>", `
          vec4 fm = texture2D(uFaceMask, vMapUv);
          vec4 sk = texture2D(uSkinMask, vMapUv);
          float eyeMag = fm.b > 0.5 ? (fm.b - 0.5) * 2.0 : fm.b * 2.0;
          float eyeSgn = fm.b > 0.5 ? 1.0 : -1.0;
          vec2 uvm = vMapUv - vec2(uGaze.x * eyeSgn, uGaze.y) * eyeMag;                      // the eye opening slides under the lids with the gaze
          diffuseColor *= texture2D(map, uvm);
          float lum = dot(diffuseColor.rgb, vec3(0.3, 0.59, 0.11));
          diffuseColor.rgb *= mix(vec3(1.0), vec3(1.12, 0.84, 0.82), uFlush * sk.r);                            // the flush
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(lum) * vec3(0.88, 0.92, 1.0), 0.55 * uPale * sk.r);      // pale and cold while flat
          if (fm.r > 0.02) {
            float edge = 1.02 - uLid;
            float covered = smoothstep(edge - 0.04, edge + 0.04, fm.r);
            vec3 lidSkin = texture2D(map, vMapUv + vec2(0.0, 0.016 * (2.0 * fm.r - 2.35))).rgb;   // the skin just above the upper lid, with its own shading
            lidSkin *= 1.0 - 0.2 * uLid * smoothstep(0.35, 1.0, fm.r);                              // the crease deepens as the lid closes
            diffuseColor.rgb = mix(diffuseColor.rgb, lidSkin * (0.9 + 0.1 * fm.r), covered);
            float lash = (1.0 - smoothstep(0.0, 0.05, abs(fm.r - edge))) * smoothstep(0.03, 0.12, uLid);
            diffuseColor.rgb = mix(diffuseColor.rgb, uSkin * 0.22, lash * 0.75);
          }
          if (fm.g > 0.02) {
            float open = smoothstep(1.0 - uMouth, 1.0 - uMouth + 0.2, fm.g) * step(0.01, uMouth);
            float band = (1.0 - smoothstep(0.07, 0.15, abs(sk.b - 0.5))) * step(0.02, sk.b) * uTeeth;         // the teeth, bared when clenched
            vec3 inside = mix(vec3(0.05, 0.015, 0.012), vec3(0.82, 0.76, 0.66), band);
            diffuseColor.rgb = mix(diffuseColor.rgb, inside, open);
          }`)
        .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
          roughnessFactor = mix(roughnessFactor, 0.3, uSweat * sk.g * smoothstep(0.12, 0.35, dot(diffuseColor.rgb, vec3(0.3, 0.59, 0.11))));   // sweat: a sheen on the skin, the hair stays matte`);
      face.sh = sh;
    };
    m.needsUpdate = true;
  };
  boy.traverse(o => {
    if (o.isMesh) { o.frustumCulled = false; o.castShadow = true; o.receiveShadow = true;
      for (const m of (Array.isArray(o.material) ? o.material : [o.material])) { if (!m) continue; m.emissive && m.emissive.setRGB(0, 0, 0); m.roughness = 0.8; m.envMapIntensity = 0.3; if (m.name === "owner_head") faceShader(m); } }
    if (o.isBone) bones[o.name] = o;
  });
  const mixer = new THREE.AnimationMixer(boy);
  const clip = fixClip(THREE, cg.animations[0], conv);
  const PB = THREE.PropertyBinding; clip.tracks = clip.tracks.filter(t => PB.findNode(boy, PB.parseTrackName(t.name).nodeName));
  const action = mixer.clipAction(clip); action.play();
  mixer.update(0.01); boy.updateMatrixWorld(true);
  const wp = b => bones[b] ? bones[b].getWorldPosition(new THREE.Vector3()) : null;
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  // --- the chair, built round the pose: a heavy oak frame, a slatted back, padded arms, straps with buckles --------------
  const chair = new THREE.Group(); scene.add(chair);
  const hips = wp("Hips"), knL = wp("LeftLeg"), knR = wp("RightLeg"), hL = wp("LeftHand"), hR = wp("RightHand"), head = wp("Head");
  // the crown and the chin, read off the skinned head mesh in this pose: the rig's head_end bone points off the forehead
  // (16 cm ahead of and 8 cm below the top of the hair on this model), so a cap placed on it hung in front of his face
  const skull = (() => {
    let hm = null; boy.traverse(o => { if (!hm && o.isSkinnedMesh && (Array.isArray(o.material) ? o.material : [o.material]).some(m => m && m.name === "owner_head")) hm = o; });
    if (!hm) return null;
    hm.skeleton.update(); const pos = hm.geometry.attributes.position, v = new THREE.Vector3(); let topY = -Infinity, botY = Infinity;
    for (let i = 0; i < pos.count; i++) { hm.getVertexPosition(i, v); topY = Math.max(topY, v.y); botY = Math.min(botY, v.y); }
    let n = 0, cx = 0, cz = 0, chin = null;                                                   // the band where the rim sits, 4 to 8 cm under the top; the chin: the lowest, most forward point
    for (let i = 0; i < pos.count; i++) { hm.getVertexPosition(i, v); const d = topY - v.y; if (d > 0.04 && d < 0.08) { n++; cx += v.x; cz += v.z; } if (v.y < botY + 0.02 && (!chin || v.z > chin.z)) chin = v.clone(); }
    return n ? { top: V(cx / n, topY, cz / n), chin } : null;
  })();
  const top = skull ? skull.top : wp("head_end") || head.clone().add(V(0, 0.12, 0));
  const spine = wp("Spine"), fL = wp("LeftFoot"), fR = wp("RightFoot"), elL = wp("LeftForeArm"), elR = wp("RightForeArm");
  // he faces +z (the camera); the hips bone sits ~0.23 m above the seat on this rig; the seat runs from behind the hips to
  // just short of the knees, the back posts stand behind it
  const seatY = hips.y - 0.23, seatZ0 = hips.z - 0.17, seatZ1 = Math.max(knL.z, knR.z) - 0.03, seatD = Math.max(0.44, seatZ1 - seatZ0), seatW = 0.66;
  const wood = woodGrain("#4a2e1a"), wood2 = woodGrain("#3b2414"), leather = leatherMat(), pad = new THREE.MeshStandardMaterial({ color: 0x241a14, roughness: 0.7 });
  const sponge = new THREE.MeshStandardMaterial({ color: 0xb79c62, roughness: 0.95 });
  const box = (w, h, d, mat, x, y, z, rx = 0, ry = 0, rz = 0, r = 0.006) => { const m = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, r), mat); m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.castShadow = m.receiveShadow = true; chair.add(m); return m; };
  const screw = (x, y, z, rx = 0, ry = 0) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.006, 10), metal); m.position.set(x, y, z); m.rotation.set(rx, ry, 0); chair.add(m); return m; };
  const cz = (seatZ0 + seatZ1) / 2, P = 0.09;                                              // post thickness
  box(seatW, 0.07, seatD, wood, 0, seatY, cz, 0, 0, 0, 0.01);                                // the seat
  box(seatW - 0.02, 0.09, 0.05, wood2, 0, seatY - 0.08, seatZ1 - 0.02);                     // the apron
  for (const sx of [-1, 1]) box(P, seatY, P, wood2, sx * (seatW / 2 - P / 2), seatY / 2, seatZ1 - P / 2);             // front legs
  for (const sx of [-1, 1]) box(0.05, 0.05, seatD - 0.1, wood2, sx * (seatW / 2 - P / 2), 0.16, cz);                 // stretchers
  box(seatW - 0.1, 0.05, 0.05, wood2, 0, 0.16, seatZ1 - P / 2);
  const backZ = seatZ0 - 0.03, backH = 2.1;
  for (const sx of [-1, 1]) box(P, backH, P, wood2, sx * (seatW / 2 - P / 2), backH / 2, backZ);                      // the tall posts
  box(seatW, 0.12, 0.07, wood, 0, backH - 0.06, backZ, 0, 0, 0, 0.01);                                                // the top rail
  box(seatW, 0.09, 0.06, wood, 0, seatY + 0.3, backZ);                                                                // the low rail
  for (let k = -2; k <= 2; k++) box(0.06, backH - 0.5 - (seatY + 0.35), 0.03, wood, k * 0.11, (backH - 0.12 + seatY + 0.35) / 2, backZ + 0.005);   // slats
  box(seatW - 0.2, 0.3, 0.035, wood, 0, head.y - 0.05, backZ + 0.02, 0, 0, 0, 0.008);                                 // the headboard
  for (const [h, sx, el] of [[hL, -1, elL], [hR, 1, elR]]) {                                                          // the arms
    const ay = h.y - 0.045, az = h.z, ax = sx * (seatW / 2 - 0.01);
    box(0.15, 0.05, 0.62, wood, ax, ay, az + 0.02, 0, 0, 0, 0.008);
    box(0.12, 0.02, 0.4, pad, ax, ay + 0.035, az + 0.04, 0, 0, 0, 0.006);                                           // the leather pad
    box(0.06, ay - seatY - 0.03, 0.06, wood2, ax, (ay + seatY) / 2, az + 0.26);                                      // the arm posts
    box(0.06, ay - seatY - 0.03, 0.06, wood2, ax, (ay + seatY) / 2, az - 0.2);
    const strap = new THREE.Mesh(new THREE.TorusGeometry(0.056, 0.014, 8, 20, Math.PI), leather); strap.position.set(h.x, ay + 0.035, az); strap.rotation.set(0, Math.PI / 2, 0); strap.scale.set(1, 1, 1.4); strap.castShadow = true; chair.add(strap);
    const buckle = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.016, 0.03), metal); buckle.position.set(h.x + sx * 0.052, ay + 0.045, az); chair.add(buckle);
    screw(h.x + sx * 0.062, ay + 0.058, az, Math.PI / 2, 0);
  }
  const belt = (y, z, r, sy = 1, w = 0.02) => { const m = new THREE.Mesh(new THREE.TorusGeometry(r, w, 8, 40, Math.PI), leather); m.position.set(spine.x, y, z); m.rotation.set(Math.PI / 2, 0, 0); m.scale.set(1, 1, sy); m.castShadow = true; chair.add(m); return m; };
  const chest = belt(spine.y + 0.02, spine.z - 0.03, 0.22, 0.78, 0.022);                                              // the chest strap
  const chestBuckle = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.045, 0.014), metal); chestBuckle.position.set(spine.x, spine.y + 0.02, spine.z + 0.145); chair.add(chestBuckle);
  const lap = belt(hips.y + 0.02, hips.z - 0.02, 0.2, 0.9, 0.02);                                                     // the lap belt
  const lapBuckle = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.04, 0.014), metal); lapBuckle.position.set(hips.x, hips.y + 0.02, hips.z + 0.17); chair.add(lapBuckle);
  for (const f of [fL, fR]) { const s = new THREE.Mesh(new THREE.TorusGeometry(0.062, 0.014, 8, 20), leather); s.position.set(f.x, f.y + 0.09, f.z - 0.05); s.rotation.y = Math.PI / 2; s.scale.set(1, 1.2, 1); s.castShadow = true; chair.add(s);
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, 0.012), metal); b.position.set(f.x, f.y + 0.09, f.z + 0.015); chair.add(b); }   // ankle straps
  // the headgear: a sponge-rimmed metal cap with its stud, and the chin strap, ride on the head (children of the Head bone,
  // so they turn and wander with it: the cap is on him, not over him); the bracket stays on the frame and its arm is a
  // hinged, telescoping link from the bracket to the cap; the two head cables re-anchor to the stud as it moves
  const clamp = new THREE.Group(); chair.add(clamp);
  const capY = top.y - 0.06;                                                                  // the rim round the crown where the skull is as wide as the ring, the cap over the hair
  const headUp = bones.Head ? V(0, 1, 0).applyQuaternion(bones.Head.getWorldQuaternion(new THREE.Quaternion())).normalize() : V(0, 1, 0);
  const capG = new THREE.Group(); capG.position.set(top.x, capY, top.z); capG.quaternion.setFromUnitVectors(V(0, 1, 0), headUp); clamp.add(capG);   // the cap sits square on the skull's axis
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.095, 0.06, 24), metal); cap.position.set(0, 0.035, 0); cap.castShadow = true; capG.add(cap);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.095, 0.018, 10, 32), sponge); rim.position.set(0, -0.005, 0); rim.rotation.x = Math.PI / 2; capG.add(rim);
  const stud = new THREE.Mesh(new THREE.SphereGeometry(0.022, 12, 10), new THREE.MeshStandardMaterial({ color: 0x9fd3ff, emissive: 0x3a7fc0, emissiveIntensity: 0.0, roughness: 0.3, metalness: 0.6 }));
  stud.position.set(0, 0.07, 0); capG.add(stud);
  const studW = new THREE.Vector3(), capW = new THREE.Vector3(), armTo = new THREE.Vector3();
  const bracketTop = V(top.x, capY + 0.06, backZ + 0.05);                                     // where the arm hinges on the frame
  const bracket = new THREE.Mesh(new THREE.BoxGeometry(0.03, backH - 0.12 - (capY + 0.055), 0.03), dark); bracket.position.set(top.x, (capY + 0.055 + backH - 0.12) / 2, backZ + 0.05); clamp.add(bracket);
  const armLen0 = top.z - backZ - 0.03;
  const bArm = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, armLen0), dark); bArm.castShadow = true; clamp.add(bArm);
  const chinAt = skull ? V(top.x, skull.chin.y + 0.085, skull.chin.z - 0.025) : V(head.x, head.y - 0.03, head.z);   // under the jaw, ear to ear
  const chin = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.012, 8, 30, Math.PI), leather); chin.position.copy(chinAt); chin.rotation.set(0, 0, Math.PI); chin.scale.set(1, 0.9, 1); clamp.add(chin);
  boy.updateMatrixWorld(true); chair.updateMatrixWorld(true);
  if (bones.Head) for (const o of [capG, chin]) bones.Head.attach(o);                         // world transforms kept; from now on they move with the head
  stud.getWorldPosition(studW); glow.position.copy(studW).add(V(0, 0.05, 0.05));
  const cables = [];                                                                          // {mesh, pts, r, off, anchor}: the head cables, re-anchored to the stud
  const tube = (pts, r, mat, follow = false) => { const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, r, 7, false), mat); m.castShadow = true; chair.add(m);
    if (follow) cables.push({ mesh: m, pts, r, off: pts[0].clone().sub(studW), anchor: pts[0].clone() }); return m; };
  const tmpA = new THREE.Vector3();
  function headgear() {                                                                       // each frame: the arm from the bracket to the cap, the cables from the stud
    cap.getWorldPosition(capW); stud.getWorldPosition(studW);
    glow.position.copy(studW).add(tmpA.set(0, 0.05, 0.05));
    armTo.copy(capW); chair.worldToLocal(armTo); armTo.y += 0.01; armTo.z -= 0.075;            // the arm meets the cap at its back edge
    bArm.position.copy(bracketTop).add(armTo).multiplyScalar(0.5); bArm.lookAt(chair.localToWorld(tmpA.copy(armTo)));
    bArm.scale.z = Math.max(0.3, bracketTop.distanceTo(armTo) / armLen0);
    for (const c of cables) { tmpA.copy(studW).add(c.off); chair.worldToLocal(tmpA);
      if (tmpA.distanceTo(c.anchor) > 0.003) { c.anchor.copy(tmpA); c.pts[0].copy(tmpA); c.mesh.geometry.dispose(); c.mesh.geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(c.pts), 48, c.r, 7, false); } }
  }
  const junction = box(0.2, 0.28, 0.07, dark, -1.55, 1.7, -1.26);
  const lever = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.2, 0.03), metal); lever.position.set(-1.55, 1.78, -1.2); lever.rotation.x = -0.5; scene.add(lever);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.025, 12, 10), new THREE.MeshStandardMaterial({ color: 0x7a1a1a, roughness: 0.4 })); knob.position.set(-1.55, 1.87, -1.15); scene.add(knob);
  tube([V(top.x, capY + 0.065, top.z), V(top.x - 0.1, capY + 0.3, top.z - 0.12), V(-0.7, 2.3, -0.7), V(-1.45, 2.1, -1.2), V(-1.55, 1.85, -1.23)], 0.013, dark, true);
  tube([V(top.x + 0.03, capY + 0.06, top.z + 0.02), V(top.x + 0.25, capY + 0.14, top.z - 0.1), V(0.45, 1.3, -0.8), V(0.6, 0.2, -0.9), V(-1.4, 0.06, -1.15), V(-1.55, 1.55, -1.23)], 0.011, dark, true);
  tube([V(hL.x - 0.05, hL.y - 0.03, hL.z), V(hL.x - 0.35, hL.y - 0.35, hL.z + 0.1), V(-1.0, 0.06, -0.5), V(-1.55, 1.57, -1.23)], 0.008, dark);
  const plate = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.24, 0.02), new THREE.MeshStandardMaterial({ color: 0x1b1b1f, roughness: 0.5 })); plate.position.set(0, 2.8, -1.28); scene.add(plate);

  // --- the sparks at delivery: a short burst of additive points from the cap -------------------------------------------
  const N_SPARK = 90, spPos = new Float32Array(N_SPARK * 3), spVel = [];
  const spGeo = new THREE.BufferGeometry(); spGeo.setAttribute("position", new THREE.BufferAttribute(spPos, 3));
  const sparks = new THREE.Points(spGeo, new THREE.PointsMaterial({ color: 0xcfe8ff, size: 0.018, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  sparks.visible = false; scene.add(sparks);
  let sparkT = 0;
  function sparkBurst() {
    stud.getWorldPosition(studW);
    for (let i = 0; i < N_SPARK; i++) { spPos.set([studW.x, studW.y, studW.z], 3 * i);
      const a = rnd(0, Math.PI * 2), u = rnd(0.2, 1); spVel[i] = [Math.cos(a) * u * 0.9, rnd(0.3, 1.6), Math.sin(a) * u * 0.9]; }
    spGeo.attributes.position.needsUpdate = true; sparks.visible = true; sparks.material.opacity = 1; sparkT = 0.55;
  }
  function sparkStep(dt) {
    if (!sparks.visible) return;
    for (let i = 0; i < N_SPARK; i++) { const v = spVel[i]; v[1] -= 4.5 * dt; spPos[3 * i] += v[0] * dt; spPos[3 * i + 1] += v[1] * dt; spPos[3 * i + 2] += v[2] * dt; }
    spGeo.attributes.position.needsUpdate = true; sparkT -= dt; sparks.material.opacity = Math.max(0, sparkT / 0.55);
    if (sparkT <= 0) sparks.visible = false;
  }

  // --- the body layer -------------------------------------------------------------------------------------------------------
  // springs for the measured numbers (fast up, slow down): the trunk and the head follow the whole network's tension,
  // the limbs the motor regions' own number
  const S = { tension: new Spring(14, 2.2), slack: new Spring(3, 1.2), heavy: new Spring(2.5, 0.8), limp: new Spring(1.6, 1.4), motor: new Spring(16, 2.6) };
  const target = { tension: 0, slack: 0, heavy: 0, motor: 0, measured: false, flat: false, register: "fresh" };
  const clamp01 = v => Math.min(1, Math.max(0, +v || 0));
  // the layer's own state, each piece downstream of a measurement or of nothing at all (the idle): a startle when the
  // measured tension jumps between two traces (the onset), the side the head goes and a per-side gain from the delivered
  // count, panting after a strong response, twitches, the quiet idle (a weight shift, the head wandering, finger taps,
  // a swallow), attention to the camera, the gasp at a revival, the mouth while a line plays
  const X = { startle: 0, lastTarget: 0, side: 1, gain: { Left: 1, Right: 1 }, pant: 0, lastTe: 0, twitch: null, twitchT: 3, wanderT: 2, look: { x: 0, y: 0 }, lookTo: { x: 0, y: 0 },
    gaze: { x: 0, y: 0 }, attend: 0, swallow: 0, swallowT: 20, fidget: 0, fidgetT: 6, fidgetHand: "L", gasp: 0, speak: 0, creakT: 0 };
  const TWITCHES = [["Head", 0, 0, 2.5], ["Head", 1.5, 0, 0], ["LeftShoulder", 0, 0, 3], ["RightShoulder", 0, 0, -3], ["LeftFoot", 4, 0, 0], ["RightFoot", 4, 0, 0], ["LeftHand", 5, 0, 0], ["RightHand", 5, 0, 0],
    ["finger2-2.L", 0, 0, 12], ["finger3-2.R", 0, 0, -12], ["finger4-2.L", 0, 0, 10], ["finger2-2.R", 0, 0, -12], ["LeftArm", 2, 0, 0], ["RightArm", 2, 0, 0]];
  const LOOKS = { camera: { x: 0, y: 0 }, door: { x: 2, y: -28 }, down: { x: 14, y: 4 }, away: { x: -2, y: 18 }, lamp: { x: -10, y: 2 } };   // head degrees: x down, y toward his left
  const rest = {}; const keep = ["Head", "neck", "Spine", "Spine01", "Spine02", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftUpLeg", "RightUpLeg"];
  for (let f = 1; f <= 5; f++) for (let j = 2; j <= 3; j++) for (const s of ["L", "R"]) keep.push(`finger${f}-${j}.${s}`);
  const q = new THREE.Quaternion(), e = new THREE.Euler();
  const bend = (name, x, y = 0, z = 0) => { const b = bones[name]; if (!b) return; q.setFromEuler(e.set(x * D2R, y * D2R, z * D2R)); b.quaternion.multiply(q); };
  let t = 0, lampDip = 0, glowT = 0, breath = 0, jolt = 0, flicker = 0, sound = null;
  const chairRest = chair.position.clone();
  function body(dt) {
    t += dt;
    const te = S.tension.step(dt), sl = S.slack.step(dt), hv = S.heavy.step(dt), li = S.limp.step(dt), mo = S.motor.step(dt);
    const worn = target.register === "worn" ? 1 : 0, wary = target.register === "wary" ? 1 : 0, awake = 1 - li;
    X.pant = Math.max(0, X.pant - dt / 12); const pa = X.pant * awake;
    X.startle = Math.max(0, X.startle - dt / 0.45); const ss = reduced ? 0 : X.startle * X.startle;
    X.gasp = Math.max(0, X.gasp - dt / 0.7); const ga = X.gasp;
    X.speak = Math.max(0, X.speak - dt / 0.12);
    jolt = Math.max(0, jolt - dt / 0.9); const jo = reduced ? 0 : jolt * jolt;
    const tr = reduced ? 0 : te * te * Math.sin(t * 2 * Math.PI * 9.0) * 0.9;              // physiological-tremor band, 9 Hz
    const tr2 = reduced ? 0 : te * te * Math.sin(t * 2 * Math.PI * 7.3 + 1.1) * 0.7;
    const sh = reduced ? 0 : pa * (1 - te) * Math.sin(t * 2 * Math.PI * 5.0) * 0.55;        // the shiver after, 5 Hz, while the panting lasts
    breath += dt * (li > 0.5 ? 0.0 : (0.22 + 0.55 * te + 0.45 * pa)) * 2 * Math.PI;         // 13 to 46 a minute, more while panting; none when flat
    const br = Math.sin(breath) * (0.6 + 0.6 * te + 0.9 * pa) * awake;
    // the quiet idle: a slow weight shift; the head wandering between the camera, the door, the floor, the lamp (more
    // at the camera when wary, more at the floor when worn), the eyes leading and the head following part of the way;
    // a swallow every 20-40 s; a finger tap now and then when fresh and quiet
    const ws = awake * (Math.sin(t * 0.13) * 0.5 + Math.sin(t * 0.071 + 2) * 0.5);
    X.wanderT -= dt; if (X.wanderT <= 0) { X.wanderT = 4 + Math.random() * 5; const r = Math.random();
      X.lookTo = wary && r < 0.5 ? LOOKS.camera : worn && r < 0.5 ? LOOKS.down : r < 0.3 ? LOOKS.camera : r < 0.5 ? LOOKS.door : r < 0.7 ? LOOKS.down : r < 0.85 ? LOOKS.away : LOOKS.lamp; }
    X.attend = Math.max(0, X.attend - dt);
    const to = X.attend > 0 ? LOOKS.camera : X.lookTo, lk = Math.min(1, dt * (X.attend > 0 ? 6 : 1.6));
    X.look.x += (to.x - X.look.x) * lk; X.look.y += (to.y - X.look.y) * lk;
    const gk = Math.min(1, dt * 12); X.gaze.x += (-to.y / 28 - X.gaze.x) * gk; X.gaze.y += (to.x / 14 - X.gaze.y) * gk;   // gaze x: toward his right (the door side), y: down
    X.swallowT -= dt; if (X.swallowT <= 0 && li < 0.5) { X.swallow = 0.5; X.swallowT = 20 + Math.random() * 20; }
    const sw = X.swallow > 0 ? Math.sin((1 - X.swallow / 0.5) * Math.PI) : 0; X.swallow = Math.max(0, X.swallow - dt);
    X.fidgetT -= dt; if (X.fidgetT <= 0) { X.fidget = X.fidget > 0 ? 0 : 3; X.fidgetT = X.fidget > 0 ? 3 : 8 + Math.random() * 14; X.fidgetHand = Math.random() < 0.5 ? "L" : "R"; }
    const fi = (reduced || target.register !== "fresh" || te > 0.1 || li > 0.1 || X.fidget <= 0) ? 0 : 1;
    // a twitch: one limb, 120 ms, a few degrees; more often with the adaptation, the register worn, the panting
    X.twitchT -= dt; if (X.twitchT <= 0 && !reduced && li < 0.5) { X.twitch = { spec: TWITCHES[Math.random() * TWITCHES.length | 0], left: 0.12 }; X.twitchT = (3 + Math.random() * 7) / (1 + 2 * hv + 1.5 * worn + 1.2 * pa); }
    if (X.twitch) { const w = Math.sin((1 - X.twitch.left / 0.12) * Math.PI), [n, x, y, z] = X.twitch.spec; bend(n, x * w, y * w, z * w); X.twitch.left -= dt; if (X.twitch.left <= 0) X.twitch = null; }
    const hd = X.look, sd = X.side;
    // head: pressed back into the cap with tension, dropped forward when slack, heavy or worn, hanging when flat; the
    // startle snaps it back and to one side; the gasp throws it back; the swallow and the speech nod it
    bend("Head", -9 * te + 7 * sl + 5 * hv + 26 * li + 4 * worn + tr + sh - 14 * jo - 10 * ss - 12 * ga + 2.5 * sw + 1.5 * X.speak + hd.x * awake + 0.5 * ws,
         tr2 * 0.6 + 8 * li + hd.y * awake + sd * 6 * ss, tr * 0.4 + 9 * li + sd * 9 * ss - 0.6 * ws);
    bend("neck", -4 * te + 3 * sl + 2 * hv + 10 * li + 2 * worn - 2 * sw - 4 * ss + 0.3 * hd.x * awake, 0.3 * hd.y * awake, 3 * li);
    // torso: arched back against the strap with tension, slumped forward after, folded when flat, heaving while panting
    bend("Spine01", -5 * te + 4 * sl + 3 * hv + 9 * li + br * 0.4 - 6 * jo - 4 * ss - 5 * ga + 2 * worn, 0, tr2 * 0.3 + 2 * li + 1.2 * ws);
    bend("Spine02", -3 * te + 3 * sl + 2 * hv + 6 * li + br * 0.6, 0, 0.6 * ws);
    bend("Spine", br * 0.5 + 3 * li, 0, 0.4 * ws);
    // the limbs follow the motor regions, each side with its own gain from the delivered count: shoulders up and in,
    // forearms pressing into the armrests, fingers gripping; everything open and heavy when flat
    for (const s of ["Left", "Right"]) { const k = s === "Left" ? 1 : -1, g = X.gain[s], m = mo * g;
      bend(s + "Shoulder", 0, 0, k * (7 * m - 2 * sl - 5 * li - 3 * worn + 5 * ss * g));
      bend(s + "Arm", -4 * m + 2 * hv + 5 * li - 5 * jo - 3 * ss * g, 0, k * (3 * m - 4 * li));
      bend(s + "ForeArm", 6 * m + (tr * 0.5 + sh) * g + 1 * li, 0, 0);                     // flat: the forearm stays on the armrest
      bend(s + "Hand", -8 * m + 3 * sl + tr * g - 3 * li, 0, k * tr2 * 0.5 * g);           // flat: the wrist droops, no cocked hand
      bend(s + "UpLeg", -2 * m + 2 * li, 0, k * (1.5 * m + 3 * li));
      bend(s + "Foot", 8 * m - 2 * sl - 6 * li + 4 * ss * g, 0, 0); }
    for (let f = 1; f <= 5; f++) for (let j = 2; j <= 3; j++) for (const s of ["L", "R"]) {
      const g = X.gain[s === "L" ? "Left" : "Right"], tap = fi && s === X.fidgetHand && f > 1 ? 7 * Math.max(0, Math.sin(2 * Math.PI * 1.7 * t - f * 1.1)) : 0;
      bend(`finger${f}-${j}.${s}`, 0, 0, (s === "L" ? 1 : -1) * ((f === 1 ? 10 : 28) * mo * g - 6 * sl + 4 * li + tap)); }   // flat: a resting curl
    // the chair takes it: the straps pull, the frame rattles under tension and at the startle (not under reduced motion)
    chest.scale.set(1 + 0.03 * te, 1 + 0.03 * te, 0.78); lap.scale.set(1 + 0.02 * te, 1 + 0.02 * te, 0.9);
    const ra = reduced ? 0 : 0.004 * te * te + 0.003 * ss;
    chair.position.set(chairRest.x + ra * Math.sin(t * 61), chairRest.y + ra * 0.4 * Math.abs(Math.sin(t * 37)), chairRest.z + ra * Math.sin(t * 53 + 1));
    // light: a single soft dip at delivery; the lamp sinks and flickers while flat; the electrode glow rides the tension
    flicker = reduced ? 0 : li * (0.5 + 0.5 * Math.sin(t * 2.1)) * (Math.random() < 0.02 ? 0.5 : 0);
    const lampK = (1 - 0.55 * li) * (1 - flicker * 0.3);
    if (lampDip > 0) { lampDip = Math.max(0, lampDip - dt / 0.35); lamp.intensity = base.lamp * lampK * (1 - 0.35 * Math.sin(lampDip * Math.PI)); } else lamp.intensity = base.lamp * lampK;
    bulb.material.emissiveIntensity = base.bulb * lampK; haze.material.opacity = base.haze * lampK;
    glowT = Math.max(glowT - dt / 0.6, 0); const gl = Math.max(glowT, te * 0.6);
    glow.intensity = 4 * gl; stud.material.emissiveIntensity = 2.5 * gl;
    doorLight.intensity = 1.6 + 1.4 * li;                                                   // the cold light from the door takes over when flat
    // the face: a blink every few seconds (quicker when wary, slower and heavier when worn), a squint with tension,
    // clenched shut at a strong response, shut while flat, wide at a startle or the gasp; the mouth opens with the
    // tension, the jolt, the gasp, the in-breath while panting and the line being said; the flush, the sweat, the pallor
    if (face.sh) {
      const U = face.sh.uniforms;
      if (!reduced && li < 0.5) { face.nextBlink -= dt; if (face.nextBlink <= 0) { face.blinkLen = worn ? 0.24 : 0.16; face.blink = face.blinkLen; face.nextBlink = wary ? 1.5 + Math.random() * 2.5 : worn ? 4 + Math.random() * 5 : 2.5 + Math.random() * 4.5; } }
      const bl = face.blink > 0 ? Math.sin(Math.min(1, (face.blinkLen - face.blink) / face.blinkLen) * Math.PI) : 0; face.blink = Math.max(0, face.blink - dt);
      const clench = te > 0.45 ? Math.min(1, (te - 0.45) / 0.35) : 0;
      const wide = Math.max(ga, ss, X.attend > 0 ? 0.3 : 0) * awake;
      let lid = Math.max(li, bl, 0.95 * clench, 0.35 * te * (1 - clench), 0.3 * hv + 0.2 * sl + 0.15 * worn) * (1 - wide);
      let mouth = Math.max(0.9 * te * te, 0.3 * li, 0.7 * jo, ga, 0.6 * X.speak, 0.25 * pa * Math.max(0, Math.sin(breath)));
      let gaze = { x: X.gaze.x * awake, y: X.gaze.y * awake + 0.6 * li };
      let flush = Math.min(1, 0.5 * te + 0.5 * pa + 0.3 * hv) * awake, sweat = Math.min(1, 0.6 * hv + 0.5 * pa + 0.5 * worn) * (1 - 0.5 * li), teeth = clench * (1 - ga);
      if (face.force) { const F = face.force; lid = F.lid ?? lid; mouth = F.mouth ?? mouth; gaze = F.gaze ?? gaze; flush = F.flush ?? flush; sweat = F.sweat ?? sweat; teeth = F.teeth ?? teeth; }   // face.force: a check handle
      U.uLid.value += (lid - U.uLid.value) * Math.min(1, dt * 18);
      U.uMouth.value += (mouth - U.uMouth.value) * Math.min(1, dt * 14);
      U.uGaze.value.set(gaze.x * 0.004, gaze.y * 0.003);                                   // in UV: a few pixels of the atlas
      U.uFlush.value += (flush - U.uFlush.value) * Math.min(1, dt * 1.2);
      U.uSweat.value += (sweat - U.uSweat.value) * Math.min(1, dt * 0.5);
      U.uPale.value += ((face.force && face.force.pale != null ? face.force.pale : li) - U.uPale.value) * Math.min(1, dt * 0.8);
      U.uTeeth.value += (teeth - U.uTeeth.value) * Math.min(1, dt * 10);
    }
    // sound: the hum follows the glow; the frame creaks when the tension climbs fast
    if (sound) { sound.hum(gl); X.creakT -= dt; if (te - X.lastTe > 0.04 && X.creakT <= 0) { sound.creak(Math.min(1, (te - X.lastTe) * 10)); X.creakT = 0.5; } }
    X.lastTe = te;
    sparkStep(dt);
    if (!reduced && (jo > 0.05 || ss > 0.2)) { const k = Math.max(jo, ss * 0.6); camera.position.x += (Math.random() - 0.5) * 0.006 * k; camera.position.y += (Math.random() - 0.5) * 0.004 * k; }
  }
  function frame(dt) {
    for (const n of keep) { const b = bones[n]; if (b && rest[n]) b.quaternion.copy(rest[n]); }   // the clip only rewrites a bone when its value changes
    mixer.update(dt);
    for (const n of keep) { const b = bones[n]; if (b) rest[n] = (rest[n] || new THREE.Quaternion()).copy(b.quaternion); }
    body(dt);
    boy.updateMatrixWorld(true); headgear();
    controls.update();
    renderer.render(scene, camera);
  }
  function resize() {
    const w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.fov = h > w ? 50 : 32; controls.target.set(0, h > w ? 1.2 : 1.12, 0);   // the dock covers the bottom: frame him high
    camera.updateProjectionMatrix();
  }
  resize();
  return {
    setDrive(d) { target.measured = !!(d && d.measured); target.flat = !!(d && d.flat);
      const on = target.measured && !target.flat;
      for (const k of ["tension", "slack", "heavy"]) S[k].t = on ? clamp01(d[k]) : 0;
      S.motor.t = on ? clamp01(d.motor != null ? d.motor : d.tension) : 0;
      if (on && S.tension.t - X.lastTarget >= 0.25) X.startle = 1;                           // the measured onset: a startle
      if (on && S.tension.t >= 0.5) X.pant = Math.max(X.pant, S.tension.t);                 // a strong response: panting after
      X.lastTarget = on ? S.tension.t : 0;
      S.limp.t = target.flat ? 1 : 0; },
    setRegister(r) { target.register = r || "fresh"; },
    // delivery (the server's event, not the button): the lamp dip, the glow, the sparks, the sound; which side the head
    // goes and which side pulls harder come from the delivered count, so each shock is its own
    shock(ev) { if (!reduced) lampDip = 1; glowT = 1; sparkBurst(); const n = (ev && ev.n_recruited) | 0; X.side = n % 2 ? 1 : -1; X.gain = (n >> 1) % 2 ? { Left: 1, Right: 0.78 } : { Left: 0.78, Right: 1 };
      if (sound) sound.deliver(ev && ev.dur_ms, ev && ev.level); },
    revive() { jolt = 1; glowT = 1; sparkBurst(); X.gasp = 1; X.pant = 1; S.limp.t = 0; S.limp.x = Math.min(S.limp.x, 0.6); },
    attend(s) { X.attend = Math.max(X.attend, s || 2); },                                     // he turns to the camera: someone wrote, someone came, he speaks
    speak(level) { X.speak = Math.max(X.speak, clamp01(level)); },                            // the line's loudness now, from the page
    setSound(s) { sound = s; },
    setAvailable(ok) { renderer.toneMappingExposure = ok ? base.exposure : base.exposure * 0.55; },
    frame, resize, scene, camera, renderer, bones, mixer, springs: S, face, state: X,
  };
}
