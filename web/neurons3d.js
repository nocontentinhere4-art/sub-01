/* Neurons3D: his live spiking neurons as points inside the 3D brain (#62). Reusable: /brain draws it today, and the
   room's mini brain can import it with a few lines (it needs only THREE, a scene, the region centroids and the cortex).

   Simulated spiking neurons (1M on GPU / 20k on CPU) inside the real wiring of one person's brain; each dot stands
   for a sampled model neuron; a model, not a mind.

   Usage:
     const n3 = Neurons3D.create({THREE, scene, nodes, cortex, sizes});
       nodes  : brain.json nodes (214, in the spiking networks' region order): {q:[x,y,z], group}
       cortex : Float32Array of cortex.bin vertex positions (optional; without it every region is a small sphere)
       sizes  : neurons3d.json "sizes": points a region (the 20k network's populations; scaled to maxPoints)
     n3.resize(bufferHeightPx, fovDeg) on resize
     n3.onFrame(msg)       every {"type":"spiking"} websocket frame (spiking/frames.py: n3.rq rates, n3.sq spikes)
     n3.update(nowMs)      once per rendered frame (cheap: a few uniforms)
     n3.setVisible(on)     the toggle; n3.state() -> {live, net, tint} for the caption
   Data: one byte a region of spike rate (log scale 0.1-100 Hz, byte 0 = below), 3 bytes a spike (region, slot 0-255,
   time 0-255 of the frame's span). Every flash is a recorded spike of a model neuron; with no frames nothing flashes.
   One draw call (THREE.Points), at most maxPoints (20 000) points; nothing is uploaded while it is hidden. */
(function (root) {
  "use strict";
  const LIVE_MS = 10000, RATE_LO = 0.1, RATE_HI = 100, FLASH_S = 0.35;

  function unb64(s) {
    if (!s) return new Uint8Array(0);
    const b = atob(s), out = new Uint8Array(b.length);
    for (let i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
    return out;
  }
  // rate (Hz) -> the byte quantise_rates sends (for group-rate tinting when a network sends no per-region rates)
  const rateByte = hz => !(hz >= RATE_LO) ? 0 : Math.max(1, Math.min(255, Math.round(1 + 254 * Math.log(Math.min(hz, RATE_HI) / RATE_LO) / Math.log(RATE_HI / RATE_LO))));
  function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }

  // ---------- where the points go: inside each region, from its centroid and the cortex mesh ----------
  function layout(nodes, cortex, sizes, maxPoints) {
    const R = nodes.length, total = sizes.reduce((a, b) => a + b, 0), k = Math.min(1, maxPoints / total);
    const count = sizes.map(s => Math.max(3, Math.floor(s * k)));
    const start = new Int32Array(R + 1);
    for (let r = 0; r < R; r++) start[r + 1] = start[r] + count[r];
    const N = start[R], pos = new Float32Array(N * 3), reg = new Float32Array(N), rand = rng(62);
    // cortex vertices -> nearest cortical centroid (the Schaefer parcels sit on the cortex; nuclei are inside)
    const cort = [], cells = nodes.map(() => []);
    nodes.forEach((n, i) => { if (/^(LH|RH)_/.test(n.name || "")) cort.push(i); });
    if (cortex && cortex.length) {
      const step = cortex.length / 3 > 40000 ? 2 : 1;                // half the vertices are plenty to find the cells
      for (let v = 0; v < cortex.length / 3; v += step) {
        const x = cortex[3 * v], y = cortex[3 * v + 1], z = cortex[3 * v + 2];
        let best = -1, bd = 1e30;
        for (const i of cort) { const q = nodes[i].q, d = (x - q[0]) ** 2 + (y - q[1]) ** 2 + (z - q[2]) ** 2; if (d < bd) { bd = d; best = i; } }
        if (best >= 0 && bd < 30 * 30) cells[best].push(v);
      }
    }
    for (let r = 0; r < R; r++) {
      const q = nodes[r].q, cell = cells[r], rad = 2.5 + 1.1 * Math.cbrt(count[r]);
      for (let j = start[r]; j < start[r + 1]; j++) {
        let x, y, z;
        if (cell.length > 8) {                                     // just under the cortical surface of its parcel
          const v = cell[Math.floor(rand() * cell.length)], u = 0.04 + 0.2 * rand();
          x = cortex[3 * v] + (q[0] - cortex[3 * v]) * u; y = cortex[3 * v + 1] + (q[1] - cortex[3 * v + 1]) * u;
          z = cortex[3 * v + 2] + (q[2] - cortex[3 * v + 2]) * u;
        } else {                                                    // a nucleus: a small cloud around its centroid
          const a = rand() * 6.2832, c = 2 * rand() - 1, s = Math.sqrt(1 - c * c), rr = rad * Math.cbrt(rand());
          x = q[0] + rr * s * Math.cos(a); y = q[1] + rr * s * Math.sin(a); z = q[2] + rr * c;
        }
        pos[3 * j] = x + (rand() - 0.5) * 0.8; pos[3 * j + 1] = y + (rand() - 0.5) * 0.8; pos[3 * j + 2] = z + (rand() - 0.5) * 0.8;
        reg[j] = r;
      }
    }
    return { N, pos, reg, start, count };
  }

  function create(o) {
    const THREE = o.THREE, nodes = o.nodes, R = nodes.length;
    const sizes = o.sizes && o.sizes.length === R ? o.sizes : nodes.map(() => 90);
    const L = layout(nodes, o.cortex, sizes, o.maxPoints || 20000);
    const flash = new Float32Array(L.N).fill(-1e4);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(L.pos, 3));
    g.setAttribute("aReg", new THREE.BufferAttribute(L.reg, 1));
    const fa = new THREE.BufferAttribute(flash, 1); if (fa.setUsage) fa.setUsage(THREE.DynamicDrawUsage);
    g.setAttribute("aFlash", fa);
    g.computeBoundingSphere();
    // per region: R = rate byte (smoothed), G = decision race highlight (striatum while a race runs)
    const texData = new Uint8Array(256 * 4), tex = new THREE.DataTexture(texData, 256, 1, THREE.RGBAFormat);
    tex.needsUpdate = true;
    const striatum = nodes.map(n => n.group === "reward");
    const mat = new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 }, uRates: { value: tex }, uSize: { value: o.pointSize || 1.3 }, uScale: { value: 1000 },
                  uFade: { value: 0 }, uFlashS: { value: FLASH_S } },
      vertexShader: `
        attribute float aReg; attribute float aFlash;
        uniform float uTime; uniform sampler2D uRates; uniform float uSize; uniform float uScale; uniform float uFlashS;
        varying vec3 vCol; varying float vA;
        void main(){
          vec4 t = texture2D(uRates, vec2((aReg + 0.5) / 256.0, 0.5));
          float rate = smoothstep(0.42, 0.86, t.r);                 // ~2-40 Hz on the log byte scale
          float dt = uTime - aFlash;
          float f = dt < 0.0 ? 0.0 : exp(-dt / uFlashS);
          vec3 base = mix(vec3(0.16, 0.2, 0.34), vec3(1.0, 0.45, 0.12), rate);
          vCol = base * (0.45 + 0.75 * rate) + vec3(1.0, 0.86, 0.6) * 3.0 * f + vec3(1.0, 0.5, 0.1) * 0.9 * t.g;
          vA = 0.5 + 0.4 * rate + 0.8 * f + 0.3 * t.g;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = max(1.5, uSize * (1.0 + 1.5 * f + 0.6 * t.g) * uScale / -mv.z);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform float uFade; varying vec3 vCol; varying float vA;
        void main(){
          vec2 c = gl_PointCoord - 0.5; float d = dot(c, c);
          if (d > 0.25) discard;
          gl_FragColor = vec4(vCol * vA * uFade * (1.0 - 4.0 * d), 1.0);
        }`,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const points = new THREE.Points(g, mat);
    points.name = "neurons"; points.visible = false; points.frustumCulled = false;
    o.scene.add(points);

    const S = { on: false, fade: 0, net: null, lastWall: -1e9, gpuWall: -1e9, tint: null, rates: new Float32Array(R),
                race: new Float32Array(R), raceOn: false, groups: null, prevArrive: 0, gap: 200, t0: performance.now(), dirty: false,
                ns: 0, shown: 0 };
    const clockS = now => (now - S.t0) / 1000;

    function onFrame(m) {
      if (!m || m.type !== "spiking") return;
      if (m.live === false) { S.lastWall = -1e9; return; }
      const n3 = m.n3; if (!n3) return;
      const now = performance.now();
      if (m.net === "cpu") { if (now - S.gpuWall < LIVE_MS) return; } else S.gpuWall = now;
      if (S.net !== m.net) { S.net = m.net; S.rates.fill(0); }
      if (m.groups) S.groups = m.groups;
      const gap = now - S.prevArrive; S.prevArrive = now;
      if (gap > 30 && gap < 2000) S.gap = 0.7 * S.gap + 0.3 * gap;   // wall time between frames: spikes play over it
      S.lastWall = now; S.raceOn = !!n3.race; S.ns = n3.ns || 0;
      // rates: measured per region (rq), else the region's network group rate (say so in the caption)
      let tint = null;
      if (n3.rq) { const q = unb64(n3.rq); if (q.length === R) { tint = "regions"; for (let r = 0; r < R; r++) S.rates[r] = S.rates[r] ? 0.55 * S.rates[r] + 0.45 * q[r] : q[r]; } }
      if (!tint && S.groups) { tint = "groups"; for (let r = 0; r < R; r++) { const hz = S.groups[nodes[r].group]; S.rates[r] = hz == null ? S.rates[r] * 0.9 : rateByte(hz); } }
      S.tint = tint; S.dirty = true;
      // spikes: flash their dots, spread over the time until the next frame as they were spread over the frame
      const b = unb64(n3.sq), span = Math.max(1, n3.span || 200), play = Math.min(600, S.gap) / 1000, t = clockS(now);
      let lo = L.N, hi = -1;
      for (let i = 0; i + 2 < b.length; i += 3) {
        const r = b[i]; if (r >= R) continue;
        const j = L.start[r] + Math.min(L.count[r] - 1, Math.floor(b[i + 1] * L.count[r] / 256));
        flash[j] = t + (b[i + 2] / 255) * play; if (j < lo) lo = j; if (j > hi) hi = j;
      }
      S.shown = b.length / 3;
      if (hi >= 0 && S.on) { fa.needsUpdate = true; }
      else if (hi >= 0) S.pendingFlash = true;
    }

    function update(now) {
      const live = now - S.lastWall < LIVE_MS;
      const target = S.on && live ? 1 : 0;
      S.fade += (target - S.fade) * 0.08; if (Math.abs(S.fade - target) < 0.004) S.fade = target;
      points.visible = S.fade > 0;
      if (!points.visible) return;
      mat.uniforms.uTime.value = clockS(now); mat.uniforms.uFade.value = S.fade;
      let raceDirty = false;
      for (let r = 0; r < R; r++) { if (!striatum[r]) continue;
        const v = S.race[r] + ((S.raceOn && live ? 1 : 0) - S.race[r]) * 0.06; if (Math.abs(v - S.race[r]) > 1e-3) { S.race[r] = v; raceDirty = true; } }
      if (S.dirty || raceDirty) {
        for (let r = 0; r < R; r++) { texData[4 * r] = Math.round(S.rates[r]); texData[4 * r + 1] = Math.round(255 * S.race[r]); }
        tex.needsUpdate = true; S.dirty = false;
      }
      if (S.pendingFlash) { fa.needsUpdate = true; S.pendingFlash = false; }
    }
    // drawing-buffer height (px) and vertical fov: a point of uSize mm is as large as 1 mm at its depth
    function resize(h, fov) { mat.uniforms.uScale.value = h / (2 * Math.tan((fov || 32) * Math.PI / 360)); }
    function setVisible(on) { S.on = !!on; }
    function state() { return { live: performance.now() - S.lastWall < LIVE_MS, net: S.net, tint: S.tint, race: S.raceOn, recorded: S.ns, shown: S.shown, points: L.N }; }
    function dispose() { o.scene.remove(points); g.dispose(); mat.dispose(); tex.dispose(); }
    function rate(r) { return S.rates[r] || 0; }                    // smoothed rate byte of region r (0 = none yet)
    return { object: points, onFrame, update, resize, setVisible, state, dispose, rate, points: L.N };
  }

  // ---------- close-up: real neuron shapes (#78) ----------
  // A block of tissue with 100-300 reconstructed neurons (web/neurons_morph.json: NeuroMorpho.Org, CC BY 4.0,
  // simplified), drawn as instanced line segments: one draw call per cell type, <= SEG_BUDGET segments in all. Each
  // drawn cell stands for a sampled model neuron of the region: when that neuron's spike arrives (n3.sq), its soma
  // flashes and a pulse runs from the soma along its axon at PULSE_UM_S (visibly slowed); its dendrites glow with the
  // region's rate. Only regions the network simulates get a close-up (no cerebellum: it is not one of the 214).
  // Illustrative shapes: the simulated network uses point neurons.
  const SEG_BUDGET = 60000, MAX_CELLS = 300, SOMA_SEGS = 3;
  const PULSE_UM_S = 1000, PULSE_W_UM = 70;                        // 1 mm/s on screen vs ~0.5 m/s in thin axons
  const SLOWDOWN = Math.round(0.5e6 / PULSE_UM_S);                 // ~500x slower than a thin unmyelinated axon
  const KINDS = {                                                  // close-up kind -> cell types, shares, cells drawn
    cortex: { types: [["pyramidal", 0.8], ["basket", 0.2]], cells: 120 },
    striatum: { types: [["medium_spiny", 1]], cells: 220 },
    thalamus: { types: [["relay", 1]], cells: 160 },
    hippocampus: { types: [["ca1_pyramidal", 1]], cells: 150 },
    amygdala: { types: [["amygdala_principal", 1]], cells: 150 },
  };
  // which close-up a region gets (by its brain.json group / name); null: none
  function kindOf(node) {
    if (!node) return null;
    const nm = node.name || "";
    if (/^(LH|RH)_/.test(nm)) return "cortex";
    if (/Caudate|Putamen|Accumbens/.test(nm)) return "striatum";
    if (/Thalamus/.test(nm)) return "thalamus";
    if (/Hippocampus/.test(nm)) return "hippocampus";
    if (/Amygdala/.test(nm)) return "amygdala";
    return null;
  }
  // how many cells of each type fit: <= MAX_CELLS cells and <= budget segments (soma marks included)
  function closeupPlan(kind, morph, budget) {
    const k = KINDS[kind]; if (!k || !morph || !morph.cells) return null;
    budget = Math.min(budget || SEG_BUDGET, SEG_BUDGET);
    const per = k.types.reduce((a, [t, f]) => a + f * ((morph.cells[t] ? morph.cells[t].n_seg : 0) + SOMA_SEGS), 0);
    const n = Math.max(0, Math.min(MAX_CELLS, k.cells, Math.floor(budget / Math.max(1, per))));
    const plan = k.types.filter(([t]) => morph.cells[t]).map(([t, f]) => ({ type: t, n: Math.round(n * f) }));
    let segs = plan.reduce((a, p) => a + p.n * (morph.cells[p.type].n_seg + SOMA_SEGS), 0);
    while (segs > budget) { const p = plan[0]; p.n--; segs -= morph.cells[p.type].n_seg + SOMA_SEGS; }   // rounding
    return { kind, cells: plan.reduce((a, p) => a + p.n, 0), segments: segs, drawCalls: plan.length, plan };
  }
  // soma position of cell i of n in the block (micrometres; y up, pia at the top for cortex)
  function placeCell(kind, type, i, n, rnd) {
    if (kind === "hippocampus")                                    // CA1: somata packed in stratum pyramidale
      return [(rnd() - 0.5) * 2000, (rnd() - 0.5) * 70, (rnd() - 0.5) * 500];
    if (kind === "cortex") {                                       // L2/3 pyramids under the pia, basket cells around
      const y = type === "pyramidal" ? -150 - 650 * rnd() : -100 - 900 * rnd();
      return [(rnd() - 0.5) * 2200, y, (rnd() - 0.5) * 700];
    }
    const s = kind === "striatum" ? 520 : 760;                      // a cube of nucleus
    return [(rnd() - 0.5) * s, (rnd() - 0.5) * s, (rnd() - 0.5) * s];
  }
  function closeup(o) {
    const THREE = o.THREE, morph = o.morph, kind = o.kind, plan = closeupPlan(kind, morph, o.budget);
    if (!plan || !plan.cells) return null;
    const group = new THREE.Group(), rnd = rng(780 + Object.keys(KINDS).indexOf(kind));
    const UM = o.unit || 0.12;                                      // scene units per micrometre
    const uniforms = { uTime: { value: 0 }, uRate: { value: 0 }, uFade: { value: 0 }, uLive: { value: 0 },
                       uSpeed: { value: PULSE_UM_S }, uWidth: { value: PULSE_W_UM }, uUnit: { value: UM } };
    const cells = [], types = [];                                   // cells[k] -> {t: types index, j: instance}
    for (const p of plan.plan) {
      const c = morph.cells[p.type], ns = c.n_seg + SOMA_SEGS, pos = new Float32Array(ns * 6), dist = new Float32Array(ns * 2),
            kd = new Float32Array(ns * 2), r = Math.max(4, c.soma_r);
      pos.set(c.pos.slice(0, c.n_seg * 6));
      for (let i = 0; i < c.n_seg; i++) { dist[2 * i] = c.dist[2 * i]; dist[2 * i + 1] = c.dist[2 * i + 1]; kd[2 * i] = kd[2 * i + 1] = c.kind[i]; }
      for (let a = 0; a < SOMA_SEGS; a++) {                          // the soma: three crossed strokes of its diameter
        const i = c.n_seg + a, o6 = 6 * i, ax = [0, 0, 0]; ax[a] = r;
        pos.set([-ax[0], -ax[1], -ax[2], ax[0], ax[1], ax[2]], o6);
        dist[2 * i] = dist[2 * i + 1] = 0; kd[2 * i] = kd[2 * i + 1] = 0;
      }
      const g = new THREE.InstancedBufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      g.setAttribute("aDist", new THREE.BufferAttribute(dist, 1));
      g.setAttribute("aKind", new THREE.BufferAttribute(kd, 1));
      const off = new Float32Array(p.n * 3), rot = new Float32Array(p.n * 2), sc = new Float32Array(p.n), spk = new Float32Array(p.n).fill(-1e4);
      for (let j = 0; j < p.n; j++) {
        off.set(placeCell(kind, p.type, j, p.n, rnd).map(v => v * UM), 3 * j);
        const a = rnd() * 6.2832;
        rot[2 * j] = Math.cos(a); rot[2 * j + 1] = Math.sin(a);
        sc[j] = (0.85 + 0.3 * rnd()) * (rnd() < 0.5 ? -1 : 1);       // mirrored copies (x only) add variety
        cells.push({ t: types.length, j });
      }
      g.setAttribute("iOff", new THREE.InstancedBufferAttribute(off, 3));
      g.setAttribute("iRot", new THREE.InstancedBufferAttribute(rot, 2));
      g.setAttribute("iScale", new THREE.InstancedBufferAttribute(sc, 1));
      const sa = new THREE.InstancedBufferAttribute(spk, 1); if (sa.setUsage) sa.setUsage(THREE.DynamicDrawUsage);
      g.setAttribute("iSpike", sa);
      g.instanceCount = p.n;
      const mat = new THREE.ShaderMaterial({ uniforms, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
        vertexShader: `
          attribute float aDist; attribute float aKind; attribute vec3 iOff; attribute vec2 iRot; attribute float iScale; attribute float iSpike;
          uniform float uTime; uniform float uRate; uniform float uLive; uniform float uSpeed; uniform float uWidth; uniform float uUnit;
          varying vec3 vCol;
          void main(){
            vec3 p = position * abs(iScale);
            p.x *= sign(iScale);                                          // a mirrored copy: x only, never upside down
            p = vec3(iRot.x * p.x + iRot.y * p.z, p.y, -iRot.y * p.x + iRot.x * p.z);
            vec3 w = p * uUnit + iOff;
            float dt = uTime - iSpike;
            float on = dt >= 0.0 ? 1.0 : 0.0;
            float soma = on * exp(-dt / 0.25);
            float front = dt * uSpeed;
            float pulse = on * exp(-pow((aDist - front) / uWidth, 2.0)) * step(front, aDist + 3.0 * uWidth);
            vec3 col;
            if (aKind < 0.5) col = vec3(0.9, 0.85, 0.75) * (0.45 + 2.6 * soma);                       // soma
            else if (aKind < 1.5) col = vec3(0.55, 0.32, 0.12) * 0.22 + vec3(1.0, 0.9, 0.6) * 4.0 * pulse; // axon
            else {                                                                                   // dendrites
              float glow = uLive * uRate;
              col = mix(vec3(0.22, 0.32, 0.6), vec3(1.0, 0.5, 0.18), glow) * (0.9 + 0.9 * glow)
                    + vec3(1.0, 0.8, 0.5) * 0.9 * soma * exp(-aDist / 40.0);
            }
            vCol = col;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(w, 1.0);
          }`,
        fragmentShader: `uniform float uFade; varying vec3 vCol; void main(){ gl_FragColor = vec4(vCol * 0.42 * uFade, 1.0); }` });
      const lines = new THREE.LineSegments(g, mat);
      lines.frustumCulled = false; lines.name = "closeup-" + p.type;
      group.add(lines);
      types.push({ type: p.type, n: p.n, spk, sa, geom: g, mat });
    }
    // block extent for framing (scene units)
    const box = { min: [1e9, 1e9, 1e9], max: [-1e9, -1e9, -1e9] };
    for (const T of types) { const off = T.geom.getAttribute("iOff").array, c = morph.cells[T.type];
      for (let j = 0; j < T.n; j++) for (let a = 0; a < 3; a++) {
        box.min[a] = Math.min(box.min[a], off[3 * j + a] + c.box[a] * UM); box.max[a] = Math.max(box.max[a], off[3 * j + a] + c.box[3 + a] * UM); } }
    const S = { t0: performance.now(), lastWall: -1e9, gap: 200, prev: 0, rate: 0, region: o.region, fade: 0, on: true, spikes: 0 };
    const clock = now => (now - S.t0) / 1000;
    function onFrame(m) {                                           // a spiking frame: only the close-up region's spikes
      if (!m || m.type !== "spiking" || !m.n3 || m.live === false) return;
      const now = performance.now(), gap = now - S.prev; S.prev = now;
      if (gap > 30 && gap < 2000) S.gap = 0.7 * S.gap + 0.3 * gap;
      S.lastWall = now;
      if (m.n3.rq) { const q = unb64(m.n3.rq); if (q.length > S.region) S.rate = q[S.region]; }
      else if (o.groupRate) S.rate = rateByte(o.groupRate(m)) || S.rate;
      const b = unb64(m.n3.sq), play = Math.min(600, S.gap) / 1000, t = clock(now), dirty = new Set();
      for (let i = 0; i + 2 < b.length; i += 3) {
        if (b[i] !== S.region) continue;
        const c = cells[Math.min(cells.length - 1, Math.floor(b[i + 1] * cells.length / 256))], T = types[c.t];
        T.spk[c.j] = t + (b[i + 2] / 255) * play; dirty.add(T); S.spikes++;
      }
      for (const T of dirty) T.sa.needsUpdate = true;
    }
    function update(now) {
      const live = now - S.lastWall < LIVE_MS;
      uniforms.uTime.value = clock(now); uniforms.uLive.value = live ? 1 : 0;
      const r = S.rate ? Math.max(0, Math.min(1, (S.rate / 255 - 0.42) / 0.44)) : 0;
      uniforms.uRate.value += (r - uniforms.uRate.value) * 0.05;
      S.fade += ((S.on ? 1 : 0) - S.fade) * 0.1; uniforms.uFade.value = S.fade;
    }
    function dispose() { for (const T of types) { T.geom.dispose(); T.mat.dispose(); } }
    function info() { return { kind, region: S.region, cells: plan.cells, segments: plan.segments,
      drawCalls: plan.drawCalls, types: plan.plan.map(p => ({ type: p.type, n: p.n, species: morph.cells[p.type].species,
      id: morph.cells[p.type].nmo_id })), live: performance.now() - S.lastWall < LIVE_MS, spikes: S.spikes,
      spiking: types.reduce((a, T) => a + T.spk.filter(x => x > -1e3).length, 0) }; }
    return { group, onFrame, update, dispose, info, box, plan };
  }

  // level of detail: "brain" (points) or "closeup" (shapes), from the camera distance. Zooming in close on the brain
  // (dist < brainIn) opens a close-up; zooming out of one (dist > its fit distance x OUT) returns to the whole brain.
  const LOD_IN = 95, LOD_OUT = 2.6;
  function lod(mode, dist, fit) {
    if (mode === "closeup") return dist > (fit || 1) * LOD_OUT ? "brain" : "closeup";
    return dist < LOD_IN ? "closeup" : "brain";
  }

  // the caption's spike clause (plain text) for state() -> {recorded, shown}. A frame can arrive with its rates but no
  // spikes when the server's per-viewer budget (3 KB/s, spiking/frames.py) was used up: say so, never "0 of N".
  function spikeLine(st) {
    const rec = st && st.recorded > 0 ? Math.round(st.recorded) : 0, shown = st && st.shown > 0 ? Math.round(st.shown) : 0;
    if (!rec) return "";
    const n = rec.toLocaleString("en-US");
    return shown ? `showing ${shown.toLocaleString("en-US")} of ${n} recorded spikes in the last frame`
                 : `last frame: ${n} spikes recorded, none sent (the stream's 3 KB/s budget was used up)`;
  }

  root.Neurons3D = { create, unb64, rateByte, spikeLine, closeup, closeupPlan, kindOf, lod, SEG_BUDGET, SLOWDOWN, PULSE_UM_S,
                     LOD_IN, LOD_OUT };
})(typeof window !== "undefined" ? window : globalThis);
