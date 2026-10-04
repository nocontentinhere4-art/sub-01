// The skin, eyes and hands on G2's final body (room_build/mh/glb/boy_g2.glb on preview/mh-motion; #98, G6).
//
//   dressBody(THREE, root)  ->  info; root = the glTF scene. The skeleton, the rest pose and the vertex order are
//                               left as they are (the clips stay valid): only the skin's material and two vertex
//                               attributes (colour, skinData, handData) change, G2's eye primitive is hidden and mine
//                               (balls, corneas, lash and tear lines, caruncles) are parented to the Head bone.
//
// Everything is computed in the mesh's bind-pose space, so it moves with the skin: no UVs are needed.
import { skinData, makeSkinMaterial, addEyes } from "./skin_eyes.js";

const EYE_K = 0.85;
let BN = s => s;   // a bone's name as GLTFLoader keeps it (it drops the ".": finger1-3.L -> finger1-3L)   // skin_eyes.js: the ball is 0.85 of MakeHuman's helper sphere; data.eyes carries the helper's radius

function bindPositions(THREE, mesh){
  // each bone's bind-pose position in the mesh's frame (from the inverse bind matrices)
  const out = new Map(), m = new THREE.Matrix4();
  mesh.skeleton.bones.forEach((b, i) => {
    m.copy(mesh.skeleton.boneInverses[i]).invert().premultiply(mesh.bindMatrixInverse);
    out.set(b.name, new THREE.Vector3().setFromMatrixPosition(m));
  });
  return out;
}

function eyeCentres(THREE, eyesMesh, posed = false){
  // G2's eye primitive: two balls (each with its cornea and iris parts); the centre and radius from each side's box
  // (the radius is half the box's width and height; the box holds only the ball's front, so the centre sits a radius
  // and the cornea's bulge behind its front)
  const P = eyesMesh.geometry.attributes.position, idx = eyesMesh.geometry.index.array, v = new THREE.Vector3();
  const box = {l: new THREE.Box3(), r: new THREE.Box3()};
  for (const i of idx) { v.fromBufferAttribute(P, i); if (posed) eyesMesh.applyBoneTransform(i, v); box[v.x > 0 ? "l" : "r"].expandByPoint(v); }
  const out = {};
  for (const k of ["l", "r"]) {
    const b = box[k], sz = b.getSize(new THREE.Vector3()), r = (sz.x + sz.y) / 4;
    const c = b.getCenter(new THREE.Vector3()); c.z = b.max.z - 1.08 * r;   // the primitive is the ball's front only
    out[k] = {center: c, radius: r, box: [b.min.toArray(), b.max.toArray()]};
  }
  return out;
}

// the hands: per vertex, where it sits on its finger (see HAND in skin_eyes.js)
function buildHandData(THREE, mesh, bind){
  const g = mesh.geometry, P = g.attributes.position, J = g.attributes.skinIndex, W = g.attributes.skinWeight, n = P.count;
  const bones = mesh.skeleton.bones.map(b => b.name);
  const hd = new Float32Array(n * 4); for (let i = 0; i < n; i++) hd[4 * i + 3] = 1;
  const info = {};
  const v = new THREE.Vector3(), q = new THREE.Vector3();
  for (const side of ["L", "R"]) {
    // the hand's plane (least-variance axis of its vertices) and which way is the back of the hand: the fingers point
    // along f, the thumb is to one side (t); the back is f x t on a right hand, t x f on a left one (mirror images)
    const handBones = new Set(bones.map((nm, i) => [nm, i]).filter(([nm]) => nm.endsWith(side) && /^(finger|metacarpal)/.test(nm) || nm === (side === "L" ? "LeftHand" : "RightHand")).map(([, i]) => i));
    const pts = [];
    for (let i = 0; i < n; i++) { let w = 0; for (let k = 0; k < 4; k++) if (handBones.has(J.getComponent(i, k))) w += W.getComponent(i, k); if (w > 0.5) pts.push(i); }
    const cen = new THREE.Vector3(); pts.forEach(i => cen.add(v.fromBufferAttribute(P, i))); cen.divideScalar(pts.length);
    const cov = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    pts.forEach(i => { v.fromBufferAttribute(P, i).sub(cen); const a = [v.x, v.y, v.z]; for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) cov[r][c] += a[r] * a[c]; });
    const nrm = smallestEigen(cov);
    const f = new THREE.Vector3();
    for (const k of [2, 3, 4, 5]) f.add(bind.get(BN(`finger${k}-3.${side}`)).clone().sub(bind.get(BN(`finger${k}-1.${side}`))));
    f.normalize();
    const t = bind.get(BN(`finger1-3.${side}`)).clone().sub(cen); t.addScaledVector(f, -t.dot(f)).normalize();
    const want = side === "R" ? f.clone().cross(t) : t.clone().cross(f);
    const dorsal = new THREE.Vector3(...nrm); if (dorsal.dot(want) < 0) dorsal.negate();
    info[side] = {centre: cen.clone(), dorsal: dorsal.clone(), fingers: f.clone(), thumb: t.clone(), tips: {}};
    // each finger bone: its axis (head to the next joint, the last one to the tip), its radius (median distance of its
    // vertices from the axis) and its place along the finger (-2 the first phalanx, -1 the middle, 0 the last)
    const seg = {};
    // (and the metacarpals of the four fingers, -3..-2: the back of the hand, for its tendons)
    for (let k = 1; k <= 5; k++) for (let p = (k > 1 ? 0 : 1); p <= 3; p++) {
      const nm = p === 0 ? `metacarpal${k - 1}.${side}` : `finger${k}-${p}.${side}`, bi = bones.indexOf(BN(nm)); if (bi < 0) continue;
      const head = bind.get(BN(nm)), mine = [];
      for (let i = 0; i < n; i++) for (let c = 0; c < 4; c++) if (J.getComponent(i, c) === bi && W.getComponent(i, c) > 0.5) mine.push(i);
      let ax, len;
      // (p = 0: the metacarpal, to its finger's knuckle)
      if (p < 3) { const nx = bind.get(BN(`finger${k}-${p + 1}.${side}`)); ax = nx.clone().sub(head); len = ax.length(); ax.normalize(); }
      else { ax = head.clone().sub(bind.get(BN(`finger${k}-2.${side}`))).normalize(); len = 0; mine.forEach(i => len = Math.max(len, v.fromBufferAttribute(P, i).sub(head).dot(ax))); }
      // the axis through the middle of the finger's section (the joint may sit off its centre)
      const off = new THREE.Vector3(); mine.forEach(i => { v.fromBufferAttribute(P, i).sub(head); off.add(v.addScaledVector(ax, -v.dot(ax))); });
      if (mine.length) off.divideScalar(mine.length);
      const ds = mine.map(i => { v.fromBufferAttribute(P, i).sub(head).sub(off); return v.addScaledVector(ax, -v.dot(ax)).length(); }).sort((a, b) => a - b);
      const lat = dorsal.clone().cross(ax).normalize(), up = ax.clone().cross(lat).normalize();   // up: the back, square to the axis
      seg[bi] = {head: head.clone().add(off), ax, len, rad: p === 0 ? 0.011 : (ds[ds.length >> 1] || 0.007), k: p - 3, lat, up};
      if (p === 3) info[side].tips[k] = head.clone().add(off).addScaledVector(ax, len);
    }
    for (let i = 0; i < n; i++) {
      let w = 0, s = 0, la = 0, dz = 0;
      v.fromBufferAttribute(P, i);
      for (let c = 0; c < 4; c++) {
        const S = seg[J.getComponent(i, c)], wc = W.getComponent(i, c); if (!S || wc <= 0) continue;
        q.copy(v).sub(S.head);
        s += wc * (S.k + q.dot(S.ax) / S.len); la += wc * q.dot(S.lat) / S.rad; dz += wc * q.dot(S.up) / S.rad; w += wc;
      }
      if (w < 0.05) continue;
      hd.set([s / w, la / w, dz / w, 1 - Math.min(1, w)], 4 * i);
    }
  }
  g.setAttribute("handData", new THREE.BufferAttribute(hd, 4));
  return info;
}

// fine body hair: on the forearms (all round, denser on the outer side) and the back of the hands (not the fingers'
// last two phalanges), lying from the elbow toward the hand; hairData = (direction, 1 - density)
function buildHairData(THREE, mesh, bind){
  const g = mesh.geometry, P = g.attributes.position, N = g.attributes.normal, J = g.attributes.skinIndex, W = g.attributes.skinWeight;
  const hd = g.attributes.handData, n = P.count, bones = mesh.skeleton.bones.map(b => b.name);
  const out = new Float32Array(n * 4); for (let i = 0; i < n; i++) out[4 * i + 3] = 1;
  for (const [side, Fa, Ha] of [["L", "LeftForeArm", "LeftHand"], ["R", "RightForeArm", "RightHand"]]) {
    const arm = new Set([Fa, BN(`lowerarm02.${side}`)].map(b => bones.indexOf(b)).filter(i => i >= 0));
    const hand = bones.indexOf(Ha);
    const dir = bind.get(Ha).clone().sub(bind.get(Fa)).normalize();
    const outer = new THREE.Vector3(side === "L" ? 1 : -1, 0.3, 0).normalize(), v = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
      let wa = 0, wh = 0;
      for (let c = 0; c < 4; c++) { const b = J.getComponent(i, c), w = W.getComponent(i, c); if (arm.has(b)) wa += w; if (b === hand) wh += w; }
      const s = hd.getX(i), fg = 1 - hd.getW(i), dz = hd.getZ(i);
      // the back of the hand: the hand bone or a metacarpal, on top; thinning out over the first phalanx
      const back = (wh + (fg > 0 && s < -1.4 ? fg : 0)) * Math.min(1, Math.max(0, (dz - 0.2) / 0.4)) * (fg > 0 ? Math.min(1, Math.max(0, (-1.3 - s) / 0.7)) : 1);
      const side_ = 0.55 + 0.45 * Math.max(0, v.fromBufferAttribute(N, i).dot(outer));
      const d = Math.min(1, wa * side_ + 0.8 * back);
      if (d < 0.02) continue;
      out.set([dir.x, dir.y, dir.z, 1 - d], 4 * i);
    }
  }
  g.setAttribute("hairData", new THREE.BufferAttribute(out, 4));
}

function smallestEigen(A){
  // the eigenvector of the smallest eigenvalue of a symmetric 3x3 (inverse iteration on A + eps)
  const m = A.map((r, i) => r.map((x, j) => x + (i === j ? 1e-9 : 0)));
  const det = (a) => a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
  const inv = (a) => { const d = det(a), c = (r, cc) => { const rr = [0, 1, 2].filter(x => x !== r), cs = [0, 1, 2].filter(x => x !== cc);
    return ((r + cc) % 2 ? -1 : 1) * (a[rr[0]][cs[0]] * a[rr[1]][cs[1]] - a[rr[0]][cs[1]] * a[rr[1]][cs[0]]); };
    return [0, 1, 2].map(i => [0, 1, 2].map(j => c(j, i) / d)); };
  const B = inv(m); let x = [0.3, 0.5, 0.8];
  for (let it = 0; it < 60; it++) { const y = B.map(r => r[0] * x[0] + r[1] * x[1] + r[2] * x[2]); const l = Math.hypot(...y); x = y.map(e => e / l); }
  return x;
}

export function dressBody(THREE, root, {iris = [0.24, 0.13, 0.06]} = {}){
  BN = THREE.PropertyBinding.sanitizeNodeName;
  let skin, eyes;
  root.traverse(o => { if (o.isSkinnedMesh) { if (o.material.name === "eyes") eyes = o; else if (o.material.name === "skin") skin = o; } });
  const bind = bindPositions(THREE, skin);
  const E = eyeCentres(THREE, eyes);
  // the skin's regions from the face's landmarks, computed in the head's frame (origin at the Head bone, as head.json)
  const O = bind.get("Head"), P = skin.geometry.attributes.position, n = P.count;
  const shifted = new Float32Array(n * 3), headOnly = [];
  for (let i = 0; i < n; i++) {
    const x = P.getX(i) - O.x, y = P.getY(i) - O.y, z = P.getZ(i) - O.z;
    shifted.set([x, y, z], 3 * i);
    if (y > E.l.center.y - O.y - 0.13 && Math.abs(x) < 0.11) headOnly.push(x, y, z);   // the head (the nose, the lips, the ears)
  }
  const eyesRel = {}; for (const k of ["l", "r"]) eyesRel[k] = {center: E[k].center.clone().sub(O).toArray(), radius: E[k].radius / EYE_K};
  const tmp = new THREE.BufferGeometry(); tmp.setAttribute("position", new THREE.BufferAttribute(shifted, 3));
  const L = skinData(THREE, tmp, {position: headOnly, eyes: eyesRel});
  skin.geometry.setAttribute("color", tmp.attributes.color);
  skin.geometry.setAttribute("skinData", tmp.attributes.skinData);
  const hands = buildHandData(THREE, skin, bind);
  // the fingers are thin: light behind them glows red through (skinData.x, the translucency mask)
  { const sd = skin.geometry.attributes.skinData, hd = skin.geometry.attributes.handData;
    for (let i = 0; i < n; i++) { const fg = 1 - hd.getW(i), s = hd.getX(i);
      if (fg > 0 && s > -2.2) sd.setX(i, Math.max(sd.getX(i), 0.55 * fg * Math.min(1, (s + 2.2) / 0.6))); } }
  buildHairData(THREE, skin, bind);
  skin.material = makeSkinMaterial(THREE);
  { const u = skin.material.userData.uniforms;
    u.uEyeL.value.set(...E.l.center.toArray(), E.l.radius); u.uEyeR.value.set(...E.r.center.toArray(), E.r.radius); }
  // my eyes in place of G2's, built in the skin's bind frame and then moved under the Head bone
  eyes.visible = false;
  const group = new THREE.Group(); group.name = "g6_eyes";
  // the eyes, lashes and tear lines go where the lids are in the rest pose (G2's rest pose moves the lid bones, so
  // the bind-pose lids are not where they render): margins and eye centres from the skinned positions, then moved
  // under the Head bone. Only the skin's own vertices: the eye primitive shares the vertex buffer.
  root.updateMatrixWorld(true); skin.skeleton.update();
  const Ep = eyeCentres(THREE, eyes, true), eyesPosed = {};
  for (const k of ["l", "r"]) eyesPosed[k] = {center: Ep[k].center.toArray(), radius: Ep[k].radius / EYE_K};
  const used = [...new Set(skin.geometry.index.array)], skinP = new Float32Array(used.length * 3), pv = new THREE.Vector3();
  used.forEach((i, j) => { pv.fromBufferAttribute(P, i); skin.applyBoneTransform(i, pv); skinP.set([pv.x, pv.y, pv.z], 3 * j); });
  const remap = new Map(used.map((i, j) => [i, j])), sIdx = Array.from(skin.geometry.index.array, i => remap.get(i));
  const loops = addEyes(THREE, group, new THREE.BufferAttribute(skinP, 3), eyesPosed, {iris, index: sIdx});
  skin.add(group);
  root.updateMatrixWorld(true);
  const headBone = skin.skeleton.bones.find(b => b.name === "Head");
  for (const c of [...group.children]) headBone.attach(c);
  return {skin, eyes: Ep, eyesBind: E, landmarks: L, hands, lidLoops: loops, headOrigin: O, cornea: group.userData.cornea, tear: group.userData.tear};
}
