// Mini real brain (picture in picture, hud stream). The real tractography (web/fibres.bin, subsampled per quality) drawn
// as one LineSegments with the same activity-driven fibre shader as /brain (web/index.html), plus the 214 atlas regions
// of web/brain.json as glow points. Always on, bottom-right of the life page; click opens /brain.
//
// createMiniBrain(el, {quality, raw}) -> {hello(m), tick(m), flash(regions, color), pulse(fromEl), update(dt, env), dispose()}
//   raw (optional): Promise<{brain, meta, fibres, ends}> shared with the construct (data.js loadBrainRaw), so the page
//   downloads brain.json / fibres.bin once; without it the files are fetched here.
//   el        the #minibrain container
//   tick(m)   m.act = activity per brain region (index = web/brain.json node index), m.sleep.stage
//   flash(regions, color)  regions = [brain region indices] (chat.regions) or [group names] (chat.networks)
//   pulse(fromEl)          a dot travels from an element (the chat box) to the mini brain
// The big fibre file is shared with the construct (same URL, browser cache): when the page exposes window.__sub01 the
// fibres are fetched after the construct is ready, so nothing is downloaded twice. It is a model of brain activity,
// not a mind.
import * as THREE from "three";

const CSS = `
  #minibrain { cursor:pointer; }
  #minibrain canvas { width:100%; height:100%; display:block; }
  #minibrain .cap { position:absolute; left:8px; bottom:6px; right:8px; font-size:10px; color:#bdbdca; text-shadow:0 1px 4px #000;
                    pointer-events:none; }
  #minibrain .cap b { color:#ff6a00; font-weight:normal; }
  @media (max-width: 899px) { #minibrain .cap .long { display:none; } }
  .mb-pulse { position:fixed; z-index:40; width:10px; height:10px; border-radius:50%; background:#ff6a00; pointer-events:none;
              box-shadow:0 0 14px #ff6a00, 0 0 28px #ff6a00; transition:transform .75s cubic-bezier(.3,.7,.3,1), opacity .75s; }
`;
// every Nth fibre of the 60k streamlines
const FIBRE_STEP = { low: 40, medium: 15, high: 8 };
const LOOK = { AWAKE: { level: 1, speed: 1, rot: 0.5 }, NREM: { level: 0.35, speed: 0.25, rot: 0.12 }, REM: { level: 0.5, speed: 0.6, rot: 0.25 } };

export function createMiniBrain(el, { quality, raw = null } = {}) {
  const noop = { hello() {}, tick() {}, flash() {}, pulse() {}, update() {}, dispose() {} };
  if (!el) return noop;
  const dbg = (window.__minibrain = { regions: 0, fibres: 0, flashes: 0 });
  const style = document.createElement("style"); style.textContent = CSS; document.head.appendChild(style);
  el.title = "open the brain";
  el.setAttribute("role", "link");
  el.setAttribute("aria-label", "its brain, live (open the brain page)");
  el.onclick = () => { location.href = "/brain"; };
  const cap = document.createElement("span"); cap.className = "cap";
  const long = document.createElement("span"); long.className = "long"; long.textContent = " · a model of brain activity, not a mind";
  cap.append("its brain, live", long, " · ");
  const stageEl = document.createElement("b"); stageEl.textContent = "AWAKE"; cap.appendChild(stageEl);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "low-power" });
  } catch (e) { console.warn("[minibrain] no WebGL:", e && e.message); return noop; }
  renderer.setPixelRatio(Math.min(1.5, devicePixelRatio || 1));
  renderer.setClearColor(0x05050a, 1);
  el.append(renderer.domElement, cap);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 4 / 3, 1, 3000);
  camera.up.set(0, 0, 1); camera.position.set(-170, 115, 82); camera.lookAt(0, 0, 0);   // /brain framing, closer (the PiP is small)
  const pivot = new THREE.Group(); scene.add(pivot);

  const actData = new Uint8Array(256 * 4);           // R = activity / 3, G = flash (0..1) per region
  const actTex = new THREE.DataTexture(actData, 256, 1, THREE.RGBAFormat);
  const flashCol = new THREE.Color(0xff6a00);
  let nodes = [], groupIdx = {}, points = null, fibreMat = null;
  let act = null, base = null, flashK = null;
  const look = { ...LOOK.AWAKE }, hot = new THREE.Color(0xff7a1a), cold = new THREE.Color(0x3a2f8a), tmp = new THREE.Color();
  let stage = "AWAKE", disposed = false;

  const qname = (quality && quality.name) || "medium";

  (raw ? raw.then(x => x.brain) : fetch("/brain.json").then(r => (r.ok ? r.json() : null))).then(d => {
    if (disposed || !d || !Array.isArray(d.nodes)) return;
    nodes = d.nodes; dbg.regions = nodes.length;
    const n = nodes.length, pos = new Float32Array(n * 3);
    nodes.forEach((nd, i) => { pos.set(nd.q || nd.p, i * 3); (groupIdx[nd.group] ||= []).push(i); });
    act = new Float32Array(n); flashK = new Float32Array(n);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute("size", new THREE.BufferAttribute(new Float32Array(n).fill(3), 1));
    const m = new THREE.ShaderMaterial({
      vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { scale: { value: 1 } },
      vertexShader: `attribute float size; varying vec3 vC; uniform float scale;
        void main(){ vC = color; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * scale * 420.0 / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vC; void main(){ vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard;
        gl_FragColor = vec4(vC, smoothstep(0.5, 0.05, r)); }`,
    });
    points = new THREE.Points(g, m); pivot.add(points); resize();
    loadFibres(nodes);
  }).catch(e => console.warn("[minibrain] brain.json:", e && e.message));

  // the fibres come after the construct has loaded the same files (browser cache); never wait more than ~25 s
  function loadFibres(nodesList) {
    let waited = 0;
    const go = () => {
      if (disposed) return;
      const s = window.__sub01;
      if (s && !s.ready && waited < 25000) { waited += 400; setTimeout(go, 400); return; }
      (raw ? raw.then(x => [x.meta, x.fibres, x.ends])
        : Promise.all([fetch("/fibres.json").then(r => r.json()), fetch("/fibres.bin").then(r => r.arrayBuffer()), fetch("/fibres_ends.bin").then(r => r.arrayBuffer())]))
        .then(([meta, fbuf, ebuf]) => { if (!disposed) buildFibres(nodesList, meta, fbuf, ebuf); })
        .catch(e => console.warn("[minibrain] fibres:", e && e.message));
    };
    go();
  }

  function buildFibres(nodesList, meta, fbuf, ebuf) {
    const step = FIBRE_STEP[qname] || FIBRE_STEP.medium, k = meta.pts;
    let maxLab = 0; for (const nd of nodesList) maxLab = Math.max(maxLab, nd.lab | 0);
    const lab2node = new Int16Array(maxLab + 1).fill(-1); nodesList.forEach((nd, i) => { lab2node[nd.lab] = i; });
    const P = new Float32Array(fbuf), E = new Int16Array(ebuf), n = Math.floor(meta.n / step), segs = n * (k - 1);
    const pos = new Float32Array(segs * 6), dcol = new Float32Array(segs * 6), nod = new Float32Array(segs * 4), tp = new Float32Array(segs * 2);
    let o = 0;
    for (let s0 = 0; s0 < n; s0++) {
      const s = s0 * step;
      const la = E[2 * s], lb = E[2 * s + 1];
      const na = la >= 0 && la <= maxLab ? lab2node[la] : -1, nb = lb >= 0 && lb <= maxLab ? lab2node[lb] : -1;
      for (let i = 0; i < k - 1; i++, o++) {
        const a = (s * k + i) * 3, b = a + 3;
        const dx = P[b] - P[a], dy = P[b + 1] - P[a + 1], dz = P[b + 2] - P[a + 2], L = Math.hypot(dx, dy, dz) || 1;
        for (let j = 0; j < 3; j++) { pos[o * 6 + j] = P[a + j]; pos[o * 6 + 3 + j] = P[b + j]; }
        const c0 = Math.abs(dx) / L, c1 = Math.abs(dy) / L, c2 = Math.abs(dz) / L;
        dcol[o * 6] = dcol[o * 6 + 3] = c0; dcol[o * 6 + 1] = dcol[o * 6 + 4] = c1; dcol[o * 6 + 2] = dcol[o * 6 + 5] = c2;
        nod[o * 4] = nod[o * 4 + 2] = na; nod[o * 4 + 1] = nod[o * 4 + 3] = nb;
        tp[o * 2] = i / (k - 1); tp[o * 2 + 1] = (i + 1) / (k - 1);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("dcol", new THREE.BufferAttribute(dcol, 3));
    g.setAttribute("nodes", new THREE.BufferAttribute(nod, 2));
    g.setAttribute("tpos", new THREE.BufferAttribute(tp, 1));
    const op = qname === "low" ? 0.085 : qname === "high" ? 0.03 : 0.045;     // fewer fibres -> brighter each
    fibreMat = new THREE.ShaderMaterial({
      uniforms: { act: { value: actTex }, time: { value: 0 }, opacity: { value: op }, level: { value: 1 }, flashCol: { value: flashCol } },
      vertexShader: `
        attribute vec3 dcol; attribute vec2 nodes; attribute float tpos;
        uniform sampler2D act; uniform float time; uniform float level; uniform vec3 flashCol;
        varying vec3 vCol;
        vec2 actAt(float i){ return i < 0.0 ? vec2(0.0) : texture2D(act, vec2((i + 0.5) / 256.0, 0.5)).rg; }
        void main(){
          vec2 a = actAt(nodes.x), b = actAt(nodes.y);
          float drive = clamp((max(a.x, b.x) * 3.0 - 1.15) / 0.9, 0.0, 1.0);        // above the region's own baseline
          float fl = max(a.y, b.y);
          float dir = a.x >= b.x ? tpos : 1.0 - tpos;                                // pulses leave the more active end
          float wave = pow(0.5 + 0.5 * sin(dir * 22.0 - time * 7.0), 8.0);
          float glow = 0.6 + level * drive * (0.6 + 3.5 * wave) + fl * (2.0 + 4.0 * wave);
          vec3 c = mix(dcol, vec3(1.0), drive * wave * 0.35);
          vCol = mix(c, flashCol, clamp(fl * 1.4, 0.0, 0.85)) * glow;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: "uniform float opacity; varying vec3 vCol; void main(){ gl_FragColor = vec4(vCol * opacity, 1.0); }",
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const lines = new THREE.LineSegments(g, fibreMat); lines.frustumCulled = false; pivot.add(lines);
    dbg.fibres = n;
  }

  function resize() {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    if (points) points.material.uniforms.scale.value = Math.max(0.6, h / 260) * renderer.getPixelRatio();
  }
  const ro = new ResizeObserver(resize); ro.observe(el); resize();

  let acc = 0, t = 0;
  return {
    hello() {},
    tick(m) {
      if (m.sleep?.stage) { stage = m.sleep.stage; stageEl.textContent = stage; }
      if (!act || !Array.isArray(m.act) || m.act.length !== act.length) return;
      const n = act.length;
      if (!base) base = Float32Array.from(m.act);
      let sum = 0;
      for (let i = 0; i < n; i++) { const a = +m.act[i] || 0; base[i] = base[i] * 0.998 + a * 0.002; act[i] = a / Math.max(base[i], 0.02); sum += act[i]; }
      const gm = Math.max(1e-3, sum / n);             // stage changes rescale the whole brain: show regional contrast
      for (let i = 0; i < n; i++) act[i] /= gm;
    },
    flash(regions, color = 0xff6a00) {
      if (!flashK || !regions) return;
      const list = Array.isArray(regions) ? regions : Object.keys(regions);
      flashCol.set(color);
      for (const r of list) {
        for (const i of (typeof r === "number" ? [r] : groupIdx[r] || [])) if (i >= 0 && i < flashK.length) flashK[i] = 1;
      }
      dbg.flashes++;
    },
    pulse(fromEl) {
      if (!fromEl) return;
      const a = fromEl.getBoundingClientRect(), b = el.getBoundingClientRect();
      if (!a.width && !a.height) return;
      const dot = document.createElement("div"); dot.className = "mb-pulse";
      dot.style.left = `${a.left + a.width / 2 - 5}px`; dot.style.top = `${a.top + a.height / 2 - 5}px`;
      document.body.appendChild(dot);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        dot.style.transform = `translate(${b.left + b.width / 2 - a.left - a.width / 2}px, ${b.top + b.height / 2 - a.top - a.height / 2}px) scale(.5)`;
        dot.style.opacity = "0.15";
      }));
      setTimeout(() => dot.remove(), 900);
    },
    update(dt, env) {
      t += dt; acc += dt;
      if (!points || el.offsetParent === null) return;
      const every = env?.quality?.name === "low" ? 1 / 20 : 1 / 30;     // the mini view does not need 60 fps
      if (acc < every) return;
      const step = acc; acc = 0;
      const tgt = LOOK[stage] || LOOK.AWAKE, kk = 1 - Math.exp(-step / 2.5);
      for (const key in look) look[key] += (tgt[key] - look[key]) * kk;
      pivot.rotation.z += step * 0.25 * look.rot;
      const col = points.geometry.attributes.color, size = points.geometry.attributes.size;
      let anyFlash = false;
      for (let i = 0; i < act.length; i++) {
        const a = Math.max(0, Math.min(1, (act[i] - 0.6) / 1.8));
        const f = flashK[i];
        tmp.copy(cold).lerp(hot, a * look.level);
        if (f > 0) { tmp.lerp(flashCol, f); flashK[i] = Math.max(0, f - step * 0.55); anyFlash = true; }
        col.setXYZ(i, tmp.r * (0.35 + 0.65 * look.level), tmp.g * (0.35 + 0.65 * look.level), tmp.b * (0.35 + 0.65 * look.level));
        size.setX(i, 1.6 + a * 3.2 + f * 5);
        actData[i * 4] = Math.min(255, Math.round(act[i] / 3 * 255));
        actData[i * 4 + 1] = Math.round(Math.min(1, f) * 255);
      }
      col.needsUpdate = true; size.needsUpdate = true; actTex.needsUpdate = true;
      if (fibreMat) {
        fibreMat.uniforms.time.value += step * look.speed; fibreMat.uniforms.level.value = look.level;
      }
      renderer.render(scene, camera);
      dbg.activeFlash = anyFlash;
    },
    dispose() { disposed = true; ro.disconnect(); renderer.dispose(); el.textContent = ""; },
  };
}
