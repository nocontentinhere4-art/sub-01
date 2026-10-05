// The face of the dressed G2 character (#98, G6; preview/room-mh's web/room/boy.glb = clothes-mh's boy_g2_dressed.glb):
// the skin, the eyes and lashes from preview/skin_eyes (body.js: dressBody), plus eyebrows as real strands, on the
// skinned body without touching its skeleton, rest pose or vertex order.
//
//   dressFace(THREE, root)  ->  info (dressBody's, plus brows and the lid bones found)
import { dressBody } from "../skin_eyes/body.js";

// the eyebrows: thin tapered ribbons rooted on the skin along each brow's arc (thicker at the head, thinning to the
// tail), the hairs at the head pointing up, along the body outward and a little up, at the tail outward and down;
// lying close to the skin (the root's normal from the skin under it), each a little curved and uneven
function browStrands(THREE, skinMesh, eye, side, {count = 950, colour = [0.022, 0.015, 0.011]} = {}){
  const ray = new THREE.Raycaster(), pos = [], idx = [], col = [];
  const rnd = (a) => { const x = Math.sin(a * 127.1 + side * 311.7) * 43758.5453; return x - Math.floor(x); };
  const C = eye.center, r = eye.radius, s = Math.sign(C.x);                  // s: +1 his left (x > 0)
  const SEG = 4;
  for (let n = 0; n < count; n++) {
    // u along the brow from its head (over the inner corner) to its tail; v across it
    // (straight and low, a man's: a slight rise to the body, the tail a little down; full at the head, thin at the tail;
    // across it the roots crowd the middle and thin toward the edges, so no line is drawn round it)
    const u = Math.pow(rnd(n), 0.9), v = Math.max(-1.3, Math.min(1.3, (rnd(n + 77) + rnd(n + 78) + rnd(n + 79) - 1.5) / 0.75));
    const x = C.x + s * (-0.0185 + 0.047 * u);
    const yc = C.y + 0.0200 + 0.0022 * Math.sin(Math.PI * Math.min(1, u * 1.2)) - 0.0032 * Math.max(0, u - 0.72) / 0.28;
    const halfH = 0.0044 * (1 - 0.62 * u);
    if (rnd(n + 13) > 1 - 0.45 * Math.max(0, u - 0.7) / 0.3) continue;      // the tail thins out
    const y = yc + v * halfH;
    // the skin under it: a ray from the front
    ray.set(new THREE.Vector3(x, y, C.z + 0.08), new THREE.Vector3(0, 0, -1));
    const hit = ray.intersectObject(skinMesh, false)[0]; if (!hit) continue;
    const p0 = hit.point, nrm = hit.face.normal.clone().transformDirection(skinMesh.matrixWorld);
    // the hair's direction: up at the head, outward-up along the body, outward-down at the tail, plus a little scatter
    const a = (u < 0.2 ? 80 - 260 * u : u < 0.7 ? 24 - 20 * (u - 0.2) : 14 - 70 * (u - 0.7)) + (rnd(n + 5) - 0.5) * 24 - 16 * v * (u < 0.3 ? 1 : 0.4);
    const ang = THREE.MathUtils.degToRad(a);
    const d = new THREE.Vector3(s * Math.cos(ang), Math.sin(ang), 0);
    d.addScaledVector(nrm, -d.dot(nrm)).normalize();                          // along the skin
    const L = (0.0060 + 0.003 * rnd(n + 9)) * (1 - 0.25 * u), w = 0.00013 * (0.8 + 0.4 * rnd(n + 3));   // (thicker than real: the room's distance)
    const lift = nrm.clone().multiplyScalar(0.0006 + 0.0006 * rnd(n + 21));
    const p1 = p0.clone().addScaledVector(d, L * 0.5).add(lift), p2 = p0.clone().addScaledVector(d, L).addScaledVector(nrm, 0.0003);
    const side3 = new THREE.Vector3().crossVectors(d, nrm).normalize();
    const base = pos.length / 3, shade = 0.75 + 0.5 * rnd(n + 31);
    for (let k = 0; k <= SEG; k++) {
      const t = k / SEG, A = (1 - t) * (1 - t), B = 2 * t * (1 - t), Cq = t * t;
      const q = new THREE.Vector3().addScaledVector(p0, A).addScaledVector(p1, B).addScaledVector(p2, Cq).addScaledVector(nrm, 0.0001);
      const hw = w * (1 - 0.8 * t) / 2;
      pos.push(q.x - side3.x * hw, q.y - side3.y * hw, q.z - side3.z * hw, q.x + side3.x * hw, q.y + side3.y * hw, q.z + side3.z * hw);
      for (let e = 0; e < 2; e++) col.push(colour[0] * shade, colour[1] * shade, colour[2] * shade);
      if (k < SEG) { const o = base + 2 * k; idx.push(o, o + 1, o + 2, o + 1, o + 3, o + 2); }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
}

// which bones move the skin round the eyes (the lids): the skin vertices within 2.2 radii of each eye's centre whose
// weight to a bone other than the head's is over 0.3, by bone
function lidBones(THREE, skin, E){
  const P = skin.geometry.attributes.position, J = skin.geometry.attributes.skinIndex, W = skin.geometry.attributes.skinWeight;
  const names = skin.skeleton.bones.map(b => b.name), out = {}, v = new THREE.Vector3();
  for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i);
    const near = ["l", "r"].some(k => v.distanceTo(E[k].center) < E[k].radius * 2.2); if (!near) continue;
    for (let c = 0; c < 4; c++) { const w = W.getComponent(i, c), nm = names[J.getComponent(i, c)];
      if (w > 0.3 && nm !== "Head") out[nm] = (out[nm] || 0) + 1; } }
  return out;
}

// a more adult face (the coordinator, for the owner: MakeHuman's reads young and round): a firmer jaw and chin, a little
// more cheekbone, less fat in the lower cheek, a firmer nose bridge. Displacements of the face's vertices only, in the
// mesh's bind space, each a Gaussian round a point placed from the eye centres (G2's eye primitive); the neck (below
// the jaw), the ears, the skull and the eyes keep their places, so the hair and the clothes stay valid. No vertex is
// added, removed or reordered; no bone or weight changes. Returns {index: [dx, dy, dz]} for G2 to bake.
const FACE_SHAPE = [   // [x (mirrored), y, z] from the eye centres' midpoint, sigma, [dx (outward), dy, dz]
  [[0, -0.115, 0.010], 0.014, [0, -0.003, 0.004]],              // the chin: forward and a little down
  [[0.056, -0.100, -0.075], 0.016, [0.005, -0.002, 0]],         // the jaw's angle: wider
  [[0.046, -0.108, -0.020], 0.015, [0.003, -0.0015, 0]],        // the jawline between: firmer
  [[0.042, -0.065, -0.005], 0.013, [-0.0025, 0, -0.002]],       // the lower cheek: less fat
  [[0.047, -0.020, -0.020], 0.011, [0.002, 0, 0.0015]],         // the cheekbone: a little more
  [[0, -0.004, 0.017], 0.008, [0, 0, 0.0015]],                  // the nose bridge
];
function faceShape(THREE, skin, eyes, amount = 1){
  const g = skin.geometry, P = g.attributes.position, used = new Set(g.index.array), eyeV = new Set(eyes.geometry.index.array);
  const box = new THREE.Box3(), v = new THREE.Vector3(); for (const i of eyeV) box.expandByPoint(v.fromBufferAttribute(P, i));
  const M = box.getCenter(new THREE.Vector3()); M.x = 0; M.z = box.max.z - 0.013;            // between the eye centres
  const sm = (a, b, t) => { const k = Math.min(1, Math.max(0, (t - a) / (b - a))); return k * k * (3 - 2 * k); };
  const delta = {}, w = new Float32Array(P.count);
  for (const i of used) { if (eyeV.has(i)) continue;
    v.fromBufferAttribute(P, i); const q = v.clone().sub(M), s = Math.sign(q.x) || 1;
    const guard = sm(-0.135, -0.11, q.y) * (1 - sm(0.07, 0.085, Math.abs(q.x)))           // the neck, the ears
      * Math.min(1, Math.min(...[1, -1].map(e => v.distanceTo(new THREE.Vector3(e * (box.max.x - 0.012), M.y, M.z)))) / 0.02);   // the eyes (their centres)
    if (guard <= 0) continue;
    const d = [0, 0, 0];
    for (const [[cx, cy, cz], sg, [dx, dy, dz]] of FACE_SHAPE) {
      const k = Math.exp(-((Math.abs(q.x) - cx) ** 2 + (q.y - cy) ** 2 + (q.z - cz) ** 2) / (2 * sg * sg));   // (mirrored: |x|)
      d[0] += s * dx * k; d[1] += dy * k; d[2] += dz * k;
    }
    const f = guard * amount, m = Math.hypot(...d) * f; if (m < 1e-5) continue;
    P.setXYZ(i, v.x + d[0] * f, v.y + d[1] * f, v.z + d[2] * f); w[i] = m;
    delta[i] = d.map(x => +(x * f).toFixed(6));
  }
  P.needsUpdate = true;
  // the normals of the moved vertices (and round them) from the new shape
  const tmp = new THREE.BufferGeometry(); tmp.setAttribute("position", P); tmp.setIndex(g.index); tmp.computeVertexNormals();
  const N = g.attributes.normal, N2 = tmp.attributes.normal;
  for (const i of used) if (w[i] > 0 || delta[i]) N.setXYZ(i, N2.getX(i), N2.getY(i), N2.getZ(i));
  N.needsUpdate = true; g.computeBoundingSphere();
  return delta;
}
// relaxed upper lids: of the lid bones (orbicularis03/04), the one whose vertices sit above the eye is turned so they
// come down ~0.6 mm (the sign and size from a test turn), before the lashes and the tear lines are fitted to the lids
function relaxLids(THREE, skin, eyes, drop = 0.0006){
  const g = skin.geometry, P = g.attributes.position, J = g.attributes.skinIndex, W = g.attributes.skinWeight, bones = skin.skeleton.bones;
  const box = new THREE.Box3(), v = new THREE.Vector3(); for (const i of new Set(eyes.geometry.index.array)) box.expandByPoint(v.fromBufferAttribute(P, i));
  const eyeY = box.getCenter(v).y, done = [];
  for (const side of ["L", "R"]) {
    let best = null;
    for (const nm of [`orbicularis03${side}`, `orbicularis04${side}`]) { const bi = bones.findIndex(b => b.name === nm); if (bi < 0) continue;
      const ids = []; for (let i = 0; i < P.count; i++) for (let c = 0; c < 4; c++) if (J.getComponent(i, c) === bi && W.getComponent(i, c) > 0.3) ids.push(i);
      let y = 0; for (const i of ids) y += v.fromBufferAttribute(P, i).y; y /= Math.max(1, ids.length);
      if (y > eyeY && (!best || y > best.y)) best = {bone: bones[bi], ids, y}; }
    if (!best) continue;
    const meanY = () => { skin.skeleton.update(); let y = 0; for (const i of best.ids) { v.fromBufferAttribute(P, i); skin.applyBoneTransform(i, v); y += v.y; } return y / best.ids.length; };
    const b = best.bone, q0 = b.quaternion.clone(); skin.parent.updateMatrixWorld(true);
    const y0 = meanY(); b.rotateX(0.1); b.updateMatrixWorld(true); const y1 = meanY(); b.quaternion.copy(q0);
    const per = (y1 - y0) / 0.1; if (Math.abs(per) < 1e-5) continue;
    b.rotateX(-drop / per); b.updateMatrixWorld(true);                        // the turn that lowers the lid by `drop`
    done.push([b.name, +(-drop / per).toFixed(3)]);
  }
  skin.skeleton.update();
  return done;
}

export function dressFace(THREE, root, opts = {}){
  let skin0, eyes0; root.traverse(o => { if (o.isSkinnedMesh) { if (o.material.name === "eyes") eyes0 = o; else if (o.material.name === "skin") skin0 = o; } });
  const shape = opts.shape === false ? {} : faceShape(THREE, skin0, eyes0, opts.shape || 1.4);
  root.updateMatrixWorld(true);
  const lids = relaxLids(THREE, skin0, eyes0);
  root.updateMatrixWorld(true);
  const info = dressBody(THREE, root, opts);
  info.shapeDelta = shape; info.lidsRelaxed = lids;
  const skin = info.skin, E = info.eyes;                                 // E: the eye centres in the skinned (rest) pose
  // a static copy of the skin in its rest pose, to root the brows on (the skinned mesh raycasts slowly)
  root.updateMatrixWorld(true);
  const g = skin.geometry, P = g.attributes.position, pv = new THREE.Vector3(), rest = new Float32Array(P.count * 3);
  for (let i = 0; i < P.count; i++) { pv.fromBufferAttribute(P, i); skin.applyBoneTransform(i, pv); rest.set([pv.x, pv.y, pv.z], 3 * i); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(rest, 3)); sg.setIndex(g.index);
  const stat = new THREE.Mesh(sg, new THREE.MeshBasicMaterial({side: THREE.DoubleSide}));
  stat.matrixWorld.identity(); stat.matrixAutoUpdate = false;
  const browMat = new THREE.MeshStandardMaterial({vertexColors: true, roughness: 0.55, side: THREE.DoubleSide});
  const headBone = skin.skeleton.bones.find(b => b.name === "Head"), brows = [];
  for (const [k, side] of [["l", 1], ["r", -1]]) {
    const m = new THREE.Mesh(browStrands(THREE, stat, E[k], side), browMat); m.name = "brow_" + k;
    skin.add(m); root.updateMatrixWorld(true); headBone.attach(m); brows.push(m);
  }
  info.brows = brows.map(m => m.geometry.index.count / 24);
  info.lidBones = lidBones(THREE, skin, E);
  return info;
}
