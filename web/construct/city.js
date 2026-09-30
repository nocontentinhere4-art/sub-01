// STUB city (core stream). The city stream replaces this file; keep the exports.
//
// createCity(scene, data, quality) -> {update(dt, env, act), flash(regions, color), setFear(k), object, dispose()}
//   data     loadBrainData() result (web/construct/data.js): districts (city positions, roles), roads (real fibres)
//   act      Float32Array per brain region: activity relative to that region's own running baseline, normalised to the
//            global mean (1 = usual level; > 1 = more active than usual), or null before the first tick
//   env      {romeHour, dayK, night, stage, sleep, quality, market, groups, groupRel, time, view, ...} (see main.js)
//   flash(regions, color)  regions = [brain region indices] (chat.regions) or [group names] (chat.networks)
//   setFear(k)             0..1: the fear district (amygdala + salience) stays dark unless k rises
// This placeholder: one InstancedMesh of towers (height / glow = live activity), the fibre roads as one additive
// LineSegments (pulses leave the more active end, like the /brain page), a dark ground, and labels on the four places.
import * as THREE from "three";

const GROUP_COLOR = {
  default: 0xff8a3d, somatomotor: 0xff6a00, visual: 0xffb070, attention: 0xff9a50, salience: 0xff5a2e, control: 0xffc890,
  limbic: 0xb88cff, memory: 0x8fb4ff, reward: 0xffd23f, fear: 0xff2a1a, relay: 0xfff1e0, other: 0xc0a8d8,
};
const PLACE_LABEL = { home: "home · default network", reward: "bakery · reward", park: "park · memory", fear: "fear · amygdala" };

export function createCity(scene, data, quality) {
  const root = new THREE.Group(); root.name = "city"; scene.add(root);
  const N = data.districts.length, R = data.radius;

  // ---- ground ----
  const ground = new THREE.Mesh(new THREE.CircleGeometry(R * 1.35, 96).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0x07080f }));
  ground.position.y = -0.2; root.add(ground);
  const grid = new THREE.PolarGridHelper(R * 1.3, 24, 14, 96, 0x2a1406, 0x160b05);
  grid.position.y = -0.1; root.add(grid);

  // ---- districts: one instanced tower each ----
  const geo = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
  const shade = new Float32Array(geo.attributes.position.count * 3);        // dark feet, glowing tops
  for (let v = 0; v < geo.attributes.position.count; v++) shade.fill(geo.attributes.position.getY(v) > 0.5 ? 1 : 0.18, v * 3, v * 3 + 3);
  geo.setAttribute("color", new THREE.BufferAttribute(shade, 3));
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, vertexColors: true });
  const towers = new THREE.InstancedMesh(geo, mat, N);
  towers.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  const baseCol = data.districts.map(d => new THREE.Color(GROUP_COLOR[d.group] ?? 0xffa060));
  const foot = data.districts.map(d => (d.role === "home" || d.role === "reward" || d.role === "park" ? 12 : /Thalamus|Pallidum/.test(d.name) ? 9 : 7));
  const level = new Float32Array(N).fill(1), flashK = new Float32Array(N), flashCol = baseCol.map(() => new THREE.Color());
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), c = new THREE.Color();
  for (let i = 0; i < N; i++) towers.setColorAt(i, baseCol[i]);
  root.add(towers);

  // ---- roads: the real fibres ----
  const actData = new Uint8Array(256 * 4);
  const actTex = new THREE.DataTexture(actData, 256, 1, THREE.RGBAFormat); actTex.needsUpdate = true;
  const rg = new THREE.BufferGeometry();
  rg.setAttribute("position", new THREE.BufferAttribute(data.roads.positions, 3));
  rg.setAttribute("ends", new THREE.BufferAttribute(data.roads.pairs, 2));
  rg.setAttribute("tpos", new THREE.BufferAttribute(data.roads.t, 1));
  const roadMat = new THREE.ShaderMaterial({
    uniforms: { act: { value: actTex }, time: { value: 0 }, level: { value: 1 }, opacity: { value: 0.45 * Math.sqrt(2500 / Math.max(1, data.roads.fibres)) },
      tint: { value: new THREE.Color(0xff6a00) } },
    vertexShader: `
      attribute vec2 ends; attribute float tpos;
      uniform sampler2D act; uniform float time; uniform float level; uniform vec3 tint;
      varying vec3 vCol;
      float actAt(float i){ return i < 0.0 ? 0.0 : texture2D(act, vec2((i + 0.5) / 256.0, 0.5)).r * 3.0; }
      void main(){
        float a = actAt(ends.x), b = actAt(ends.y);
        float drive = clamp((max(a, b) - 1.1) / 0.9, 0.0, 1.0);
        float dir = a >= b ? tpos : 1.0 - tpos;
        float wave = pow(0.5 + 0.5 * sin(dir * 18.0 - time * 5.0), 8.0);
        vCol = mix(tint, vec3(1.0, 0.93, 0.85), drive * wave * 0.6) * (0.12 + level * (0.6 + drive * (0.5 + 2.5 * wave)));
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position + vec3(0.0, 0.4, 0.0), 1.0);
      }`,
    fragmentShader: `uniform float opacity; varying vec3 vCol; void main(){ gl_FragColor = vec4(vCol * opacity, 1.0); }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const roads = new THREE.LineSegments(rg, roadMat); roads.frustumCulled = false; root.add(roads);

  // ---- place labels ----
  const labels = [];
  for (const role of ["home", "reward", "park", "fear"]) {
    const i = data.districtOf(role);
    if (i == null) continue;
    const sp = textSprite(PLACE_LABEL[role]);
    sp.position.copy(data.districts[i].pos).add(new THREE.Vector3(0, 70, 0));
    // fade out a label when the camera is close to its district (first person at home: keeps it off the HUD text)
    const L = { sp, i, role, base: 0.9 };
    sp.onBeforeRender = (r, sc, cam) => {
      const d = cam.position.distanceTo(sp.position);
      sp.material.opacity = L.base * THREE.MathUtils.smoothstep(d, 160, 340);
    };
    root.add(sp); labels.push(L);
  }

  let fear = 0, t = 0;
  function setFear(k) { fear = Math.max(0, Math.min(1, +k || 0)); }

  function update(dt, env, act) {
    t += dt;
    const stage = env?.stage || "AWAKE";
    const sleepK = stage === "NREM" ? 0.3 : stage === "REM" ? 0.55 : 1;
    const dayK = env?.dayK ?? 1;
    const lvl = sleepK * (0.55 + 0.45 * Math.max(dayK, env?.night ? 0 : 0.5));
    roadMat.uniforms.time.value = t;
    roadMat.uniforms.level.value = sleepK * (env?.night ? 0.75 : 1);
    const k = 1 - Math.exp(-dt * 3);
    for (let i = 0; i < N; i++) {
      const a = act ? Math.min(3, act[i] || 0) : 1;
      level[i] += (a - level[i]) * k;
      if (act) actData[i * 4] = Math.min(255, Math.round(a / 3 * 255));
      const d = data.districts[i];
      // fear district: dark unless fear rises; salience: dim at rest, fully lit from fear 0.4 (continuous)
      const dark = d.role === "fear" ? 0.12 + 0.88 * fear : d.role === "salience" ? Math.min(1, 0.12 + 2.2 * fear) : 1;
      const up = Math.max(0, level[i] - 0.6);
      const h = (6 + 40 * up + (d.role === "home" && d.cluster === 0 ? 14 : 0)) * (0.6 + 0.4 * sleepK);
      s.set(foot[i], h, foot[i]);
      m4.compose(p.copy(d.pos), q, s);
      towers.setMatrixAt(i, m4);
      c.copy(baseCol[i]).multiplyScalar((0.25 + 0.9 * Math.min(1.6, up)) * lvl * dark);
      if (flashK[i] > 0) { c.lerp(flashCol[i], flashK[i]); flashK[i] = Math.max(0, flashK[i] - dt * 0.5); }
      towers.setColorAt(i, c);
    }
    if (act) actTex.needsUpdate = true;
    towers.instanceMatrix.needsUpdate = true;
    towers.instanceColor.needsUpdate = true;
    for (const L of labels) L.base = (L.role === "fear" ? 0.25 + 0.75 * fear : 0.9) * (0.5 + 0.5 * sleepK);
  }

  const groupIdx = {};
  data.districts.forEach(d => (groupIdx[d.group] ||= []).push(d.i));
  function flash(regions, color = 0xff6a00) {
    if (!regions) return;
    const list = Array.isArray(regions) ? regions : Object.keys(regions);
    for (const r of list) for (const i of (typeof r === "number" ? [r] : groupIdx[r] || [])) {
      if (i >= 0 && i < N) { flashK[i] = 1; flashCol[i].set(color).multiplyScalar(1.6); }
    }
  }

  function dispose() {
    scene.remove(root);
    root.traverse(o => { o.geometry?.dispose(); if (o.material) { o.material.map?.dispose(); o.material.dispose(); } });
    actTex.dispose();
  }

  update(0, {}, null);
  return { update, flash, setFear, object: root, dispose };
}


function textSprite(text) {
  const cv = document.createElement("canvas"), x = cv.getContext("2d");
  const fs = 44; x.font = `${fs}px ui-monospace, Menlo, monospace`;
  cv.width = Math.ceil(x.measureText(text).width) + 40; cv.height = fs + 30;
  x.font = `${fs}px ui-monospace, Menlo, monospace`;
  x.fillStyle = "rgba(5,6,12,0.7)"; x.fillRect(0, 0, cv.width, cv.height);
  x.strokeStyle = "#ff6a00"; x.lineWidth = 3; x.strokeRect(1.5, 1.5, cv.width - 3, cv.height - 3);
  x.fillStyle = "#ffe6cc"; x.textBaseline = "middle"; x.fillText(text, 20, cv.height / 2 + 2);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false, toneMapped: false, sizeAttenuation: false, fog: false }));
  const h = 0.045; sp.scale.set(h * cv.width / cv.height, h, 1);
  sp.renderOrder = 10;
  return sp;
}
