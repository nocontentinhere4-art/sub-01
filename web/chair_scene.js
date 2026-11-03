// SUB-01 · the chair scene (web/chair.html): the character seated in a tall wooden chair, head clamp, straps and
// cables, under one warm lamp against a block wall, after the reference image. His body moves from three measured
// numbers (chair.py Drive: tension, slack, heavy), never from the button: the only thing that follows the button is
// the lamp dip at delivery. The procedural layer is additive on the seated clip and bounded by the restraints (the
// head stays in the clamp, the wrists on the armrests, the torso against the strap), with springs for the body's own
// inertia. Artistic mappings of simulated signals, not physiology.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { prep, fixClip } from "./room/char_mixamo.js";

const D2R = Math.PI / 180;
const WOOD = 0x4a2e1a, WOOD2 = 0x5c3a22, LEATHER = 0x1b1512, METAL = 0x8c8c8c, DARK = 0x2a2a2a;

// a spring that follows its target faster up than down: the body tenses at once and lets go slowly
class Spring {
  constructor(up = 10, down = 2) { this.x = 0; this.v = 0; this.t = 0; this.up = up; this.down = down; }
  step(dt) { const k = this.t > this.x ? this.up : this.down, a = k * k * (this.t - this.x) - 2 * k * this.v; this.v += a * dt; this.x += this.v * dt; return this.x; }
}

function blockWall(w = 6, h = 3.2) {
  const c = document.createElement("canvas"); c.width = 1024; c.height = 512; const g = c.getContext("2d");
  g.fillStyle = "#8a7a52"; g.fillRect(0, 0, c.width, c.height);
  const bw = 1024 / 12, bh = 512 / 12;
  for (let r = 0; r < 12; r++) for (let i = -1; i < 13; i++) {
    const x = i * bw + (r % 2 ? bw / 2 : 0), y = r * bh, n = Math.random();
    g.fillStyle = `rgb(${150 + n * 40 | 0},${132 + n * 36 | 0},${88 + n * 30 | 0})`;
    g.fillRect(x + 3, y + 3, bw - 6, bh - 6);
    g.fillStyle = "rgba(0,0,0,.12)"; for (let k = 0; k < 14; k++) g.fillRect(x + 4 + Math.random() * (bw - 10), y + 4 + Math.random() * (bh - 10), 2 + Math.random() * 5, 1 + Math.random() * 2);
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(w / 4.8, h / 2.4); t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.95, metalness: 0 });
}

function woodGrain(base = "#4a2e1a") {
  const c = document.createElement("canvas"); c.width = 256; c.height = 256; const g = c.getContext("2d");
  g.fillStyle = base; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 90; i++) { g.strokeStyle = `rgba(${i % 2 ? 20 : 120},${i % 2 ? 10 : 70},${i % 2 ? 5 : 35},${0.08 + Math.random() * 0.12})`; g.lineWidth = 1 + Math.random() * 2;
    g.beginPath(); const y = Math.random() * 256; g.moveTo(0, y); g.bezierCurveTo(80, y + (Math.random() - 0.5) * 20, 170, y + (Math.random() - 0.5) * 20, 256, y); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.7, metalness: 0.05 });
}

export async function createScene({ canvas, lite = false, small = false, reduced = false, onProgress = () => {} }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !lite, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lite ? 1 : 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = !lite && !small; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x050505);
  const scene = new THREE.Scene(); scene.fog = new THREE.Fog(0x050505, 6, 12);
  const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 40); camera.position.set(0, 1.25, 3.6);
  const controls = new OrbitControls(camera, canvas); controls.target.set(0, 1.12, 0); controls.enablePan = false; controls.enableDamping = true;
  controls.minDistance = 2.2; controls.maxDistance = 4.6; controls.minPolarAngle = 1.15; controls.maxPolarAngle = 1.72; controls.minAzimuthAngle = -0.7; controls.maxAzimuthAngle = 0.7;
  controls.rotateSpeed = 0.5; controls.update();

  // --- the room: a block wall, a concrete floor, one warm lamp ------------------------------------------------------
  const wallMat = blockWall();
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(7, 3.4), wallMat); wall.position.set(0, 1.7, -1.1); wall.receiveShadow = true; scene.add(wall);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(10, 8), new THREE.MeshStandardMaterial({ color: 0x3a3630, roughness: 0.9 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
  scene.add(new THREE.HemisphereLight(0x6a5a3a, 0x0a0806, 0.22));
  const lamp = new THREE.SpotLight(0xffd79a, 38, 9, 0.62, 0.55, 1.6); lamp.position.set(0.35, 3.1, 1.9); lamp.target.position.set(0, 0.9, 0);
  lamp.castShadow = renderer.shadowMap.enabled; lamp.shadow.mapSize.set(1024, 1024); lamp.shadow.bias = -0.0004; lamp.shadow.radius = 3; scene.add(lamp, lamp.target);
  const rim = new THREE.DirectionalLight(0x6f86b0, 0.5); rim.position.set(-1.5, 2.2, -1.5); scene.add(rim);
  const fill = new THREE.PointLight(0xffe2b0, 2.4, 5, 2); fill.position.set(-1.2, 1.2, 1.4); scene.add(fill);
  const glow = new THREE.PointLight(0xbfe0ff, 0, 1.2, 2); scene.add(glow);                   // the electrode glow at delivery
  const base = { lamp: lamp.intensity, exposure: renderer.toneMappingExposure };

  // --- the character and his seated clip ----------------------------------------------------------------------------
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  const load = url => new Promise((ok, no) => loader.load(url, ok, e => onProgress(url, e), no));
  onProgress("character", null);
  const [g, cg] = await Promise.all([load("room/char_mixamo.glb"), load("room/mh_mx/room_seated_idle.glb")]);
  const conv = prep(THREE, g);
  const boy = g.scene; scene.add(boy);
  const bones = {};
  boy.traverse(o => {
    if (o.isMesh) { o.frustumCulled = false; o.castShadow = true; o.receiveShadow = true; const m = o.material; if (m) { m.emissive && m.emissive.setRGB(0, 0, 0); m.roughness = 0.8; m.envMapIntensity = 0.3; } }
    if (o.isBone) bones[o.name] = o;
  });
  const mixer = new THREE.AnimationMixer(boy);
  const clip = fixClip(THREE, cg.animations[0], conv);
  const PB = THREE.PropertyBinding; clip.tracks = clip.tracks.filter(t => PB.findNode(boy, PB.parseTrackName(t.name).nodeName));
  const action = mixer.clipAction(clip); action.play();
  mixer.update(0.01); boy.updateMatrixWorld(true);
  const wp = b => bones[b] ? bones[b].getWorldPosition(new THREE.Vector3()) : null;

  // --- the chair, built round the pose: seat under the hips, armrests under the hands, clamp round the head -----------
  const chair = new THREE.Group(); scene.add(chair);
  const hips = wp("Hips"), knL = wp("LeftLeg"), knR = wp("RightLeg"), hL = wp("LeftHand"), hR = wp("RightHand"), head = wp("Head"), top = wp("head_end") || head.clone().add(new THREE.Vector3(0, 0.12, 0));
  const spine = wp("Spine"), fL = wp("LeftFoot"), fR = wp("RightFoot");
  // he faces +z (the camera); the hips bone sits ~0.23 m above the seat on this rig (the room's seat is 0.505 m under
  // hips at 0.739); the seat runs from behind the hips to just short of the knees, the back posts stand behind it
  const seatY = hips.y - 0.23, seatZ0 = hips.z - 0.16, seatZ1 = Math.max(knL.z, knR.z) - 0.03, seatD = Math.max(0.42, seatZ1 - seatZ0), seatW = 0.62;
  const wood = woodGrain(), wood2 = woodGrain("#5c3a22"), leather = new THREE.MeshStandardMaterial({ color: LEATHER, roughness: 0.55, metalness: 0.05 });
  const metal = new THREE.MeshStandardMaterial({ color: METAL, roughness: 0.35, metalness: 0.85 }), dark = new THREE.MeshStandardMaterial({ color: DARK, roughness: 0.6, metalness: 0.4 });
  const box = (w, h, d, mat, x, y, z, rx = 0, ry = 0, rz = 0) => { const m = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, 0.008), mat); m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.castShadow = m.receiveShadow = true; chair.add(m); return m; };
  const cz = (seatZ0 + seatZ1) / 2;
  box(seatW, 0.05, seatD, wood, 0, seatY, cz);                                                   // the seat
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) box(0.06, seatY, 0.06, wood2, sx * (seatW / 2 - 0.04), seatY / 2, cz + sz * (seatD / 2 - 0.04));   // legs
  const backZ = seatZ0 - 0.02, backH = 2.05;
  for (const sx of [-1, 1]) box(0.07, backH, 0.07, wood2, sx * (seatW / 2 - 0.035), backH / 2, backZ);     // the tall back posts
  for (const y of [seatY + 0.35, seatY + 0.75, backH - 0.08]) box(seatW, 0.08, 0.05, wood, 0, y, backZ);  // crossbars
  box(seatW - 0.14, 0.6, 0.03, wood, 0, seatY + 0.42, backZ + 0.015);                                       // the back board
  for (const [h, sx] of [[hL, -1], [hR, 1]]) {                                                              // armrests under the hands
    const ay = h.y - 0.035, az = h.z;
    box(0.11, 0.045, 0.5, wood, sx * (seatW / 2 - 0.02), ay, az + 0.05);
    box(0.05, ay - seatY, 0.05, wood2, sx * (seatW / 2 - 0.02), (ay + seatY) / 2, az + 0.22);
    const strap = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.012, 8, 20, Math.PI), leather); strap.position.set(h.x, ay + 0.03, az); strap.rotation.set(0, Math.PI / 2, 0); strap.castShadow = true; chair.add(strap);
    const buckle = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.012, 0.02), metal); buckle.position.set(h.x + sx * 0.05, ay + 0.03, az); chair.add(buckle);
  }
  const chest = new THREE.Mesh(new THREE.TorusGeometry(0.21, 0.016, 8, 36, Math.PI), leather);             // the chest strap, over the front of the torso
  chest.position.set(spine.x, spine.y + 0.02, spine.z - 0.02); chest.rotation.set(Math.PI / 2, 0, 0); chest.scale.set(1, 1, 0.75); chest.castShadow = true; chair.add(chest);
  const cb = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.03, 0.012), metal); cb.position.set(spine.x, spine.y + 0.02, spine.z + 0.16); chair.add(cb);
  for (const f of [fL, fR]) { const s = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.012, 8, 20), leather); s.position.set(f.x, f.y + 0.08, f.z - 0.04); s.rotation.y = Math.PI / 2; s.scale.set(1, 1.2, 1); chair.add(s); }   // ankle straps
  // the head clamp: a band round the forehead, two brackets up to the top crossbar, a cap with the electrode, cables
  const clamp = new THREE.Group(); chair.add(clamp);
  const band = new THREE.Mesh(new THREE.TorusGeometry(0.115, 0.012, 8, 40), dark); band.position.set(head.x, head.y + 0.08, head.z + 0.01); band.rotation.x = Math.PI / 2; band.scale.set(1, 1, 1.15); band.castShadow = true; clamp.add(band);
  for (const sx of [-1, 1]) { const br = new THREE.Mesh(new THREE.BoxGeometry(0.025, backH - 0.08 - (head.y + 0.08), 0.03), dark); br.position.set(head.x + sx * 0.125, (head.y + 0.08 + backH - 0.08) / 2, head.z + 0.01); br.castShadow = true; clamp.add(br);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.02, 0.03), dark); arm.position.set(head.x + sx * 0.19, head.y + 0.1, head.z + 0.01); arm.rotation.z = sx * 0.6; clamp.add(arm); }
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.085, 0.05, 20), metal); cap.position.set(top.x, top.y + 0.015, top.z); cap.castShadow = true; clamp.add(cap);
  const stud = new THREE.Mesh(new THREE.SphereGeometry(0.02, 12, 10), new THREE.MeshStandardMaterial({ color: 0x9fd3ff, emissive: 0x3a7fc0, emissiveIntensity: 0.0, roughness: 0.3, metalness: 0.6 }));
  stud.position.set(top.x, top.y + 0.045, top.z); clamp.add(stud); glow.position.copy(stud.position).add(new THREE.Vector3(0, 0.05, 0.05));
  const tube = (pts, r, mat) => { const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, r, 7, false), mat); m.castShadow = true; chair.add(m); return m; };
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const junction = box(0.16, 0.22, 0.06, dark, -1.35, 1.75, -1.07);
  tube([V(top.x, top.y + 0.045, top.z), V(top.x - 0.1, top.y + 0.25, top.z - 0.1), V(-0.6, 2.25, -0.5), V(-1.3, 2.1, -1.0), V(-1.35, 1.87, -1.04)], 0.012, dark);
  tube([V(top.x + 0.03, top.y + 0.04, top.z + 0.02), V(top.x + 0.22, top.y + 0.1, top.z - 0.08), V(0.4, 1.3, -0.65), V(0.55, 0.25, -0.75), V(-1.3, 0.05, -1.0), V(-1.35, 1.6, -1.04)], 0.011, dark);
  tube([V(hL.x - 0.05, hL.y - 0.02, hL.z), V(hL.x - 0.3, hL.y - 0.3, hL.z + 0.1), V(-0.9, 0.08, -0.4), V(-1.35, 1.62, -1.05)], 0.008, dark);
  const plate = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.22, 0.02), new THREE.MeshStandardMaterial({ color: 0x1e1e22, roughness: 0.5 })); plate.position.set(0, 2.75, -1.08); scene.add(plate);

  // --- the body layer -------------------------------------------------------------------------------------------------
  const S = { tension: new Spring(14, 2.2), slack: new Spring(3, 1.2), heavy: new Spring(2.5, 0.8) };
  const target = { tension: 0, slack: 0, heavy: 0, measured: false };
  const rest = {}; const keep = ["Head", "neck", "Spine", "Spine01", "Spine02", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftUpLeg", "RightUpLeg"];
  for (let f = 1; f <= 5; f++) for (let j = 2; j <= 3; j++) for (const s of ["L", "R"]) keep.push(`finger${f}-${j}.${s}`);
  const q = new THREE.Quaternion(), e = new THREE.Euler();
  const bend = (name, x, y = 0, z = 0) => { const b = bones[name]; if (!b) return; q.setFromEuler(e.set(x * D2R, y * D2R, z * D2R)); b.quaternion.multiply(q); };
  let t = 0, lampDip = 0, glowT = 0, breath = 0;
  function body(dt) {
    t += dt;
    const te = S.tension.step(dt), sl = S.slack.step(dt), hv = S.heavy.step(dt);
    const tr = reduced ? 0 : te * te * Math.sin(t * 2 * Math.PI * 9.0) * 0.9;              // physiological-tremor band, 9 Hz
    const tr2 = reduced ? 0 : te * te * Math.sin(t * 2 * Math.PI * 7.3 + 1.1) * 0.7;
    breath += dt * (0.22 + 0.55 * te) * 2 * Math.PI;                                       // 13 to 46 breaths a minute
    const br = Math.sin(breath) * (0.6 + 0.6 * te);
    // head: pressed back into the clamp with tension, dropped forward when slack or heavy; a tremor under tension
    bend("Head", -9 * te + 7 * sl + 5 * hv + tr, tr2 * 0.6, tr * 0.4);
    bend("neck", -4 * te + 3 * sl + 2 * hv, 0, 0);
    // torso: arched back against the strap with tension, slumped forward after
    bend("Spine01", -5 * te + 4 * sl + 3 * hv + br * 0.4, 0, tr2 * 0.3);
    bend("Spine02", -3 * te + 3 * sl + 2 * hv + br * 0.6, 0, 0);
    bend("Spine", br * 0.5, 0, 0);
    // shoulders up and in, forearms pressing into the armrests, fingers gripping
    for (const s of ["Left", "Right"]) { const k = s === "Left" ? 1 : -1;
      bend(s + "Shoulder", 0, 0, k * (7 * te - 2 * sl));
      bend(s + "Arm", -4 * te + 2 * hv, 0, k * 3 * te);
      bend(s + "ForeArm", 6 * te + tr * 0.5, 0, 0);
      bend(s + "Hand", -8 * te + 3 * sl + tr, 0, k * tr2 * 0.5);
      bend(s + "UpLeg", -2 * te, 0, k * 1.5 * te);
      bend(s + "Foot", 8 * te - 2 * sl, 0, 0); }
    for (let f = 1; f <= 5; f++) for (let j = 2; j <= 3; j++) for (const s of ["L", "R"]) bend(`finger${f}-${j}.${s}`, 0, 0, (s === "L" ? 1 : -1) * (f === 1 ? 10 : 28) * te - (s === "L" ? 1 : -1) * 6 * sl);
    // the chair takes it: the straps pull, the clamp band tightens a touch
    chest.scale.set(1 + 0.03 * te, 1 + 0.03 * te, 0.75); band.scale.set(1 - 0.03 * te, 1, 1.15 - 0.03 * te);
    // light: a single soft dip at delivery (none under reduced motion); the electrode glow rides the measured tension
    if (lampDip > 0) { lampDip = Math.max(0, lampDip - dt / 0.35); lamp.intensity = base.lamp * (1 - 0.35 * Math.sin(lampDip * Math.PI)); } else lamp.intensity = base.lamp;
    glowT = Math.max(glowT - dt / 0.6, 0); const gl = Math.max(glowT, te * 0.6);
    glow.intensity = 4 * gl; stud.material.emissiveIntensity = 2.5 * gl;
  }
  function frame(dt) {
    for (const n of keep) { const b = bones[n]; if (b && rest[n]) b.quaternion.copy(rest[n]); }   // the clip only rewrites a bone when its value changes
    mixer.update(dt);
    for (const n of keep) { const b = bones[n]; if (b) rest[n] = (rest[n] || new THREE.Quaternion()).copy(b.quaternion); }
    body(dt);
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
    setDrive(d) { target.measured = !!(d && d.measured); for (const k of ["tension", "slack", "heavy"]) { S[k].t = target.measured ? Math.min(1, Math.max(0, d[k] || 0)) : 0; } },
    shock() { if (!reduced) lampDip = 1; glowT = 1; },
    setAvailable(ok) { renderer.toneMappingExposure = ok ? base.exposure : base.exposure * 0.55; },
    frame, resize, scene, camera, renderer, bones, mixer, springs: S,
  };
}
