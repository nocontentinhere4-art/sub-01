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
      uniforms: { uTime: { value: 0 }, uRates: { value: tex }, uSize: { value: o.pointSize || 0.9 }, uScale: { value: 1000 },
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
          vCol = base * (0.35 + 0.65 * rate) + vec3(1.0, 0.86, 0.6) * 2.4 * f + vec3(1.0, 0.5, 0.1) * 0.9 * t.g;
          vA = 0.28 + 0.3 * rate + 0.7 * f + 0.3 * t.g;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = uSize * (1.0 + 2.2 * f + 0.6 * t.g) * uScale / -mv.z;
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
    return { object: points, onFrame, update, resize, setVisible, state, dispose, points: L.N };
  }

  root.Neurons3D = { create, unb64, rateByte };
})(typeof window !== "undefined" ? window : globalThis);
