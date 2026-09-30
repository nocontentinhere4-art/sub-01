// The construct's city (city stream): SUB-01's 214 atlas regions as districts, its real fibres as light roads.
//
// STYLE NOTE (the look of the construct - keep it when touching fx / travel / hud)
//   Ground & sky   dark blue-black (#05060c .. #0b1020): the city floats on a near-black plane with a faint grid and
//                  terraced district plinths; the sky is a deep gradient with a dusty warm horizon by day, near black
//                  with a few stars at night. Nothing is green, nothing "rains code": this is our own construct.
//   Light          one family: orange / neon #ff6a00, amber #ff8a3d, gold #ffd23f, warm whites (#fff1e0) for windows and
//                  pulses. Cool accents are rare and meaningful: teal (#5fd8c8) marks the park (limbic / memory),
//                  violet-blue (#8fb4ff) marks the memory / relay regions. Red (#ff2a1a) exists only for fear.
//   Activity       a district is a cluster of towers. Live activity (tick.act vs the region's own baseline) drives the
//                  tower height (short and dim = quiet, tall and glowing = active), the fraction of lit windows and the
//                  glow of the roofs; the roads carry light pulses that leave the more active end of each bundle and get
//                  brighter when either end is above its usual level. A chat flash is a short white-orange bloom of the
//                  hit districts and their roads.
//   Roles          home (default network) warm amber, wide and cosy; the bakery / food district (reward: accumbens,
//                  caudate, putamen) golden with a tall landmark; the park (hippocampus / memory / limbic) calm teal,
//                  lower and quieter; the fear district (amygdala + salience) unlit, almost black, until fear rises -
//                  then it flickers red. Four small labels name them. Night: darker sky, brighter windows, lit roads.
//                  NREM: everything dims and slows; REM: the towers sway. Lab (env.lab): cold blue-white diagnostic.
//
// createCity(scene, data, quality) -> {update(dt, env, act), flash(regions, color), setFear(k), object, dispose(), stats}
//   data     loadBrainData() result (data.js): districts (city positions, roles), roads (real fibres), graph
//   act      Float32Array per brain region: activity relative to that region's own running baseline, normalised to the
//            global mean (1 = usual level; > 1 = more active than usual), or null before the first tick
//   env      {romeHour, dayK, night, stage, lab, sleep, quality, market, groups, groupRel, time, view, ...} (main.js)
//   flash(regions, color)  regions = [brain region indices] (chat.regions) or [group names] (chat.networks)
//   setFear(k)             0..1 (main.js: groups.fear / groups.salience above their usual level)
// Rendering: one InstancedMesh for every tower and plinth of the city (per-instance attributes, per-district live state
// in a 256x2 RGBA texture: level / flash / dark + flash colour), one additive LineSegments for the roads, one ground
// disc, one sky dome, four label sprites + one LineSegments of label pins. Per frame the JS touches only the 214
// districts; heights, windows, pulses and flashes are computed in the shaders. It is a model of brain activity, not a mind.
import * as THREE from "three";

const GROUP_COLOR = {
  default: 0xffa060, somatomotor: 0xff6a00, visual: 0xffb070, attention: 0xff9a50, salience: 0xc8402a, control: 0xffc890,
  limbic: 0x7fc8c0, memory: 0x8fb4ff, reward: 0xffd23f, fear: 0x4a1210, relay: 0xfff1e0, other: 0xc0a8d8,
};
const ROLE_COLOR = { home: 0xffb060, reward: 0xffc63a, park: 0x5fd8c8, fear: 0x3a0e0c, salience: 0xc8402a };
const PLACE_LABEL = { home: "home · default network", reward: "food · reward", park: "park · memory", fear: "fear · amygdala" };
const ROLE_LABEL_COLOR = { home: "#ffb060", reward: "#ffd23f", park: "#5fd8c8", fear: "#ff2a1a" };
// towers per district (min .. max by connectivity; role districts get the max + 2) per quality
const DENSITY = { low: [3, 6], medium: [5, 10], high: [7, 14] };
const PLINTH = 22, CLUSTER_R = 10.5, GROUND_Y = -0.6, TEX_W = 256;
const H_MIN = 6, H_RANGE = 46;

// Fog for the construct's own shaders: the scene fog (main.js) at a lower density so the overview still reads;
// opaque surfaces fade to the fog colour, additive lines fade to black (FOG_ADD).
const FOG_GLSL = `
  #ifdef USE_FOG
    #ifdef FOG_EXP2
      float fogK = 1.0 - exp(-fogDensity * fogDensity * vFogDepth * vFogDepth * 0.3);
    #else
      float fogK = smoothstep(fogNear, fogFar, vFogDepth);
    #endif
  #else
    float fogK = 0.0;
  #endif`;
const FOG_MIX = FOG_GLSL + `\n  gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor, fogK);`;
const FOG_ADD = FOG_GLSL + `\n  gl_FragColor.rgb *= 1.0 - fogK;`;

export function createCity(scene, data, quality) {
  const root = new THREE.Group(); root.name = "city"; scene.add(root);
  const N = data.districts.length, R = data.radius;
  const qn = quality?.name in DENSITY ? quality.name : "medium";
  const disposables = [];

  // ---------------- live per-district state (texture) ----------------
  // row 0: r = level (0..3), g = flash (0..1), b = dark (0..1); row 1: flash colour
  const state = new Uint8Array(TEX_W * 2 * 4);
  const stateTex = new THREE.DataTexture(state, TEX_W, 2, THREE.RGBAFormat);
  stateTex.minFilter = stateTex.magFilter = THREE.NearestFilter; stateTex.needsUpdate = true;
  disposables.push(stateTex);
  const level = new Float32Array(N).fill(1), flashK = new Float32Array(N);
  for (let i = 0; i < N; i++) { state[i * 4] = 85; state[i * 4 + 2] = 255; state[i * 4 + 3] = 255; }

  // ---------------- sky dome ----------------
  const sky = new THREE.Mesh(new THREE.SphereGeometry(2800, 24, 12), new THREE.ShaderMaterial({
    uniforms: { uNight: { value: 0 }, uLab: { value: 0 }, uSleep: { value: 1 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform float uNight, uLab, uSleep; varying vec3 vDir;
      float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      void main(){
        float h = clamp(vDir.y, -0.2, 1.0);
        vec3 zenD = vec3(0.030, 0.040, 0.090), horD = vec3(0.14, 0.065, 0.038);
        vec3 zenN = vec3(0.008, 0.010, 0.022), horN = vec3(0.055, 0.028, 0.030);
        vec3 zen = mix(zenD, zenN, uNight), hor = mix(horD, horN, uNight);
        vec3 c = mix(hor, zen, pow(smoothstep(-0.05, 0.55, h), 0.7));
        c += vec3(0.10, 0.045, 0.01) * (1.0 - uNight) * exp(-abs(h - 0.04) * 22.0);   // a thin warm band on the day horizon
        vec2 s = floor(vDir.xz / max(0.02, vDir.y) * 60.0);
        float star = step(0.9965, hash(s)) * smoothstep(0.02, 0.2, vDir.y) * uNight;
        c += star * vec3(0.9, 0.85, 0.8) * 0.8;
        c = mix(c, vec3(0.03, 0.05, 0.08) + 0.12 * vec3(0.5, 0.7, 0.9) * (1.0 - h), uLab);
        gl_FragColor = vec4(c * (0.35 + 0.65 * uSleep), 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    side: THREE.BackSide, depthWrite: false, fog: false,
  }));
  sky.renderOrder = -10; sky.frustumCulled = false; root.add(sky);
  disposables.push(sky.geometry, sky.material);

  // ---------------- ground: dark disc with a faint grid ----------------
  const ground = new THREE.Mesh(new THREE.CircleGeometry(R * 3.5, 96).rotateX(-Math.PI / 2), new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { uNight: { value: 0 }, uLab: { value: 0 }, uLevel: { value: 1 }, uR: { value: R } }]),
    vertexShader: `
      varying vec2 vXZ;
      #include <fog_pars_vertex>
      void main(){
        vXZ = position.xz;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: `
      uniform float uNight, uLab, uLevel, uR; varying vec2 vXZ;
      #include <fog_pars_fragment>
      float gridLine(vec2 p, float s){ vec2 g = abs(fract(p / s - 0.5) - 0.5) / fwidth(p / s); return 1.0 - clamp(min(g.x, g.y), 0.0, 1.0); }
      void main(){
        float r = length(vXZ) / uR;
        vec3 base = mix(vec3(0.012, 0.014, 0.03), vec3(0.006, 0.007, 0.014), uNight);
        vec3 line = mix(vec3(1.0, 0.42, 0.0), vec3(0.45, 0.7, 0.9), uLab);
        float g = gridLine(vXZ, 25.0) * 0.03 + gridLine(vXZ, 125.0) * 0.055;
        float fade = 1.0 - smoothstep(0.9, 1.7, r);
        vec3 c = mix(base, vec3(0.02, 0.03, 0.05), uLab) + line * g * fade * (0.6 + 0.4 * uNight) * uLevel;
        gl_FragColor = vec4(c, 1.0);
        ${FOG_MIX}
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    fog: true,
  }));
  ground.position.y = GROUND_Y; root.add(ground);
  disposables.push(ground.geometry, ground.material);

  // ---------------- districts: towers + plinths, one InstancedMesh ----------------
  const degree = data.districts.map(d => (data.graph?.adj?.[d.i] || []).reduce((s, e) => s + (data.graph.edges[e.e]?.count || 0), 0));
  const degSorted = degree.slice().sort((a, b) => a - b);
  const degLo = degSorted[Math.floor(N * 0.1)] || 0, degHi = degSorted[Math.floor(N * 0.9)] || 1;
  const [nMin, nMax] = DENSITY[qn];
  const layout = [];                                             // {i, x, z, y0, sx, sy, sz, hmul, kind, tint, win, seed}
  const tmpC = new THREE.Color();
  for (const d of data.districts) {
    const i = d.i, rnd = mulberry(i * 7919 + 17);
    const role = d.role, main = !!role && data.districtOf(role) === i;
    const conn = Math.max(0, Math.min(1, (degree[i] - degLo) / Math.max(1, degHi - degLo)));
    let n = Math.round(nMin + (nMax - nMin) * conn);
    if (role === "home" || main) n = nMax + 2;
    const tint = tmpC.set(role ? ROLE_COLOR[role] : (GROUP_COLOR[d.group] ?? 0xffa060));
    if (!role) tint.offsetHSL((rnd() - 0.5) * 0.02, 0, (rnd() - 0.5) * 0.1);
    const win = role === "park" ? 0.45 : role === "fear" ? 0.6 : role === "home" ? 1.25 : 1;
    const hRole = role === "park" ? 0.62 : role === "home" ? 0.85 : 1;
    // plinth (terrace): from the ground up to the district level
    layout.push({ i, x: d.pos.x, z: d.pos.z, y0: GROUND_Y, sx: PLINTH, sy: d.pos.y - GROUND_Y + 0.25, sz: PLINTH, hmul: 1, kind: 1,
      tint: tint.clone(), win: 0, seed: rnd() });
    const placed = [];
    const rMax = CLUSTER_R + (main ? 1.5 : 0);
    for (let k = 0; k < n; k++) {
      let best = null;
      for (let tries = 0; tries < 40 && !best; tries++) {
        const centre = k === 0;
        const ang = rnd() * Math.PI * 2, rad = centre ? 0 : Math.sqrt(rnd()) * rMax;
        const x = Math.cos(ang) * rad, z = Math.sin(ang) * rad;
        const f = centre ? (main ? 6.5 : 5 + rnd() * 1.5) : 2.4 + rnd() * 3.2;
        const sx = f * (0.8 + rnd() * 0.5), sz = f * (0.8 + rnd() * 0.5);
        if (Math.abs(x) + sx / 2 > rMax + 2 || Math.abs(z) + sz / 2 > rMax + 2) continue;
        if (placed.some(p => Math.abs(p.x - x) < (p.sx + sx) / 2 + 0.8 && Math.abs(p.z - z) < (p.sz + sz) / 2 + 0.8)) continue;
        best = { x, z, sx, sz, rad };
      }
      if (!best) continue;
      placed.push(best);
      const falloff = 1 - 0.45 * best.rad / rMax;
      const hmul = (k === 0 ? (main ? 1.7 : 1.25) : 0.4 + rnd() * 0.7) * falloff * hRole;
      layout.push({ i, x: d.pos.x + best.x, z: d.pos.z + best.z, y0: d.pos.y, sx: best.sx, sy: 1, sz: best.sz, hmul, kind: 0,
        tint: tint.clone(), win, seed: rnd() });
    }
  }
  const M = layout.length;
  const geo = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
  const aInfo = new Float32Array(M * 4), aTint = new Float32Array(M * 3), aWin = new Float32Array(M);
  const towerMat = new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uState: { value: stateTex }, uTime: { value: 0 }, uLevel: { value: 1 }, uNight: { value: 0 }, uSleep: { value: 1 },
      uRem: { value: 0 }, uLab: { value: 0 }, uPump: { value: 0 }, uDump: { value: 0 }, uHmin: { value: H_MIN }, uHrange: { value: H_RANGE },
    }]),
    vertexShader: `
      attribute vec4 aInfo; attribute vec3 aTint; attribute float aWin;
      uniform sampler2D uState; uniform float uTime, uSleep, uRem, uHmin, uHrange;
      varying vec3 vLocal, vNrm, vTint, vFlashCol; varying vec4 vState; varying vec4 vInfo; varying float vH, vWin; varying vec2 vSize;
      #include <fog_pars_vertex>
      void main(){
        float di = aInfo.x; vec2 uv = vec2((di + 0.5) / ${TEX_W}.0, 0.25);
        vec4 st = texture2D(uState, uv); vec3 fc = texture2D(uState, vec2(uv.x, 0.75)).rgb;
        float lvl = st.r * 3.0;
        float up = smoothstep(0.55, 1.9, lvl);
        float plinth = step(0.5, aInfo.w);
        float h = mix((uHmin + uHrange * up) * aInfo.z * (0.72 + 0.28 * uSleep), 1.0, plinth);
        vec3 pos = position; pos.y *= h;
        float sx = length(instanceMatrix[0].xyz), sy = length(instanceMatrix[1].xyz), sz = length(instanceMatrix[2].xyz);
        // REM: the towers sway (a gentle shear in world units that grows with height)
        float sway = uRem * (1.0 - plinth) * pos.y;
        pos.x += sway * 0.05 * sin(uTime * 0.9 + aInfo.y * 6.2832) / max(sx, 0.1);
        pos.z += sway * 0.035 * cos(uTime * 0.7 + aInfo.y * 9.0) / max(sz, 0.1);
        vLocal = vec3(position.x * sx, pos.y * sy, position.z * sz);
        vH = mix(h, sy, plinth); vSize = vec2(sx, sz);
        vNrm = normal; vTint = aTint; vFlashCol = fc; vState = vec4(lvl, st.g, st.b, up); vInfo = aInfo; vWin = aWin;
        vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: `
      uniform float uTime, uLevel, uNight, uSleep, uLab, uPump, uDump;
      varying vec3 vLocal, vNrm, vTint, vFlashCol; varying vec4 vState; varying vec4 vInfo; varying float vH, vWin; varying vec2 vSize;
      #include <fog_pars_fragment>
      float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
      void main(){
        vec3 n = vNrm;
        float side = 1.0 - abs(n.y), top = step(0.5, n.y);
        float up = vState.w, flash = vState.y, dark = vState.z;
        vec3 tint = mix(vTint, vec3(0.62, 0.76, 0.92), uLab);
        float yk = clamp(vLocal.y / max(vH, 1.0), 0.0, 1.0);
        vec3 col;
        if (vInfo.w > 0.5) {
          // plinth: deep blue-black terrace with a thin lit rim on top
          col = vec3(0.010, 0.012, 0.026) + tint * 0.012;
          float rim = smoothstep(vH - 0.35, vH, vLocal.y) * side;
          vec2 gp = abs(fract(vLocal.xz / 2.75 - 0.5) - 0.5) / fwidth(vLocal.xz / 2.75);
          float plaza = 1.0 - clamp(min(gp.x, gp.y), 0.0, 1.0);
          col += tint * (rim * 0.9 * (0.3 + 0.7 * up) + top * (0.03 + 0.10 * up + plaza * (0.12 + 0.45 * up)));
        } else {
          // tower body: dark, lighter towards the roof, a warm side by day
          col = tint * (0.03 + 0.085 * yk) * (0.7 + 0.3 * abs(n.x) * (1.0 - uNight));
          float across = abs(n.x) > 0.5 ? vLocal.z : vLocal.x, hw = abs(n.x) > 0.5 ? vSize.y * 0.5 : vSize.x * 0.5;
          float edge = side * (1.0 - smoothstep(0.0, 0.14, hw - abs(across)));
          col += edge * tint * (0.25 + 0.9 * up);
          // windows: a procedural grid, lit fraction from activity + night, seeded per tower
          if (side > 0.5) {
            float u = abs(n.x) > 0.5 ? vLocal.z : vLocal.x;
            vec2 g = vec2(u, vLocal.y) / vec2(1.7, 2.4);
            vec2 cell = floor(g), f = fract(g);
            float inWin = step(0.26, f.x) * step(f.x, 0.74) * step(0.30, f.y) * step(f.y, 0.72);
            float seed = floor(vInfo.y * 1024.0 + 0.5);
            float r = hash(cell + seed * 0.37 + n.x * 3.0 + n.z * 7.0);
            float litFrac = (0.10 + 0.55 * up + 0.22 * uNight) * vWin * (0.35 + 0.65 * uSleep);
            float lit = step(r, litFrac) * step(vLocal.y, vH - 0.9);
            float flick = 0.82 + 0.18 * sin(uTime * (0.6 + r * 2.5) * (0.4 + 0.6 * uSleep) + r * 40.0);
            float pump = 1.0 + uPump * 0.6 * (0.5 + 0.5 * sin(uTime * 2.2 - vLocal.y * 0.25));
            float dump = 1.0 - uDump * step(0.55, hash(vec2(cell.y + floor(uTime * 7.0), seed * 0.11)));
            vec3 wcol = mix(tint, vec3(1.0, 0.93, 0.80), 0.25 + 0.6 * hash(cell * 1.7 + seed * 0.53));
            col += inWin * lit * flick * pump * dump * wcol * (0.55 + 1.1 * up) * (1.0 - uLab);
          }
          // roof and rim glow scale with activity
          col += top * tint * (0.55 + 1.6 * up);
          col += side * smoothstep(vH - 0.5, vH, vLocal.y) * tint * (0.8 + 1.6 * up);
        }
        col *= dark * uLevel;
        // flash: a white-orange bloom that fades
        col += vFlashCol * flash * flash * (0.4 + 1.2 * top + 0.5 * yk) * uLevel;
        gl_FragColor = vec4(col, 1.0);
        ${FOG_MIX}
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    fog: true,
  });
  const towers = new THREE.InstancedMesh(geo, towerMat, M);
  towers.frustumCulled = false;
  const m4 = new THREE.Matrix4(), q0 = new THREE.Quaternion(), sv = new THREE.Vector3(), pv = new THREE.Vector3();
  layout.forEach((L, k) => {
    m4.compose(pv.set(L.x, L.y0, L.z), q0, sv.set(L.sx, L.sy, L.sz));
    towers.setMatrixAt(k, m4);
    aInfo[k * 4] = L.i; aInfo[k * 4 + 1] = L.seed; aInfo[k * 4 + 2] = L.hmul; aInfo[k * 4 + 3] = L.kind;
    aTint[k * 3] = L.tint.r; aTint[k * 3 + 1] = L.tint.g; aTint[k * 3 + 2] = L.tint.b;
    aWin[k] = L.win;
  });
  geo.setAttribute("aInfo", new THREE.InstancedBufferAttribute(aInfo, 4));
  geo.setAttribute("aTint", new THREE.InstancedBufferAttribute(aTint, 3));
  geo.setAttribute("aWin", new THREE.InstancedBufferAttribute(aWin, 1));
  towers.instanceMatrix.needsUpdate = true;
  root.add(towers);
  disposables.push(geo, towerMat);

  // ---------------- roads: the real fibres, light pulses in the shader ----------------
  const rg = new THREE.BufferGeometry();
  rg.setAttribute("position", new THREE.BufferAttribute(data.roads.positions, 3));
  rg.setAttribute("ends", new THREE.BufferAttribute(data.roads.pairs, 2));
  rg.setAttribute("tpos", new THREE.BufferAttribute(data.roads.t, 1));
  const roadMat = new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uState: { value: stateTex }, uTime: { value: 0 }, uLevel: { value: 1 }, uNight: { value: 0 }, uSpeed: { value: 1 }, uLab: { value: 0 },
      uOpacity: { value: 0.32 * Math.sqrt(2500 / Math.max(1, data.roads.fibres)) },
    }]),
    vertexShader: `
      attribute vec2 ends; attribute float tpos;
      uniform sampler2D uState; uniform float uTime, uLevel, uNight, uSpeed, uLab;
      varying vec3 vCol;
      #include <fog_pars_vertex>
      vec4 stAt(float i){ return i < 0.0 ? vec4(0.33, 0.0, 1.0, 0.0) : texture2D(uState, vec2((i + 0.5) / ${TEX_W}.0, 0.25)); }
      vec3 fcAt(float i){ return i < 0.0 ? vec3(0.0) : texture2D(uState, vec2((i + 0.5) / ${TEX_W}.0, 0.75)).rgb; }
      void main(){
        vec4 sa = stAt(ends.x), sb = stAt(ends.y);
        float a = sa.r * 3.0, b = sb.r * 3.0;
        float drive = smoothstep(1.05, 2.0, max(a, b));
        float dark = min(sa.b, sb.b);
        float dir = a >= b ? tpos : 1.0 - tpos;
        float wave = pow(0.5 + 0.5 * sin(dir * 22.0 - uTime * 4.5 * uSpeed), 10.0);
        float slow = 0.6 + 0.4 * sin(dir * 6.0 - uTime * 1.2 * uSpeed + ends.x * 0.37);
        float flash = max(sa.g, sb.g);
        vec3 tint = mix(vec3(1.0, 0.42, 0.0), vec3(0.55, 0.78, 0.95), uLab);
        vec3 c = mix(tint, vec3(1.0, 0.93, 0.85), drive * wave * 0.7);
        float bright = (0.075 + 0.07 * uNight) * slow + drive * (0.3 + 2.2 * wave);
        c = c * bright * uLevel * dark;
        c += mix(fcAt(ends.x), fcAt(ends.y), tpos) * flash * flash * 1.6 * uLevel;
        vCol = c;
        vec4 mvPosition = modelViewMatrix * vec4(position + vec3(0.0, 0.45, 0.0), 1.0);
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: `
      uniform float uOpacity; varying vec3 vCol;
      #include <fog_pars_fragment>
      void main(){
        gl_FragColor = vec4(vCol * uOpacity, 1.0);
        ${FOG_ADD}
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: true,
  });
  const roads = new THREE.LineSegments(rg, roadMat); roads.frustumCulled = false; root.add(roads);
  disposables.push(rg, roadMat);

  // ---------------- labels for the four places (+ pins) ----------------
  const labels = [], pinPos = [];
  for (const role of ["home", "reward", "park", "fear"]) {
    const i = data.districtOf(role);
    if (i == null) continue;
    const sp = textSprite(PLACE_LABEL[role], ROLE_LABEL_COLOR[role]);
    const top = data.districts[i].pos.y + H_MIN + H_RANGE * 1.2;
    sp.position.copy(data.districts[i].pos).setY(top + 26);
    const L = { sp, i, role, base: 0.9 };
    sp.onBeforeRender = (r, sc, cam) => {                       // fade when the camera stands in that district
      const d = cam.position.distanceTo(sp.position);
      sp.material.opacity = L.base * THREE.MathUtils.smoothstep(d, 90, 220);
    };
    root.add(sp); labels.push(L);
    disposables.push(sp.material.map, sp.material);
    pinPos.push(sp.position.x, data.districts[i].pos.y + 2, sp.position.z, sp.position.x, top + 18, sp.position.z);
  }
  const pinGeo = new THREE.BufferGeometry();
  pinGeo.setAttribute("position", new THREE.Float32BufferAttribute(pinPos, 3));
  const pinMat = new THREE.LineBasicMaterial({ color: 0xffb070, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false });
  const pins = new THREE.LineSegments(pinGeo, pinMat); root.add(pins);
  disposables.push(pinGeo, pinMat);

  // ---------------- per-frame ----------------
  let fear = 0, fearShown = 0, t = 0, pulseT = 0;
  const groupIdx = {};
  data.districts.forEach(d => (groupIdx[d.group] ||= []).push(d.i));
  const flashC = new THREE.Color(), warmWhite = new THREE.Color(1, 0.95, 0.85);
  function setFear(k) { fear = Math.max(0, Math.min(1, +k || 0)); }

  function update(dt, env, act) {
    t += dt;
    const stage = env?.stage || "AWAKE";
    const sleepK = stage === "NREM" ? 0.3 : stage === "REM" ? 0.6 : 1;
    const rem = stage === "REM" ? 1 : 0;
    const dayK = env?.dayK ?? 1;
    const night = env?.night ? 1 : Math.max(0, Math.min(1, 1 - dayK / 0.5));
    const lab = env?.lab ? 1 : 0;
    const lvl = sleepK * (0.6 + 0.4 * Math.max(dayK, 0.6));
    const market = env?.market || "calm";
    pulseT += dt * (stage === "NREM" ? 0.3 : 1);
    const U = towerMat.uniforms;
    U.uTime.value = pulseT; U.uLevel.value = lvl; U.uNight.value = night; U.uSleep.value = sleepK; U.uRem.value = rem; U.uLab.value = lab;
    U.uPump.value += ((market === "pumping" ? 1 : 0) - U.uPump.value) * (1 - Math.exp(-dt * 2));
    U.uDump.value += ((market === "dumping" ? 1 : 0) - U.uDump.value) * (1 - Math.exp(-dt * 2));
    const RU = roadMat.uniforms;
    RU.uTime.value = pulseT; RU.uLevel.value = sleepK * (0.75 + 0.25 * night); RU.uNight.value = night; RU.uSpeed.value = stage === "NREM" ? 0.35 : 1; RU.uLab.value = lab;
    sky.material.uniforms.uNight.value = night; sky.material.uniforms.uLab.value = lab; sky.material.uniforms.uSleep.value = sleepK;
    ground.material.uniforms.uNight.value = night; ground.material.uniforms.uLab.value = lab; ground.material.uniforms.uLevel.value = sleepK;
    fearShown += (fear - fearShown) * (1 - Math.exp(-dt * 3));
    const flicker = fearShown > 0.02 ? 0.55 + 0.45 * Math.abs(Math.sin(t * 9.1) * Math.sin(t * 2.3 + 1)) : 0;

    const k = 1 - Math.exp(-dt * 2.5);
    const hasAct = !!act && act.length >= N;
    for (let i = 0; i < N; i++) {
      const a = hasAct ? Math.min(3, Math.max(0, act[i] || 0)) : 1;
      level[i] += (a - level[i]) * k;
      const d = data.districts[i];
      const dark = d.role === "fear" ? 0.06 + 0.94 * fearShown * flicker : d.role === "salience" ? Math.min(1, 0.3 + 1.6 * fearShown) : 1;
      const o = i * 4;
      state[o] = Math.min(255, Math.round(level[i] / 3 * 255));
      if (flashK[i] > 0) { flashK[i] = Math.max(0, flashK[i] - dt * 0.4); state[o + 1] = Math.round(flashK[i] * 255); }
      else state[o + 1] = 0;
      state[o + 2] = Math.round(dark * 255);
    }
    stateTex.needsUpdate = true;
    pinMat.opacity = 0.35 * sleepK;
    for (const L of labels) L.base = (L.role === "fear" ? 0.25 + 0.75 * fearShown : 0.9) * (0.5 + 0.5 * sleepK);
  }

  function flash(regions, color = 0xff6a00) {
    if (!regions) return;
    flashC.set(color).lerp(warmWhite, 0.35);
    const list = Array.isArray(regions) ? regions : Object.keys(regions);
    for (const r of list) for (const i of (typeof r === "number" ? [r] : groupIdx[r] || [])) {
      if (!(i >= 0 && i < N)) continue;
      flashK[i] = 1;
      const o = (TEX_W + i) * 4;
      state[o] = Math.round(flashC.r * 255); state[o + 1] = Math.round(flashC.g * 255); state[o + 2] = Math.round(flashC.b * 255); state[o + 3] = 255;
    }
    stateTex.needsUpdate = true;
  }

  function dispose() {
    scene.remove(root);
    for (const x of disposables) x?.dispose?.();
  }

  const stats = { instances: M, towers: M - N, plinths: N, fibres: data.roads.fibres, roadSegments: data.roads.segments,
    drawCalls: 5 + labels.length, triangles: M * 12 + 96 + 24 * 12 * 2 };
  update(0, {}, null);
  return { update, flash, setFear, object: root, dispose, stats };
}

/** Deterministic PRNG (mulberry32). */
function mulberry(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let x = a; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
}

function textSprite(text, accent = "#ff6a00") {
  const cv = document.createElement("canvas"), x = cv.getContext("2d");
  const fs = 40, pad = 22, bar = 10;
  x.font = `${fs}px ui-monospace, Menlo, monospace`;
  cv.width = Math.ceil(x.measureText(text).width) + pad * 2 + bar; cv.height = fs + 28;
  x.font = `${fs}px ui-monospace, Menlo, monospace`;
  x.fillStyle = "rgba(5,6,12,0.78)"; roundRect(x, 0, 0, cv.width, cv.height, 10); x.fill();
  x.strokeStyle = "rgba(255,241,224,0.25)"; x.lineWidth = 2; roundRect(x, 1, 1, cv.width - 2, cv.height - 2, 9); x.stroke();
  x.fillStyle = accent; roundRect(x, 8, 10, bar - 2, cv.height - 20, 3); x.fill();
  x.fillStyle = "#fff1e0"; x.textBaseline = "middle"; x.fillText(text, pad + bar, cv.height / 2 + 2);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false, toneMapped: false, sizeAttenuation: false, fog: false }));
  const h = 0.036; sp.scale.set(h * cv.width / cv.height, h, 1);
  sp.renderOrder = 10;
  return sp;
}
function roundRect(x, l, t, w, h, r) {
  x.beginPath(); x.moveTo(l + r, t); x.arcTo(l + w, t, l + w, t + h, r); x.arcTo(l + w, t + h, l, t + h, r); x.arcTo(l, t + h, l, t, r); x.arcTo(l, t, l + w, t, r); x.closePath();
}
