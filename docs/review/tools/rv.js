// G23 review helpers, injected into /room.html?debug after the harness's page_checks.js
(() => {
  const F = 0.16, V = () => new THREE.Vector3(), R = window.__rv = {};
  const allBones = () => { const s = new Map(); boy.traverse(o => { if (o.isBone) s.set(o.name, o); }); return s; };
  R.bones = () => [...allBones().keys()];
  const find = re => { for (const [n, b] of allBones()) if (re.test(n)) return b; return null; };
  const B = {
    neck: () => find(/^(mixamorig:?)?Neck$|^neck01$|^neck$/i) || find(/neck/i),
    head: () => find(/^(mixamorig:?)?Head$|^head$/i),
    lfoot: () => find(/^(mixamorig:?)?LeftFoot$|^foot\.L$/i), rfoot: () => find(/^(mixamorig:?)?RightFoot$|^foot\.R$/i),
    lhand: () => find(/^(mixamorig:?)?LeftHand$|^wrist\.L$|^hand\.L$/i), rhand: () => find(/^(mixamorig:?)?RightHand$|^wrist\.R$|^hand\.R$/i),
    larm: () => find(/^(mixamorig:?)?LeftArm$|^upperarm01\.L$|^upper_arm\.L$/i), rarm: () => find(/^(mixamorig:?)?RightArm$|^upperarm01\.R$|^upper_arm\.R$/i),
  };
  R.which = () => Object.fromEntries(Object.entries(B).map(([k, f]) => [k, f() ? f().name : null]));
  const wp = b => { boy.updateMatrixWorld(true); return b.getWorldPosition(V()); };
  const facing = () => { const h = wp(B.head() || B.neck()), n = wp(B.neck()); const f = V(); const q = new THREE.Quaternion(); boy.getWorldQuaternion(q); f.set(0, 0, 1).applyQuaternion(q).setY(0).normalize(); return f; };
  // cam(part, az, dist, up): orbit around a body part; az in radians relative to his facing (0 = in front)
  R.cam = (part, az, dist, up, fov) => {
    let t;
    if (part === "feet") { t = wp(B.lfoot()).add(wp(B.rfoot())).multiplyScalar(0.5); t.y = Math.max(F + 0.05, t.y - 0.03); }
    else if (part === "lfoot" || part === "rfoot") { t = wp(B[part]()); t.y -= 0.03; }
    else if (part === "neck") { t = wp(B.neck()).lerp(wp(B.head()), 0.25); }
    else t = wp(B[part]());
    const f = facing(), r = V().set(f.z, 0, -f.x);
    const d = f.clone().multiplyScalar(Math.cos(az)).addScaledVector(r, Math.sin(az));
    const pos = t.clone().addScaledVector(d, dist * Math.cos(up)).add(V().set(0, dist * Math.sin(up), 0));
    if (fov) { camera.fov = fov; camera.updateProjectionMatrix(); }
    camera.position.copy(pos); controls.target.copy(t); controls.update();
    return {pos: pos.toArray().map(x => +x.toFixed(3)), t: t.toArray().map(x => +x.toFixed(3))};
  };
  R.resetFov = () => { camera.fov = R._fov0 || camera.fov; camera.updateProjectionMatrix(); };
  R._fov0 = camera.fov;
  // hide everything but him (for clean neck/arm checks), and back
  R.solo = on => { const keep = new Set(); boy.traverse(o => keep.add(o)); scene.traverse(o => { if (o.isMesh && !keep.has(o)) { if (on) { o.userData._v = o.visible; o.visible = false; } else if (o.userData._v !== undefined) { o.visible = o.userData._v; delete o.userData._v; } } }); };
  // per-foot lowest vertex over the floor (visible skinned meshes of him), metres; also which meshes visible
  R.soles = () => { boy.updateMatrixWorld(true); const v = V(), out = {L: 9, R: 9};
    const lf = wp(B.lfoot()), rf = wp(B.rfoot());
    boy.traverse(o => { if (!o.isSkinnedMesh || !o.visible) return; const P = o.geometry.attributes.position;
      for (let i = 0; i < P.count; i += 2) { o.getVertexPosition(i, v).applyMatrix4(o.matrixWorld); if (v.y > F + 0.25) continue;
        const dl = v.distanceTo(lf), dr = v.distanceTo(rf); if (Math.min(dl, dr) > 0.2) continue; const s = dl < dr ? "L" : "R"; if (v.y < out[s]) out[s] = v.y; } });
    return {L: +((out.L - F) * 100).toFixed(2), R: +((out.R - F) * 100).toFixed(2)}; };
  R.meshes = () => { const a = []; boy.traverse(o => { if (o.isSkinnedMesh || o.isMesh) a.push([o.name, o.visible, o.geometry.attributes.position.count]); }); return a; };
  R.clip = () => { const p = pose(); return {at: p.at, clip: p.clip, step: p.step && p.step.k}; };
})();
