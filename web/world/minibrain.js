// STUB mini brain (foundation). The hud stream replaces this file with the mini fibre brain.
//
// createMiniBrain(el, {quality}) -> {hello(m), tick(m), flash(regions, color), pulse(fromEl), update(dt, env), dispose()}
//   el        the #minibrain container (bottom-right overlay); clicking it opens /brain
//   tick(m)   m.act = activity per brain region (index = web/brain.json node index), m.sleep.stage
//   flash(regions, color)  regions = [brain region indices] (chat.regions) or [group names] (chat.networks)
//   pulse(fromEl)          short visual pulse from an element (the chat box) towards the brain
// This placeholder draws the 214 regions of web/brain.json as points (size / colour = live activity) with the
// strongest connections as faint lines, in its own small canvas. It is a model of brain activity, not a mind.
import * as THREE from "three";

const CSS = `
  #minibrain { cursor:pointer; }
  #minibrain canvas { width:100%; height:100%; display:block; }
  #minibrain .cap { position:absolute; left:8px; bottom:6px; right:8px; font-size:10px; color:#bdbdca; text-shadow:0 1px 4px #000;
                    pointer-events:none; }
  #minibrain .cap b { color:#ff6a00; font-weight:normal; }
  @media (max-width: 899px) { #minibrain .cap .long { display:none; } }
  .mb-pulse { position:fixed; z-index:40; width:10px; height:10px; border-radius:50%; background:#ff6a00; pointer-events:none;
              box-shadow:0 0 14px #ff6a00; transition:transform .7s cubic-bezier(.3,.7,.3,1), opacity .7s; }
`;

export function createMiniBrain(el, { quality } = {}) {
  const noop = { hello() {}, tick() {}, flash() {}, pulse() {}, update() {}, dispose() {} };
  if (!el) return noop;
  const style = document.createElement("style"); style.textContent = CSS; document.head.appendChild(style);
  el.title = "open the brain";
  el.setAttribute("role", "link");
  el.onclick = () => { location.href = "/brain"; };
  const cap = document.createElement("span"); cap.className = "cap";
  const long = document.createElement("span"); long.className = "long"; long.textContent = " · a model of brain activity, not a mind";
  cap.append("its brain, live", long, " · ");
  const stageEl = document.createElement("b"); stageEl.textContent = "AWAKE"; cap.appendChild(stageEl);

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(1.5, devicePixelRatio || 1));
  renderer.setClearColor(0x000000, 1);
  el.append(renderer.domElement, cap);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 4 / 3, 1, 1000);
  camera.position.set(0, 30, 250); camera.lookAt(0, 0, 0);
  const pivot = new THREE.Group(); scene.add(pivot);

  let nodes = [], groupIdx = {}, points = null, act = null, flashK = null, flashCol = null;
  const hot = new THREE.Color(0xff7a1a), cold = new THREE.Color(0x4a3a9a), tmp = new THREE.Color();

  fetch("/brain.json").then(r => (r.ok ? r.json() : null)).then(d => {
    if (!d || !Array.isArray(d.nodes)) return;
    nodes = d.nodes;
    const n = nodes.length, pos = new Float32Array(n * 3);
    nodes.forEach((nd, i) => {                    // MNI mm: x left-right, y back-front, z down-up
      pos[i * 3] = nd.p[0]; pos[i * 3 + 1] = nd.p[2]; pos[i * 3 + 2] = -nd.p[1];
      (groupIdx[nd.group] ||= []).push(i);
    });
    const c = new THREE.Box3().setFromArray(pos).getCenter(new THREE.Vector3());
    for (let i = 0; i < n; i++) { pos[i * 3] -= c.x; pos[i * 3 + 1] -= c.y; pos[i * 3 + 2] -= c.z; }
    act = new Float32Array(n); flashK = new Float32Array(n); flashCol = Array.from({ length: n }, () => new THREE.Color());
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute("size", new THREE.BufferAttribute(new Float32Array(n).fill(4), 1));
    const m = new THREE.ShaderMaterial({
      vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { scale: { value: 1 } },
      vertexShader: `attribute float size; varying vec3 vC; uniform float scale;
        void main(){ vC = color; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * scale * 700.0 / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vC; void main(){ vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard;
        gl_FragColor = vec4(vC, smoothstep(0.5, 0.1, r)); }`,
    });
    points = new THREE.Points(g, m); pivot.add(points); resize();
    const edges = (d.edges || []).filter(e => e[2] >= 0.5).slice(0, 400), lp = new Float32Array(edges.length * 6);
    edges.forEach(([a, b], k) => { lp.set(pos.subarray(a * 3, a * 3 + 3), k * 6); lp.set(pos.subarray(b * 3, b * 3 + 3), k * 6 + 3); });
    const lg = new THREE.BufferGeometry(); lg.setAttribute("position", new THREE.BufferAttribute(lp, 3));
    pivot.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: 0x5a3aa0, transparent: true, opacity: 0.18 })));
  }).catch(() => {});

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
      if (m.sleep?.stage) stageEl.textContent = m.sleep.stage;
      if (!act || !Array.isArray(m.act)) return;
      let hi = 1e-6; for (const v of m.act) hi = Math.max(hi, v);
      for (let i = 0; i < act.length; i++) act[i] += ((m.act[i] || 0) / hi - act[i]) * 0.3;
    },
    flash(regions, color = 0xff6a00) {
      if (!flashK || !regions) return;
      const list = Array.isArray(regions) ? regions : Object.keys(regions);
      for (const r of list) {
        for (const i of (typeof r === "number" ? [r] : groupIdx[r] || [])) {
          if (i >= 0 && i < flashK.length) { flashK[i] = 1; flashCol[i].set(color); }
        }
      }
    },
    pulse(fromEl) {
      if (!fromEl) return;
      const a = fromEl.getBoundingClientRect(), b = el.getBoundingClientRect();
      const dot = document.createElement("div"); dot.className = "mb-pulse";
      dot.style.left = `${a.left + a.width / 2}px`; dot.style.top = `${a.top + a.height / 2}px`;
      document.body.appendChild(dot);
      requestAnimationFrame(() => {
        dot.style.transform = `translate(${b.left + b.width / 2 - a.left - a.width / 2}px, ${b.top + b.height / 2 - a.top - a.height / 2}px)`;
        dot.style.opacity = "0.2";
      });
      setTimeout(() => dot.remove(), 800);
    },
    update(dt, env) {
      t += dt; acc += dt;
      if (!points || el.offsetParent === null) return;
      const fps = env?.quality?.name === "low" ? 1 / 15 : 1 / 30;       // the mini view does not need 60 fps
      if (acc < fps) return;
      const step = acc; acc = 0;
      pivot.rotation.y = t * 0.15;
      const col = points.geometry.attributes.color, size = points.geometry.attributes.size;
      const asleep = env?.stage && env.stage !== "AWAKE";
      for (let i = 0; i < act.length; i++) {
        const a = act[i];
        tmp.copy(cold).lerp(hot, Math.min(1, Math.pow(a, 1.5) * (asleep ? 0.7 : 1)));
        if (flashK[i] > 0) { tmp.lerp(flashCol[i], flashK[i]); flashK[i] = Math.max(0, flashK[i] - step * 0.6); }
        col.setXYZ(i, tmp.r, tmp.g, tmp.b);
        size.setX(i, 2.5 + a * 5 + flashK[i] * 6);
      }
      col.needsUpdate = true; size.needsUpdate = true;
      renderer.render(scene, camera);
    },
    dispose() { ro.disconnect(); renderer.dispose(); el.textContent = ""; },
  };
}
