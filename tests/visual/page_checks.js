// In-page helpers of the visual QA harness (issue #98, G8). Injected into /room.html?debug after it has loaded; it
// only uses what the page exposes on `window` under ?debug (THREE, scene, camera, controls, renderer, boy, room,
// bones, head, hand, phone, SURF, ANCHOR, actions, current, sim, settle, animate_, pose, penetration, camGoal,
// updateCameraGoal). Everything lives under window.__qa. Nothing here changes the page's own files.
(() => {
  const F = 0.16;                                                   // the floor's top (room.html, build_room.py FY)
  const V = () => new THREE.Vector3();
  const qa = window.__qa = {};
  let hudStyle = null, columnsCache = {};

  // the page's ?debug marker spheres (magenta, SURF positions) are a debug aid, not what viewers see: hidden here
  const MARKERS = new Set();
  qa.hideMarkers = () => { let n = 0; scene.traverse(o => { if (o.isMesh && o.material && o.material.isMeshBasicMaterial && o.material.color &&
    o.material.color.getHex() === 0xff00ff && o.geometry && o.geometry.type === "SphereGeometry") { o.visible = false; MARKERS.add(o); n++; } }); return n; };
  qa.ready = () => ({
    boy: !!window.boy, room: !!window.room, hand: !!window.hand, boot: !document.getElementById("boot"),
    clips: Object.keys(window.actions || {}), mixer: !!window.mixer,
  });

  // ---- stepping and rendering (the page's frame() is frozen with window.FREEZE; these do the work instead)
  qa.step = (dt, n) => { for (let i = 0; i < n; i++) window.animate_(dt); return window.pose(); };
  qa.render = () => {
    scene.traverse(o => { if (o.isLight && o.shadow) o.shadow.needsUpdate = true; });   // the shadow maps are hand-updated
    window.sim(0, 1);
    return renderer.info.render.calls;
  };
  qa.lights = () => {
    const out = {exposure: +renderer.toneMappingExposure.toFixed(3), lights: []};
    scene.traverse(o => { if (o.isLight) out.lights.push({type: o.type, intensity: +o.intensity.toFixed(3), color: "#" + o.color.getHexString()}); });
    return out;
  };
  qa.screenState = () => {                                          // what the page shows on the monitor and where its camera goes
    const m = window.monitor, on = !!(m && m.mesh.material.map);
    window.updateCameraGoal(); const p = camGoal.pos, over = p.distanceTo(new THREE.Vector3(5.2, 5.0, 6.0)) < 0.01;
    return {monitor_on: on, camera: over ? "overview" : p.x < -0.5 && p.z < -0.3 ? "monitor" : "him", goal: p.toArray().map(x => +x.toFixed(2)),
            phone: !!(window.phone && phone.visible), duvet_w: window.DUV ? +DUV.w.toFixed(2) : null, roll: window.ROLL ? +ROLL.a.toFixed(2) : null};
  };
  qa.followCam = () => { window.updateCameraGoal(); camera.position.copy(camGoal.pos); controls.target.copy(camGoal.target); controls.update(); };
  qa.lookFrom = (pos, target) => { camera.position.set(...pos); controls.target.set(...target); controls.update(); };
  // a medium shot of him: candidate positions on a 1.5 m ring at chest height, the first one from his front-right round
  // that is inside the open room and has a clear line of sight to him (a ray against the room's meshes)
  const inRoom = p => p.x > -1.75 && p.z > -1.3 && p.x < 3.5 && p.z < 3.5 && p.y > 0.3 && p.y < 2.3;
  qa.characterCam = () => {
    boy.updateMatrixWorld(true);
    const hips = wp(bones.Hips), hd = wp(head), f = facing(), up = V().set(0, 1, 0);
    const lying = hd.y - hips.y < 0.3, tgt = hips.clone().lerp(hd, lying ? 0.5 : 0.6);
    const meshes = []; room.traverse(m => { if (m.isMesh && m.visible) meshes.push(m); });
    const ray = new THREE.Raycaster(), dir = V();
    const clear = pos => { dir.subVectors(tgt, pos); const d = dir.length(); ray.set(pos, dir.normalize()); ray.far = d - 0.25;
      return ray.intersectObjects(meshes, false).length === 0; };
    const a0 = lying ? Math.atan2(0.55, 0.8) : Math.atan2(f.x, f.z) - 0.6;   // from his front-right (lying: from the bed's open side)
    let pos = null, tried = 0;
    for (const da of [0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 2.6, -2.6, 3.1]) {
      const a = a0 + da, p = tgt.clone().add(V().set(Math.sin(a) * 1.5, lying ? 1.1 : 0.45, Math.cos(a) * 1.5)); tried++;
      if (inRoom(p) && clear(p)) { pos = p; break; }
    }
    if (!pos) { pos = tgt.clone().add(V().set(1.1, 0.9, 1.1)); }        // nothing clear: from the open corner
    camera.position.copy(pos); controls.target.copy(tgt); controls.update();
    return {pos: pos.toArray().map(x => +x.toFixed(3)), target: tgt.toArray().map(x => +x.toFixed(3)), tried};
  };
  // leftovers of an earlier scene on the same page (the dish he was eating stays on the desk until he bins it): hidden,
  // so each scene shows only its own props
  qa.clearFood = () => { let n = 0; for (const o of scene.children) { if (o === room || o === boy || o.name) continue;
    let food = false; o.traverse(m => { if (/^F_/.test(m.name)) food = true; }); if (food && o.visible) { o.visible = false; n++; } } return n; };
  qa.jitter = k => {                                                // a sub-millimetre camera move: z-fighting flickers, geometry does not
    const right = V().setFromMatrixColumn(camera.matrixWorld, 0);
    camera.position.addScaledVector(right, 0.0007 * k); controls.target.addScaledVector(right, 0.0007 * k);
    qa.render();
  };
  qa.canvasRect = () => { const r = renderer.domElement.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
  qa.hud = on => {
    if (!hudStyle) { hudStyle = document.createElement("style"); hudStyle.textContent = "#top,#side,#corner,#dock,#vignette,#away{display:none!important}"; }
    if (on) hudStyle.remove(); else document.head.appendChild(hudStyle);
  };
  qa.info = () => ({
    dpr: window.dpr, size: [renderer.domElement.width, renderer.domElement.height],
    calls: renderer.info.render.calls, triangles: renderer.info.render.triangles,
    textures: renderer.info.memory.textures, geometries: renderer.info.memory.geometries,
    webgl2: renderer.capabilities.isWebGL2, maxAniso: renderer.capabilities.getMaxAnisotropy(),
  });

  // ---- close-up cameras, from the bones and the room's known places (the page's OrbitControls limits apply)
  const facing = () => V().set(Math.sin(boy.rotation.y), 0, Math.cos(boy.rotation.y));
  const wp = b => b.getWorldPosition(V());
  qa.closeup = name => {
    boy.updateMatrixWorld(true);
    const up = V().set(0, 1, 0), f = facing();
    let pos, tgt;
    if (name === "face") {                                            // in front of his face, a little above (walking or standing scenes)
      const h = wp(head), fp = wp(bones.headfront || head);
      const dir = head.localToWorld(V().set(0, 30, 30)).sub(h).setY(0).normalize();
      tgt = fp.clone(); pos = fp.clone().addScaledVector(dir, 0.50).addScaledVector(up, 0.05);
    } else if (name === "hands") {                                    // seated: from his right side, a little in front and above the desk top
      const m = wp(bones.LeftHand).add(wp(bones.RightHand)).multiplyScalar(0.5), right = V().set(f.z, 0, -f.x);
      tgt = m; pos = m.clone().addScaledVector(right, 0.55).addScaledVector(f, 0.22).addScaledVector(up, 0.36);
    } else if (name === "grip") {                                     // the phone in his hand, from beside his head
      const m = phone.visible ? phone.getWorldPosition(V()) : wp(bones.RightHand), hd = wp(head);
      tgt = m; pos = m.clone().add(V().set(0.35, 0.25, 0.45));
    } else if (name === "feet") {
      const m = wp(bones.LeftFoot).add(wp(bones.RightFoot)).multiplyScalar(0.5); m.y = F + 0.04;
      tgt = m; pos = m.clone().addScaledVector(f, 0.55).addScaledVector(up, 0.22);
    } else if (name === "socks") {                                     // the laundry pinch hanger over the bed's head end (build_room.py PH)
      tgt = V().set(-1.745, 1.80, 0.45); pos = V().set(-1.08, 1.92, 0.62);
    } else if (name === "desk") {
      const c = SURF.monitor.c; tgt = V().set(c[0] + 0.1, 1.02, c[2] + 0.35); pos = V().set(-0.45, 1.55, 0.25);
    } else if (name === "bed") {                                       // the bed from its open side, a little above
      tgt = V().set(-1.05, 0.86, 0.87); pos = V().set(0.25, 1.95, 1.35);
    } else if (name === "duvet") {                                     // the duvet's drape and the pillow, close
      tgt = V().set(-1.45, 0.86, 0.75); pos = V().set(-0.65, 1.45, 1.25);
    } else throw new Error("unknown close-up " + name);
    camera.position.copy(pos); controls.target.copy(tgt); controls.update();
    return {pos: pos.toArray().map(x => +x.toFixed(3)), target: tgt.toArray().map(x => +x.toFixed(3))};
  };

  // ---- the character against the room: the page's bed/chair test plus the floor and the desk
  // columns(): the room's static mesh as columns of inside-intervals over a zone (metres, cell size), by vertical rays;
  // computed once per zone (software rasteriser or not, raycasting is CPU work: ~1 s for the desk zone)
  qa.columns = (key, x0, x1, z0, z1, cell = 0.03) => {
    if (columnsCache[key]) return columnsCache[key];
    const st = room.getObjectByName("room_static"); if (!st) return null;
    const meshes = []; st.traverse(m => { if (m.isMesh) meshes.push(m); });
    const sides = meshes.map(m => m.material.side); meshes.forEach(m => { m.material.side = THREE.DoubleSide; });
    const ray = new THREE.Raycaster(), o = V(), nx = Math.ceil((x1 - x0) / cell), nz = Math.ceil((z1 - z0) / cell), cols = [];
    const t0 = performance.now();
    for (let i = 0; i < nx; i++) for (let k = 0; k < nz; k++) {
      o.set(x0 + (i + 0.5) * cell, -0.5, z0 + (k + 0.5) * cell); ray.set(o, new THREE.Vector3(0, 1, 0));
      const hits = [];
      for (const h of ray.intersectObjects(meshes, false)) if (!hits.length || h.point.y - hits[hits.length - 1] > 0.002) hits.push(h.point.y);
      cols[i * nz + k] = hits.length >= 2 ? hits.slice(0, hits.length - (hits.length % 2)) : null;
    }
    meshes.forEach((m, i) => { m.material.side = sides[i]; });
    return columnsCache[key] = {x0, z0, cell, nx, nz, cols, ms: Math.round(performance.now() - t0)};
  };
  qa.body = (every = 2) => {
    let sm; boy.traverse(o => { if (o.isSkinnedMesh) sm = o; }); boy.updateMatrixWorld(true);
    const P = sm.geometry.attributes.position, I = sm.geometry.attributes.skinIndex, W = sm.geometry.attributes.skinWeight, v = V();
    const desk = qa.columns("desk", -1.92, -0.30, -1.47, -0.72);
    const boneOf = i => { let b = 0, bw = 0; for (let k = 0; k < 4; k++) if (W.getComponent(i, k) > bw) { bw = W.getComponent(i, k); b = I.getComponent(i, k); } return sm.skeleton.bones[b].name; };
    const out = {sampled: 0, below_floor: 0, desk: 0, min_y: 9, by: {}, foot_min_y: {Left: 9, Right: 9}};
    for (let i = 0; i < P.count; i += every) {
      sm.getVertexPosition(i, v); v.applyMatrix4(sm.matrixWorld); out.sampled++;
      out.min_y = Math.min(out.min_y, v.y);
      const bn = boneOf(i);
      if (/Foot|ToeBase/.test(bn)) { const s = bn.startsWith("Left") ? "Left" : "Right"; out.foot_min_y[s] = Math.min(out.foot_min_y[s], v.y); }
      if (v.y < F - 0.012) { out.below_floor++; out.by["floor:" + bn] = (out.by["floor:" + bn] || 0) + 1; }
      if (desk) { const ci = Math.floor((v.x - desk.x0) / desk.cell), ck = Math.floor((v.z - desk.z0) / desk.cell);
        const col = ci >= 0 && ci < desk.nx && ck >= 0 && ck < desk.nz && desk.cols[ci * desk.nz + ck];
        if (col) for (let j = 0; j < col.length; j += 2) if (v.y > col[j] + 0.01 && v.y < col[j + 1] - 0.01) { out.desk++; out.by["desk:" + bn] = (out.by["desk:" + bn] || 0) + 1; break; } }
    }
    const pen = window.penetration(every, true);
    out.bed = pen.bed; out.chair = pen.chair; Object.assign(out.by, Object.fromEntries(Object.entries(pen.by).filter(([k]) => k !== "pts")));
    for (const k of ["min_y"]) out[k] = +out[k].toFixed(3);
    out.foot_min_y = {Left: +out.foot_min_y.Left.toFixed(3), Right: +out.foot_min_y.Right.toFixed(3)};
    out.floor_y = F; out.desk_columns_ms = desk && desk.ms;
    return out;
  };

  // ---- props: does each separate object rest on something (a downward ray from just above its lowest point)?
  // gap > 8 mm: floating; the surface under it above its bottom: sunk into it. Wall-hung things are listed, not judged.
  const HANGING = new Set(["headphones", "hangers", "wall_clock", "SURF_lamp", "SURF_monitor", "SURF_window", "shadow_shell"]);
  qa.props = () => {
    const all = []; scene.traverse(m => { if (m.isMesh && m.visible && !m.isSkinnedMesh) all.push(m); });
    const cands = [];
    for (const o of room.children) if (o.name !== "room_static" && !/^SURF_/.test(o.name)) cands.push([o.name, o]);
    scene.children.forEach((o, i) => { if (o !== room && o !== boy && !o.isLight && o.visible && (o.isGroup || o.isMesh) && !o.name) {
      let col = null, n = 0; o.traverse(m => { if (m.isMesh) { n++; col = col || (m.material && m.material.color && "#" + m.material.color.getHexString()); } });
      if (n) cands.push([`scene#${i}(${col})`, o]); } });
    const ray = new THREE.Raycaster(), box = new THREE.Box3(), c = V(), out = [];
    boy.updateMatrixWorld(true); const boyBox = new THREE.Box3().setFromObject(boy).expandByScalar(0.05);
    for (const [name, o] of cands) {
      if (MARKERS.has(o)) continue;
      let skip = false, mat = null; o.traverse(m => { if (m.isMesh && !skip) { const mm = [].concat(m.material)[0]; mat = mat || mm;
        if (mm && (mm.isShaderMaterial || mm.blending === THREE.AdditiveBlending || mm.colorWrite === false)) skip = true; } });
      if (skip) continue;
      o.updateMatrixWorld(true); box.setFromObject(o); if (box.isEmpty()) continue; box.getCenter(c);
      const sz = [box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z];
      if (Math.min(...sz) < 0.006) continue;                           // a plane (a screen, the window's sky): nothing to rest
      let plane = true, n = 0; o.traverse(m => { if (m.isMesh) { n++; if (!(m.geometry && m.geometry.type === "PlaneGeometry")) plane = false; } });
      if (n && plane) continue;                                        // a turned screen plane (its box is thick): still a plane
      if (boyBox.containsPoint(c)) continue;                           // in his hands (chopsticks, the phone, a bag): not resting on anything
      const mine = new Set(); o.traverse(m => mine.add(m));
      const others = all.filter(m => !mine.has(m));
      const sides = others.map(m => m.material.side); others.forEach(m => { m.material.side = THREE.DoubleSide; });
      let best = null;
      for (const [dx, dz] of [[0, 0], [0.35, 0.35], [-0.35, 0.35], [0.35, -0.35], [-0.35, -0.35]]) {
        const sx = c.x + dx * (box.max.x - box.min.x), sz = c.z + dz * (box.max.z - box.min.z);
        ray.set(V().set(sx, box.min.y + 0.05, sz), V().set(0, -1, 0)); ray.far = 3;
        const h = ray.intersectObjects(others, false)[0];
        if (h) { const gap = box.min.y - h.point.y; if (best === null || Math.abs(gap) < Math.abs(best)) best = gap; }
      }
      others.forEach((m, i) => { m.material.side = sides[i]; });
      const r = {name, at: c.toArray().map(x => +x.toFixed(2)), bottom_y: +box.min.y.toFixed(3), size: sz.map(x => +x.toFixed(2)),
                 gap_mm: best === null ? null : Math.round(best * 1000), hanging: HANGING.has(name) || /^SURF_/.test(name)};
      r.verdict = r.hanging ? "hangs" : best === null ? "nothing under it" : best > 0.008 ? "floating" : best < -0.004 ? "sunk" : "ok";
      out.push(r);
    }
    return out;
  };

  // ---- textures: size against the object they cover (texels per metre of its longest side)
  qa.textures = () => {
    const seen = new Map(), box = new THREE.Box3(), s = V();
    scene.traverse(m => {
      if (!m.isMesh || !m.visible) return;
      box.setFromObject(m); box.getSize(s); const dim = Math.max(s.x, s.y, s.z);
      for (const mat of [].concat(m.material)) for (const k of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap"]) {
        const t = mat && mat[k]; if (!t || !t.image) continue;
        const w = t.image.width || t.image.videoWidth || 0, h = t.image.height || 0, key = t.uuid;
        const e = seen.get(key) || {kind: k, size: [w, h], aniso: t.anisotropy, objects: [], max_dim_m: 0, material: mat.name || ""};
        e.objects.push(m.name || m.parent && m.parent.name || "?"); e.max_dim_m = Math.max(e.max_dim_m, dim); seen.set(key, e);
      }
    });
    return [...seen.values()].map(e => ({...e, objects: [...new Set(e.objects)].slice(0, 4), max_dim_m: +e.max_dim_m.toFixed(2),
      texels_per_m: e.max_dim_m > 0 ? Math.round(Math.min(e.size[0], e.size[1]) / e.max_dim_m) : null}));
  };

  // ---- performance: real frames of the page's own loop over `ms` (FREEZE lifted meanwhile), and the character logic alone
  qa.fps = ms => new Promise(res => {
    const r = renderer.render.bind(renderer); let k = 0; renderer.render = (...a) => { k++; r(...a); };
    window.FREEZE = false; const t0 = performance.now();
    setTimeout(() => { window.FREEZE = true; renderer.render = r; res({renders: k, fps: +(k * 1000 / (performance.now() - t0)).toFixed(2)}); }, ms);
  });
  qa.animateMs = (n = 120) => { const t0 = performance.now(); for (let i = 0; i < n; i++) window.animate_(1 / 60); return +((performance.now() - t0) / n).toFixed(3); };
})();
