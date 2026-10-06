// Contact checks for the room upgrade (preview/room-upgrade): his skin against the desk chair, the keyboard, the mouse and
// the game controller, vertex by vertex, frame by frame, in the page's own states (?debug: act(), live(), variant()).
// Each object is turned into columns of inside-intervals in its own frame (vertical rays every CELL metres through its
// closed meshes), so a point is inside when it lies between an entry and the next exit under/over it. A chair that is not
// closed (the owner's Tripo chair) is tested through a signed distance grid instead (--chair-sdf, tests/visual/chair_sdf.py). Run by
// tests/visual/contacts.py; it reports, per scenario, every penetrating (vertex, frame) with its depth and its bone.
(() => {
  const CELL = 0.005, EPS = 0.0005;
  const objs = {};
  const dbg = () => window.roomDbg ? roomDbg() : {chairNode: () => room.getObjectByName("chair")};   // (main: the room's own node)
  function columns(name, node) { const o = columnsOf(node, node, name); if (o) objs[name] = o; return o; }
  function columnsOf(src, node, name = "chair") {        // src's meshes as inside-intervals in node's own frame
    node.updateMatrixWorld(true);
    const meshes = []; src.traverse(m => { if (m.isMesh && m.visible && !/_contact$/.test(m.name)) meshes.push(m); });
    if (!meshes.length) return null;
    const inv = node.matrixWorld.clone().invert(), bb = new THREE.Box3(), v = new THREE.Vector3();
    for (const m of meshes) { const P = m.geometry.attributes.position; m.updateMatrixWorld(true);
      for (let i = 0; i < P.count; i++) bb.expandByPoint(v.fromBufferAttribute(P, i).applyMatrix4(m.matrixWorld).applyMatrix4(inv)); }
    const sides = meshes.map(m => m.material.side); meshes.forEach(m => { m.material.side = THREE.DoubleSide; });
    const nx = Math.ceil((bb.max.x - bb.min.x) / CELL) + 1, nz = Math.ceil((bb.max.z - bb.min.z) / CELL) + 1, cols = new Array(nx * nz);
    const ray = new THREE.Raycaster(), o = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0).transformDirection(node.matrixWorld);
    let odd = 0;
    for (let i = 0; i < nx; i++) for (let k = 0; k < nz; k++) {
      o.set(bb.min.x + i * CELL, bb.min.y - 0.05, bb.min.z + k * CELL).applyMatrix4(node.matrixWorld); ray.set(o, up);
      const ys = [];
      for (const h of ray.intersectObjects(meshes, false)) { const y = h.point.clone().applyMatrix4(inv).y; if (!ys.length || y - ys[ys.length - 1] > EPS) ys.push(y); }
      if (ys.length % 2) odd++;
      // the chair (closed solids): entry / exit pairs; the desk things: the solid envelope from the lowest hit to the
      // highest (fingers come from above; their keycaps and shells are open underneath)
      cols[i * nz + k] = ys.length < 2 ? null : name === "chair" ? ys.slice(0, ys.length - (ys.length % 2)) : [ys[0], ys[ys.length - 1]];
    }
    meshes.forEach((m, i) => { m.material.side = sides[i]; });
    return {node, x0: bb.min.x, z0: bb.min.z, nx, nz, cols, odd, inv: new THREE.Matrix4()};
  }
  function inside(o, p) {                                // depth (m) of a world point inside the object, else 0
    if (o.sdf) { const g = o.sdf, u = p.clone().applyMatrix4(o.inv);   // (a signed distance grid, mm, in the chair's frame)
      const i = Math.round((u.x - g.lo[0]) / g.step), j = Math.round((u.y - g.lo[1]) / g.step), k = Math.round((u.z - g.lo[2]) / g.step);
      if (i < 0 || j < 0 || k < 0 || i >= g.dims[0] || j >= g.dims[1] || k >= g.dims[2]) return 0;
      const d = g.data[(i * g.dims[1] + j) * g.dims[2] + k]; return d < -g.tol ? -d / 1000 : 0; }
    if (o.subs) { let d = 0; for (const s of o.subs) { s.inv.copy(o.inv); d = Math.max(d, inside(s, p)); } return d; }
    const u = p.clone().applyMatrix4(o.inv), i = Math.round((u.x - o.x0) / CELL), k = Math.round((u.z - o.z0) / CELL);
    if (i < 0 || k < 0 || i >= o.nx || k >= o.nz) return 0;
    const c = o.cols[i * o.nz + k]; if (!c) return 0;
    for (let j = 0; j < c.length; j += 2) if (u.y > c[j] && u.y < c[j + 1]) return Math.min(u.y - c[j], c[j + 1] - u.y);
    return 0;
  }
  const HAND = /hand|finger|thumb|index|middle|ring|pinky|metacarpal|wrist|palm/i;
  const HEAD = /head|neck|jaw|eye|nose|lip|tongue|teeth|chin|skull/i;   // (not "ear": it matches ForeArm)
  // the tea bottle he picks up and drinks from: his hand holds it, so it is tested against his head as well as his hands
  const takes = (name, b) => name === "tea_bottle" ? (HAND.test(b) || HEAD.test(b)) : HAND.test(b);
  function skins() { const s = []; boy.traverse(o => { if (o.isSkinnedMesh && o.visible) s.push(o); }); return s; }
  function check(res, frame, every = 1) {             // one frame: every skinned vertex against every object
    boy.updateMatrixWorld(true);
    for (const o of Object.values(objs)) { o.node.updateMatrixWorld(true); o.inv.copy(o.node.matrixWorld).invert(); }
    const v = new THREE.Vector3();
    for (const sm of skins()) {
      const P = sm.geometry.attributes.position, I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight;
      const bone = i => { let b = 0, bw = -1; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > bw) { bw = W.getComponent(i, k); b = I.getComponent(i, k); } return sm.skeleton.bones[b].name; };
      for (let i = 0; i < P.count; i += every) {
        sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld); res.samples++;
        for (const [name, o] of Object.entries(objs)) {
          if (name !== "chair" && !takes(name, bone(i))) continue;        // (hands only, against the desk things)
          const d = inside(o, v); if (d <= 0) continue;
          const key = name + ":" + bone(i), r = res.hits[key] = res.hits[key] || {n: 0, verts: new Set(), max: 0, frames: new Set()};
          r.n++; r.verts.add(sm.name + "#" + i); r.max = Math.max(r.max, d); r.frames.add(frame);
        }
      }
    }
  }
  window.__contacts = {
    build() {
      const D = dbg(), ch = D.chairNode(), keep = ch && [ch.position.clone(), ch.rotation.y];
      // the chair: one set of columns per closed part (its parts overlap where they join: parity holds within each)
      if (ch && window.__chairSDF) { const g = window.__chairSDF, b = atob(g.b64), a = new Int8Array(b.length);
        for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i) << 24 >> 24;
        objs.chair = {node: ch, sdf: {lo: g.lo, step: g.step, dims: g.dims, data: a, tol: g.tol}, odd: 0, nx: g.dims[0] * g.dims[1] * g.dims[2], nz: 1, inv: new THREE.Matrix4()}; }
      else if (ch) { const p = new THREE.Vector3(), r = D.chairAt ? D.chairAt(0, p) : (p.copy(ch.position), ch.rotation.y);   // (columns in its own frame) ch.position.copy(p); ch.rotation.y = r; ch.updateMatrixWorld(true);
        const subs = []; for (const c of ch.children) { const prev = c.parent; const o = columnsOf(c, ch); if (o) subs.push(o); }
        objs.chair = {node: ch, subs, odd: subs.reduce((a, s) => a + s.odd, 0), nx: subs.reduce((a, s) => a + s.nx * s.nz, 0), nz: 1, inv: new THREE.Matrix4()};
        ch.position.copy(keep[0]); ch.rotation.y = keep[1]; ch.updateMatrixWorld(true); }
      for (const n of ["keyboard", "mouse", "controller", "tea_bottle"]) { const o = scene.getObjectByName(n); if (o) columns(n, o); }
      return Object.fromEntries(Object.entries(objs).map(([k, o]) => [k, {cells: o.nx * o.nz, odd_rays: o.odd}]));
    },
    // run a scenario: setup() then n frames of 1/30 s, checking every `stride` frames
    run(label, setup, seconds, stride = 2, every = 1) {
      const res = {label, samples: 0, frames: 0, hits: {}};
      setup();
      const n = Math.round(seconds * 30);
      for (let f = 0; f < n; f++) { animate_(1 / 30); if (f % stride === 0) { check(res, f, every); res.frames++; } }
      const hits = Object.fromEntries(Object.entries(res.hits).map(([k, r]) => [k, {samples: r.n, vertices: r.verts.size, frames: r.frames.size, max_mm: +(r.max * 1000).toFixed(1)}]));
      return {label, frames: res.frames, samples: res.samples, hits, at: pose().at, clip: pose().clip};
    },
    // where his skin goes in the chair's frame: 5 mm voxels (keys "i,j,k" from the origin), each with a bit mask of the
    // body regions in it (1 hands, 2 arms, 4 head, 8 torso, 16 legs), within 0.5 m of the chair's pivot axis
    occupy(setup, seconds, stride = 2, every = 1, occ = {}) {
      setup(); const D = dbg(), v = new THREE.Vector3(), u = new THREE.Vector3(), n = Math.round(seconds * 30), inv = new THREE.Matrix4();
      const region = b => /finger|metacarpal|Hand|thumb/i.test(b) ? 1 : /Arm|lowerarm|upperarm|shoulder|clavicle/i.test(b) ? 2
        : /Head|neck|jaw|eye|tongue|ear/i.test(b) ? 4 : /Leg|leg|Foot|Toe|toe/.test(b) ? 16 : 8;
      for (let f = 0; f < n; f++) { animate_(1 / 30); if (f % stride) continue;
        const ch = D.chairNode(); ch.updateMatrixWorld(true); inv.copy(ch.matrixWorld).invert(); boy.updateMatrixWorld(true);
        for (const sm of skins()) { const P = sm.geometry.attributes.position, I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight;
          for (let i = 0; i < P.count; i += every) { sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld); u.copy(v).applyMatrix4(inv);
            if (Math.abs(u.x) > 0.5 || Math.abs(u.z) > 0.5 || u.y > 1.5) continue;
            let b = 0, bw = -1; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > bw) { bw = W.getComponent(i, k); b = I.getComponent(i, k); }
            const key = Math.round(u.x / 0.005) + "," + Math.round(u.y / 0.005) + "," + Math.round(u.z / 0.005);
            occ[key] = (occ[key] || 0) | region(sm.skeleton.bones[b].name); } } }
      return occ;
    },
    objs,
  };
})();
