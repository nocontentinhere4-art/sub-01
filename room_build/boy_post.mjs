// node boy_post.mjs [out/boy2_raw.glb] [../web/room] : the new character (#76) for the web.
//
// Input: build_boy.py's skinned mesh in its bind pose (out/boy2_raw.glb, MPFB bone names) and joints (out/boy2_bind.json),
// boy_ref.mjs's old skeleton (out/boy_ref.json) and the old clips (web/room/boy.glb, boy_*.glb).
// Output (web/room/): boy2.glb (mesh, skeleton, the "sit" clip like boy.glb, plus "blink"), boy2_<clip>.glb for every
// boy_<clip>.glb (same clip names), and boy2_hands.glb (finger poses: hand_relaxed, hand_phone, hand_chopsticks,
// hand_spoon, hand_type, hand_mouse).
//
// The new skeleton has the OLD bone names and the OLD bones' rest frames (orientations), placed at the new body's joints,
// in the same units (an "Armature" node scaled 0.01 over bones in cm). So every old clip's rotations play unchanged and
// room.html's code (bones.RightHand, head (0, 30, 30) = the face's direction, ...) keeps working. What the clips cannot
// carry over: the bones' translations (the old skeleton's lengths) are dropped, except the hips', which is scaled by
// the new leg length. New bones: 30 finger bones (<Side>Hand<Finger><1..3>), LeftEye/RightEye, and sockets (plain
// nodes, not skinned) where a held object goes: RightHand > socket_phone (its centre, +y its top, +z out of the screen),
// socket_chopsticks, socket_spoon.
import fs from "node:fs";
import path from "node:path";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { prune, weld, meshopt, dedup } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";
import * as THREE from "three";
import { palmOf } from "./palm.mjs";

const [,, RAW = "out/boy2_raw.glb", WEB = "../web/room"] = process.argv;
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const REF = JSON.parse(fs.readFileSync("out/boy_ref.json", "utf8")).bones;
const BIND = JSON.parse(fs.readFileSync("out/boy2_bind.json", "utf8"));
const V = a => new THREE.Vector3(...a), Q = a => new THREE.Quaternion(...a);
const CM = 100;                                  // bones are in cm under a 0.01 "Armature" node, like the old rig

// ------------------------------------------------------------------ the skeleton: name -> {parent, pos (m, world), quat (world)}
const mpfbOf = {}; for (const [m, n] of Object.entries(BIND.map)) if (m !== "Root") mpfbOf[n] = m;
const SK = {}, order = [];
function addBone(name, parent, pos, quat) { SK[name] = {name, parent, pos: pos.clone(), quat: quat.clone().normalize()}; order.push(name); }
// the old 24 in their old order (parents before children)
for (const [name, b] of Object.entries(REF)) {
  let pos;
  if (mpfbOf[name]) pos = V(BIND.bones[mpfbOf[name]].head);
  else {                                         // head_end / headfront: helpers at the same offset from the head joint as before
    pos = V(BIND.bones[mpfbOf.Head].head).add(V(b.pos).sub(V(REF.Head.pos)));
  }
  addBone(name, b.parent, pos, Q(b.quat));
}
const frameQuat = b => new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(V(b.x).normalize(), V(b.y).normalize(), V(b.z).normalize()));
for (const S of ["Left", "Right"]) for (const F of ["Thumb", "Index", "Middle", "Ring", "Pinky"]) for (const k of [1, 2, 3]) {
  const n = `${S}Hand${F}${k}`, b = BIND.bones[mpfbOf[n]];
  addBone(n, k === 1 ? `${S}Hand` : `${S}Hand${F}${k - 1}`, V(b.head), frameQuat(b));
}
for (const S of ["Left", "Right"]) addBone(`${S}Eye`, "Head", V(BIND.bones[mpfbOf[`${S}Eye`]].head), new THREE.Quaternion());
// the spine: MPFB's chest bone starts low (its spine_03 spans 1.15-1.44 m), the old rig's three spine joints are evenly
// spread between the hips and the neck, and the old clips bend them as such. So the new spine joints go where the old
// ones were along the torso (scaled), and the torso's weights are spread over them again (SPINE below)
const SPINE = ["Hips", "Spine02", "Spine01", "Spine", "neck"];
{
  const k = SK.neck.pos.clone().sub(SK.Hips.pos).length() / V(REF.neck.pos).sub(V(REF.Hips.pos)).length();
  for (const n of ["Spine02", "Spine01", "Spine"]) SK[n].pos.copy(SK.Hips.pos).add(V(REF[n].pos).sub(V(REF.Hips.pos)).multiplyScalar(k));
}
const world = n => new THREE.Matrix4().compose(SK[n].pos, SK[n].quat, new THREE.Vector3(0.01, 0.01, 0.01));
const ARM = new THREE.Matrix4().makeScale(0.01, 0.01, 0.01);
function localOf(n) {                            // local transform under the parent (cm)
  const pw = SK[n].parent ? world(SK[n].parent) : ARM, m = new THREE.Matrix4().copy(pw).invert().multiply(world(n));
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3(); m.decompose(p, q, s); return {p, q};
}

let SOCKETS = {};                                // filled in once the palms are measured (below)
function buildSkeleton(doc, scene) {
  const nodes = {}, arm = doc.createNode("Armature").setScale([0.01, 0.01, 0.01]); scene.addChild(arm);
  for (const n of order) {
    const {p, q} = localOf(n);
    nodes[n] = doc.createNode(n).setTranslation(p.toArray()).setRotation(q.toArray());
    (SK[n].parent ? nodes[SK[n].parent] : arm).addChild(nodes[n]);
  }
  for (const [n, s] of Object.entries(SOCKETS)) { nodes[n] = doc.createNode(n).setTranslation(s.p).setRotation(s.q); nodes[s.parent].addChild(nodes[n]); }
  return {arm, nodes};
}

// ------------------------------------------------------------------ the mesh
const doc = await io.read(RAW), root = doc.getRoot();
const rawSkin = root.listSkins()[0], rawJoints = rawSkin.listJoints().map(j => j.getName());
const meshNode = root.listNodes().find(n => n.getMesh()), mesh = meshNode.getMesh();
for (const n of root.listNodes()) if (n !== meshNode) n.dispose();
for (const s of root.listSkins()) s.dispose();
const scene = root.listScenes()[0]; meshNode.setName("boy2").setTranslation([0, 0, 0]).setRotation([0, 0, 0, 1]).setScale([1, 1, 1]);
scene.addChild(meshNode);
const joints = order.filter(n => !/head_end/.test(n));   // every bone is a joint (sockets are not)
const jIndex = Object.fromEntries(joints.map((n, i) => [n, i]));
// weights: MPFB bone -> new bone (the root's few go to the hips), merged, top 4, normalised
const remap = rawJoints.map(n => jIndex[BIND.map[n]]);
// the torso's share (its weights on the hips and the three spine bones) spread again by height: each spine bone's
// influence peaks in the middle of its segment and fades into its neighbours' (below the hips joint: all hips)
const spineIds = SPINE.slice(0, 4).map(n => jIndex[n]);
const centres = [SK.Hips.pos.y, ...[1, 2, 3].map(i => (SK[SPINE[i]].pos.y + SK[SPINE[i + 1]].pos.y) / 2)];
function spineShare(y) {
  const w = [0, 0, 0, 0];
  if (y <= centres[0]) w[0] = 1; else if (y >= centres[3]) w[3] = 1;
  else for (let i = 0; i < 3; i++) if (y >= centres[i] && y <= centres[i + 1]) { const t = (y - centres[i]) / (centres[i + 1] - centres[i]); w[i] = 1 - t; w[i + 1] = t; }
  return w;
}
if (remap.some(i => i === undefined)) throw new Error("unmapped joints: " + rawJoints.filter((n, i) => remap[i] === undefined));
for (const prim of mesh.listPrimitives()) {
  const J = prim.getAttribute("JOINTS_0"), W = prim.getAttribute("WEIGHTS_0"), POS = prim.getAttribute("POSITION"), n = J.getCount();
  const jo = new Uint8Array(n * 4), wo = new Float32Array(n * 4), j = [], w = [], p = [];
  for (let i = 0; i < n; i++) {
    J.getElement(i, j); W.getElement(i, w); const acc = new Map();
    for (let k = 0; k < 4; k++) if (w[k] > 0) acc.set(remap[j[k]], (acc.get(remap[j[k]]) || 0) + w[k]);
    const torso = spineIds.reduce((t, id) => t + (acc.get(id) || 0), 0);
    if (torso > 0) { const sh = spineShare(POS.getElement(i, p)[1]); spineIds.forEach((id, k) => { if (sh[k] > 0) acc.set(id, torso * sh[k]); else acc.delete(id); }); }
    const top = [...acc].sort((a, b) => b[1] - a[1]).slice(0, 4), sum = top.reduce((s, x) => s + x[1], 0) || 1;
    top.forEach(([jj, ww], k) => { jo[i * 4 + k] = jj; wo[i * 4 + k] = ww / sum; });
  }
  if (joints.length > 255) throw new Error("too many joints");
  J.setArray(jo).setType("VEC4"); W.setArray(wo);
}

// the palms, measured on the skin (palm.mjs), as a frame in each hand bone's space (cm): Y along the fingers, Z the palm's
// normal, T across the knuckles towards the thumb; `surf` how far the palm's skin stands out along Z
const HANDF = {};
for (const side of ["Left", "Right"]) {
  const ids = new Set(joints.map((n, i) => n.startsWith(side + "Hand") ? i : -1).filter(i => i >= 0)), inv = world(side + "Hand").invert(), pts = [];
  for (const prim of mesh.listPrimitives()) { const P = prim.getAttribute("POSITION"), J = prim.getAttribute("JOINTS_0"), W = prim.getAttribute("WEIGHTS_0"), j = [], w = [], q = [];
    for (let i = 0; i < P.getCount(); i++) { J.getElement(i, j); W.getElement(i, w); let sum = 0; for (let k = 0; k < 4; k++) if (ids.has(j[k])) sum += w[k];
      if (sum > 0.9) pts.push(new THREE.Vector3(...P.getElement(i, q)).applyMatrix4(inv)); } }
  const Z = palmOf(pts), Y = new THREE.Vector3(0, 1, 0), X = new THREE.Vector3().crossVectors(Y, Z);
  const thumb = SK[side + "HandThumb1"].pos.clone().applyMatrix4(inv), T = X.clone().multiplyScalar(Math.sign(thumb.dot(X)) || 1);
  const surf = Math.max(...pts.filter(p => p.y > 3 && p.y < 9 && Math.abs(p.dot(T)) < 3).map(p => p.dot(Z)));
  HANDF[side] = {T, Y, Z, surf, right: T.dot(X) > 0};
}
// a socket placed in the palm frame: p = [along T, along Y, off the palm (from its skin)] cm; y, z = the socket's own
// y and z axes as combinations of T, Y, Z (x follows)
function socket(side, [pt, py, pz], yk, zk) {
  const F = HANDF[side], v = k => F.T.clone().multiplyScalar(k[0]).addScaledVector(F.Y, k[1]).addScaledVector(F.Z, k[2]).normalize();
  const y = v(yk), x = new THREE.Vector3().crossVectors(y, v(zk)).normalize(), z = new THREE.Vector3().crossVectors(x, y);
  const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
  return {parent: side + "Hand", p: F.T.clone().multiplyScalar(pt).addScaledVector(F.Y, py).addScaledVector(F.Z, F.surf + pz).toArray(), q: q.toArray()};
}
// the phone: its back on the palm and fingers, screen facing the palm's way, its top towards the thumb, the fingers
// wrapped round its far long edge and the thumb over the screen. Chopsticks: in the thumb's web, along the index finger,
// tips past the fingertips. Spoon: held like a pencil, its bowl past the fingertips. Tuned on boy_test.html (T.hand(...))
SOCKETS = {
  socket_phone: socket("Right", [-1.0, 9.5, 0.45], [1, 0, 0], [0, 0, 1]),
  socket_chopsticks: socket("Right", [1.5, 7.5, 1.0], [0.25, 1, 0.15], [0, -0.15, 1]),
  socket_spoon: socket("Right", [1.0, 4.0, 1.0], [0.2, 1, 0.3], [0, -0.3, 1]),
};
console.log("palms:", Object.entries(HANDF).map(([k, f]) => `${k} Z ${f.Z.toArray().map(x => x.toFixed(2))} T ${f.T.toArray().map(x => x.toFixed(2))} surf ${f.surf.toFixed(1)}`).join(" | "));

const {nodes} = buildSkeleton(doc, scene);
const skin = doc.createSkin("boy2"); joints.forEach(n => skin.addJoint(nodes[n]));
skin.setSkeleton(nodes.Hips);
const ibm = doc.createAccessor("ibm").setType("MAT4").setArray(new Float32Array(joints.flatMap(n => world(n).invert().toArray())));
skin.setInverseBindMatrices(ibm); meshNode.setSkin(skin);

// ------------------------------------------------------------------ materials: one opaque atlas, one alpha-tested
const [primBody, primHair] = mesh.listPrimitives();
const mainPng = await sharp("out/boy2_color.png").removeAlpha().webp({quality: 90}).toBuffer();
const normalPng = await sharp("out/boy2_normal.png").removeAlpha().webp({quality: 92}).toBuffer();
// occlusion, roughness, metalness (glTF's R, G, B): the AO softened (it is baked in the bind pose), no metal
const ao = await sharp("out/boy2_ao.png").greyscale().raw().toBuffer({resolveWithObject: true}), rg = await sharp("out/boy2_rough.png").greyscale().raw().toBuffer();
const orm = Buffer.alloc(ao.info.width * ao.info.height * 3);
for (let i = 0; i < ao.info.width * ao.info.height; i++) { orm[i * 3] = 255 - Math.round((255 - ao.data[i]) * 0.45); orm[i * 3 + 1] = rg[i]; orm[i * 3 + 2] = 0; }
const ormPng = await sharp(orm, {raw: {width: ao.info.width, height: ao.info.height, channels: 3}}).webp({quality: 90}).toBuffer();
const hairRgb = await sharp("out/boy2_hair_color.png").removeAlpha().raw().toBuffer({resolveWithObject: true});
const hairA = await sharp("out/boy2_hair_alpha.png").greyscale().raw().toBuffer();
const rgba = Buffer.alloc(hairRgb.info.width * hairRgb.info.height * 4);
for (let i = 0; i < hairRgb.info.width * hairRgb.info.height; i++) {
  for (let c = 0; c < 3; c++) rgba[i * 4 + c] = hairRgb.data[i * 3 + c]; rgba[i * 4 + 3] = hairA[i];
}
const hairWebp = await sharp(rgba, {raw: {width: hairRgb.info.width, height: hairRgb.info.height, channels: 4}}).webp({quality: 88, alphaQuality: 90}).toBuffer();
const texMain = doc.createTexture("boy2_body").setImage(mainPng).setMimeType("image/webp");
const texNormal = doc.createTexture("boy2_body_normal").setImage(normalPng).setMimeType("image/webp");
const texOrm = doc.createTexture("boy2_body_orm").setImage(ormPng).setMimeType("image/webp");
const texHair = doc.createTexture("boy2_hair").setImage(hairWebp).setMimeType("image/webp");
doc.createExtension(ALL_EXTENSIONS.find(e => e.EXTENSION_NAME === "EXT_texture_webp")).setRequired(true);
const matBody = doc.createMaterial("boy2_body").setBaseColorTexture(texMain).setNormalTexture(texNormal)
  .setOcclusionTexture(texOrm).setMetallicRoughnessTexture(texOrm).setRoughnessFactor(1).setMetallicFactor(1);
const matHair = doc.createMaterial("boy2_hair").setBaseColorTexture(texHair).setRoughnessFactor(0.85).setMetallicFactor(0)
  .setAlphaMode("MASK").setAlphaCutoff(0.4).setDoubleSided(true);
primBody.setMaterial(matBody); primHair.setMaterial(matHair);
for (const m of root.listMaterials()) if (m !== matBody && m !== matHair) m.dispose();

// ------------------------------------------------------------------ clips
function addClip(target, nodesOf, name, channels) {  // channels: [{node, path, times, values}]
  const a = target.createAnimation(name), buf = target.getRoot().listBuffers()[0];
  for (const c of channels) {
    const node = nodesOf[c.node]; if (!node) continue;
    const s = target.createAnimationSampler().setInput(target.createAccessor().setType("SCALAR").setArray(new Float32Array(c.times)).setBuffer(buf))
      .setOutput(target.createAccessor().setType(c.path === "rotation" ? "VEC4" : c.path === "weights" ? "SCALAR" : "VEC3").setArray(new Float32Array(c.values)).setBuffer(buf))
      .setInterpolation(c.interp || "LINEAR");
    a.addSampler(s).addChannel(target.createAnimationChannel().setTargetNode(node).setTargetPath(c.path).setSampler(s));
  }
  return a;
}
async function readClip(file) {                  // the old clip, decoded, as plain channels
  const d = await io.read(file), out = [];
  for (const a of d.getRoot().listAnimations()) {
    const ch = [];
    for (const c of a.listChannels()) {
      const s = c.getSampler();
      // getElement() decodes normalised integers (the old clips' rotations are int16)
      const acc = x => { const out = [], e = []; for (let i = 0; i < x.getCount(); i++) out.push(...x.getElement(i, e)); return out; };
      ch.push({node: c.getTargetNode().getName(), path: c.getTargetPath(), times: acc(s.getInput()), values: acc(s.getOutput()), interp: s.getInterpolation()});
    }
    out.push({name: a.getName(), channels: ch});
  }
  return out;
}

// forward kinematics (three.js, no rendering) of a skeleton playing a clip
const OLD = {};                                 // the old rig's rest (local TRS, cm)
for (const n of (await io.read(path.join(WEB, "boy.glb"))).getRoot().listNodes())
  if (REF[n.getName()]) OLD[n.getName()] = {parent: REF[n.getName()].parent, p: V(n.getTranslation()), q: Q(n.getRotation()), s: V(n.getScale())};
const NEW = Object.fromEntries(order.map(n => { const {p, q} = localOf(n); return [n, {parent: SK[n].parent, p, q, s: new THREE.Vector3(1, 1, 1)}]; }));
function fk(locals, channels, name, scale = 0.01) {
  const root = new THREE.Object3D(), b = {}; root.scale.setScalar(scale);
  for (const [n, L] of Object.entries(locals)) { const o = b[n] = new THREE.Object3D(); o.name = n; o.position.copy(L.p); o.quaternion.copy(L.q); o.scale.copy(L.s); }
  for (const [n, L] of Object.entries(locals)) (L.parent ? b[L.parent] : root).add(b[n]);
  const tracks = channels.filter(c => b[c.node] && c.path !== "weights").map(c => {
    const T = c.path === "rotation" ? THREE.QuaternionKeyframeTrack : THREE.VectorKeyframeTrack;
    return new T(`${c.node}.${c.path === "rotation" ? "quaternion" : c.path === "translation" ? "position" : "scale"}`, c.times, c.values); });
  const mixer = new THREE.AnimationMixer(root); mixer.clipAction(new THREE.AnimationClip(name, -1, tracks)).play();
  return {at(t) { mixer.setTime(t); root.updateMatrixWorld(true); return b; }};
}
const ankle = b => Math.min(b.LeftFoot.getWorldPosition(new THREE.Vector3()).y, b.RightFoot.getWorldPosition(new THREE.Vector3()).y);
const oldRestAnkle = Math.min(REF.LeftFoot.pos[1], REF.RightFoot.pos[1]), newRestAnkle = Math.min(SK.LeftFoot.pos.y, SK.RightFoot.pos.y);

// the old clip on the new skeleton: rotations as they are; the bones' translations and scales of the old skeleton are
// dropped (the old idle even scales the hips by 1.18), except the hips' path, whose height is set at every key so that
// the lower foot is as far above its rest height as the old one's (the feet stay on the floor, the seat stays a seat)
function retarget(clip) {
  const ch = clip.channels, hips = ch.find(c => c.node === "Hips" && c.path === "translation");
  const out = ch.filter(c => c.path === "rotation" && SK[c.node]).map(c => ({...c}));
  if (hips) {
    const o = fk(OLD, ch, clip.name), values = hips.values.slice();
    const n = fk(NEW, [...out, {...hips, values}], clip.name);
    for (let i = 0; i < hips.times.length; i++) {
      const t = hips.times[i], dOld = ankle(o.at(t)) - oldRestAnkle, dNew = ankle(n.at(t)) - newRestAnkle;
      values[i * 3 + 1] += (dOld - dNew) * CM;
    }
    out.push({...hips, values});
  }
  const dropped = ch.filter(c => c.path === "scale" && c.values.some(v => Math.abs(v - 1) > 1e-3)).map(c => c.node);
  if (dropped.length) console.log(`  ${clip.name}: animated scale dropped (${dropped.join(", ")})`);
  return {name: clip.name, channels: out};
}

// ------------------------------------------------------------------ Quaternius' Universal Animation Library (CC0)
// Its rig (UE-mannequin style, T-pose, facing +z, every bone bending about its local +x) is mapped onto ours: our skeleton
// is posed into its T-pose bone by bone (limb directions, then the elbow and knee hinges and the palms, like
// build_boy.py does with the old rig), which gives each bone a fixed offset; a UAL frame's world rotations times the
// offsets are ours. The hips follow the UAL pelvis (scaled by leg length) with the feet held at the same height above
// their rest. In place: the Standard pack has no root motion.
const UAL_FILE = process.env.UAL || "/opt/ual/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb";
const UMAP = {pelvis: "Hips", spine_01: "Spine02", spine_02: "Spine01", spine_03: "Spine", neck_01: "neck", Head: "Head"};
for (const [s_, S_] of [["l", "Left"], ["r", "Right"]]) {
  Object.assign(UMAP, {[`clavicle_${s_}`]: `${S_}Shoulder`, [`upperarm_${s_}`]: `${S_}Arm`, [`lowerarm_${s_}`]: `${S_}ForeArm`, [`hand_${s_}`]: `${S_}Hand`,
    [`thigh_${s_}`]: `${S_}UpLeg`, [`calf_${s_}`]: `${S_}Leg`, [`foot_${s_}`]: `${S_}Foot`, [`ball_${s_}`]: `${S_}ToeBase`});
  for (const [f, F] of [["thumb", "Thumb"], ["index", "Index"], ["middle", "Middle"], ["ring", "Ring"], ["pinky", "Pinky"]])
    for (const k of [1, 2, 3]) UMAP[`${f}_0${k}_${s_}`] = `${S_}Hand${F}${k}`;
}
const MINE = Object.fromEntries(Object.entries(UMAP).map(([u, m]) => [m, u]));
// the child joint that gives each bone its direction (ours, UAL's)
const CHILD = {Spine02: "Spine01", Spine01: "Spine", Spine: "neck", neck: "Head"};
for (const S_ of ["Left", "Right"]) {
  Object.assign(CHILD, {[`${S_}Shoulder`]: `${S_}Arm`, [`${S_}Arm`]: `${S_}ForeArm`, [`${S_}ForeArm`]: `${S_}Hand`, [`${S_}Hand`]: `${S_}HandMiddle1`,
    [`${S_}UpLeg`]: `${S_}Leg`, [`${S_}Leg`]: `${S_}Foot`, [`${S_}Foot`]: `${S_}ToeBase`});
  for (const F of ["Thumb", "Index", "Middle", "Ring", "Pinky"]) { CHILD[`${S_}Hand${F}1`] = `${S_}Hand${F}2`; CHILD[`${S_}Hand${F}2`] = `${S_}Hand${F}3`; }
}
let UAL = null;
async function loadUAL() {
  if (!fs.existsSync(UAL_FILE)) { console.warn("  no UAL file:", UAL_FILE); return null; }
  const ud = await io.read(UAL_FILE), ur = ud.getRoot(), skin = ur.listSkins()[0], joints = skin.listJoints(), jn = new Set(joints.map(j => j.getName()));
  const U = {};
  for (const j of joints) U[j.getName()] = {parent: jn.has(j.getParentNode()?.getName()) ? j.getParentNode().getName() : null,
    p: V(j.getTranslation()), q: Q(j.getRotation()), s: V(j.getScale())};
  const rest = fk(U, [], "rest", 1).at(0), W = {};
  for (const n of Object.keys(U)) W[n] = {p: rest[n].getWorldPosition(new THREE.Vector3()), q: rest[n].getWorldQuaternion(new THREE.Quaternion())};
  // UAL's palms, measured on its mannequin's skin like ours
  const palms = {};
  for (const [s_, S_] of [["l", "Left"], ["r", "Right"]]) {
    const ids = new Set(joints.map((j, i) => /^(hand|index|middle|ring|pinky|thumb)_/.test(j.getName()) && j.getName().endsWith("_" + s_) ? i : -1).filter(i => i >= 0));
    const inv = new THREE.Matrix4().fromArray(skin.getInverseBindMatrices().getElement(joints.findIndex(j => j.getName() === "hand_" + s_), [])), pts = [];
    for (const m of ur.listMeshes()) for (const prim of m.listPrimitives()) {
      const P = prim.getAttribute("POSITION"), J = prim.getAttribute("JOINTS_0"), Wt = prim.getAttribute("WEIGHTS_0"); if (!J) continue;
      for (let i = 0, j = [], w = [], q = []; i < P.getCount(); i++) { J.getElement(i, j); Wt.getElement(i, w); let sum = 0; for (let k = 0; k < 4; k++) if (ids.has(j[k])) sum += w[k];
        if (sum > 0.9) pts.push(new THREE.Vector3(...P.getElement(i, q)).applyMatrix4(inv)); }
    }
    palms[S_] = palmOf(pts).applyQuaternion(W["hand_" + s_].q);
  }
  const anims = Object.fromEntries(ur.listAnimations().map(a => [a.getName(), a]));
  return {U, W, palms, anims};
}
// our skeleton in UAL's T-pose: world rotations per bone
function canonical(ual) {
  const b = fk(NEW, [], "canon").at(0), W = ual.W, wp = n => b[n].getWorldPosition(new THREE.Vector3()), wq = n => b[n].getWorldQuaternion(new THREE.Quaternion());
  const turn = (n, R) => { const pq = b[n].parent.getWorldQuaternion(new THREE.Quaternion()); b[n].quaternion.copy(pq.invert().multiply(R.clone().multiply(wq(n)))); b[n].updateMatrixWorld(true); };
  const aim = n => { const c = CHILD[n]; if (!c || !MINE[n] || !MINE[c]) return;
    const mine = wp(c).sub(wp(n)).normalize(), theirs = W[MINE[c]].p.clone().sub(W[MINE[n]].p).normalize();
    turn(n, new THREE.Quaternion().setFromUnitVectors(mine, theirs)); };
  const twist = (n, have, want) => { const a = wp(CHILD[n]).sub(wp(n)).normalize();
    const h = have.clone().addScaledVector(a, -have.dot(a)).normalize(), w = want.clone().addScaledVector(a, -want.dot(a)).normalize();
    turn(n, new THREE.Quaternion().setFromAxisAngle(a, Math.atan2(a.dot(new THREE.Vector3().crossVectors(h, w)), h.dot(w)))); };
  const xOf = n => new THREE.Vector3(1, 0, 0).applyQuaternion(W[n].q);       // UAL's hinge (flex about +x)
  const HINGE_LOCAL = {ForeArm: {Left: [-0.8, 0, 0.6], Right: [-0.8, 0, -0.6]}, Leg: {Left: [1, 0, 0], Right: [1, 0, 0]}};
  const hingeOf = (n, side, kind) => new THREE.Vector3(...HINGE_LOCAL[kind][side]).normalize().applyQuaternion(wq(n));
  for (const n of ["Spine02", "Spine01", "Spine", "neck"]) aim(n);
  for (const S_ of ["Left", "Right"]) {
    const s_ = S_[0].toLowerCase();
    aim(`${S_}Shoulder`); aim(`${S_}Arm`); aim(`${S_}ForeArm`);
    twist(`${S_}Arm`, hingeOf(`${S_}ForeArm`, S_, "ForeArm"), xOf(`lowerarm_${s_}`)); aim(`${S_}ForeArm`);
    aim(`${S_}Hand`);
    twist(`${S_}Hand`, HANDF[S_].Z.clone().applyQuaternion(wq(`${S_}Hand`)), ual.palms[S_]);
    for (const F of ["Thumb", "Index", "Middle", "Ring", "Pinky"]) { aim(`${S_}Hand${F}1`); aim(`${S_}Hand${F}2`); }
    aim(`${S_}UpLeg`); aim(`${S_}Leg`);
    twist(`${S_}UpLeg`, hingeOf(`${S_}Leg`, S_, "Leg"), xOf(`calf_${s_}`)); aim(`${S_}Leg`);
    aim(`${S_}Foot`);
  }
  const off = {};
  for (const [m, u] of Object.entries(MINE)) off[m] = W[u].q.clone().invert().multiply(wq(m));
  return off;
}
// a UAL clip on our skeleton, resampled at 30 fps, every bone keyed
function fromUAL(ual, off, name, as, {loop = true} = {}) {
  const a = ual.anims[name], ch = [];
  for (const c of a.listChannels()) { const sm = c.getSampler(), acc = x => { const o = [], e = []; for (let i = 0; i < x.getCount(); i++) o.push(...x.getElement(i, e)); return o; };
    ch.push({node: c.getTargetNode().getName(), path: c.getTargetPath(), times: acc(sm.getInput()), values: acc(sm.getOutput())}); }
  const dur = Math.max(...ch.map(c => c.times[c.times.length - 1])), n = Math.max(2, Math.round(dur * 30) + 1), times = [...Array(n)].map((_, i) => i * dur / (n - 1));
  const u = fk(ual.U, ch, name, 1), mine = fk(NEW, [], as);
  const uRestAnkle = Math.min(ual.W.foot_l.p.y, ual.W.foot_r.p.y), uRestPelvis = ual.W.pelvis.p;
  const k = (SK.Hips.pos.y - newRestAnkle) / (uRestPelvis.y - uRestAnkle);   // leg-length ratio
  const outQ = Object.fromEntries(order.map(b => [b, []])), outT = [];
  const armInv = new THREE.Matrix4().makeScale(100, 100, 100);
  for (const t of times) {
    const ub = u.at(t), mb = mine.at(0);
    for (const b of order) {                       // parents first: our world rotation = UAL world x offset
      const o = mb[b];
      if (MINE[b]) { const uq = ub[MINE[b]].getWorldQuaternion(new THREE.Quaternion()).multiply(off[b]);
        const pq = o.parent.getWorldQuaternion(new THREE.Quaternion()); o.quaternion.copy(pq.invert().multiply(uq)); }
      else { const L = NEW[b]; o.quaternion.copy(L.q); }
      o.updateMatrixWorld(true);
      outQ[b].push(...o.quaternion.toArray());
    }
    // hips: UAL pelvis offset from its rest, scaled; then the lower ankle held as far above its rest as UAL's
    const up = ub.pelvis.getWorldPosition(new THREE.Vector3()).sub(uRestPelvis).multiplyScalar(k);
    const hipsW = SK.Hips.pos.clone().add(up);
    mb.Hips.position.copy(hipsW.clone().applyMatrix4(armInv)); mb.Hips.updateMatrixWorld(true);
    const dU = Math.min(ub.foot_l.getWorldPosition(new THREE.Vector3()).y, ub.foot_r.getWorldPosition(new THREE.Vector3()).y) - uRestAnkle;
    const dM = ankle(mb) - newRestAnkle;
    hipsW.y += dU * k - dM;
    outT.push(...hipsW.applyMatrix4(armInv).toArray());
  }
  const channels = order.map(b => ({node: b, path: "rotation", times, values: outQ[b]}));
  channels.push({node: "Hips", path: "translation", times, values: outT});
  return {name: as, channels, duration: dur, hips0: outT.slice(0, 3).map(v => v / CM)};
}
// the room's names (#63's list) for what UAL Standard has
const UAL_CLIPS = {stand_idle: "Idle_Loop", walk: "Walk_Loop", sit_down_chair: "Sitting_Enter", stand_up_chair: "Sitting_Exit",
  sit_idle_upright: "Sitting_Idle_Loop", take_item: "PickUp_Table", door_open_pull: "Interact"};

// finger poses. A pose: per finger the flex of its three joints (deg, + curls towards the palm) and its spread at the
// knuckle (deg, + away from the middle finger); the thumb: its base turned about the hand's own axes (x across the
// knuckles, y along the fingers, z the palm side), then its two joints' flex.
const FINGERS = ["Index", "Middle", "Ring", "Pinky"];
const POSES = {
  hand_relaxed: {L: {curl: [[14, 20, 10], [18, 24, 12], [22, 26, 14], [26, 28, 14]], spread: [-2, 0, -2, -4], thumb: {base: [10, 6, 0], flex: [8, 10]}}},
  hand_phone: {R: {curl: [[22, 78, 30], [24, 80, 30], [26, 80, 30], [34, 70, 25]], spread: [-1, 0, -1, -3], thumb: {base: [48, 24, 25], flex: [6, 10]}}},
  hand_chopsticks: {R: {curl: [[22, 18, 8], [36, 30, 14], [62, 60, 40], [70, 64, 40]], spread: [2, 0, -2, -4], thumb: {base: [30, 20, 20], flex: [10, 14]}}},
  hand_spoon: {R: {curl: [[30, 26, 12], [42, 40, 20], [64, 62, 40], [72, 66, 42]], spread: [1, 0, -2, -4], thumb: {base: [30, 22, 20], flex: [12, 16]}}},
  hand_type: {L: {curl: [[22, 30, 12], [24, 32, 14], [24, 32, 14], [24, 30, 12]], spread: [0, 0, -2, -4], thumb: {base: [14, 4, 0], flex: [6, 8]}}},
  hand_mouse: {R: {curl: [[10, 14, 8], [10, 14, 8], [24, 28, 14], [30, 34, 18]], spread: [0, 0, -3, -6], thumb: {base: [18, 10, 10], flex: [6, 6]}}},
};
for (const p of Object.values(POSES)) for (const [a, b] of [["L", "R"], ["R", "L"]]) if (!p[a]) p[a] = p[b] === POSES.hand_relaxed.L ? p[b] : null;
for (const [k, p] of Object.entries(POSES)) { if (!p.L) p.L = POSES.hand_relaxed.L; if (!p.R) p.R = k === "hand_type" ? p.L : POSES.hand_relaxed.L; }
const deg = Math.PI / 180;
function poseChannels(spec) {
  const ch = [];
  for (const [S, side] of [["L", "Left"], ["R", "Right"]]) {
    const P = spec[S], hand = SK[`${side}Hand`], hq = hand.quat;
    const F = HANDF[side], hx = F.T.clone().applyQuaternion(hq), hy = F.Y.clone().applyQuaternion(hq), palm = F.Z.clone().applyQuaternion(hq);
    const mid = SK[`${side}HandMiddle1`].pos;
    const posed = {};                            // world rotation of each finger bone once posed
    const put = (n, worldQ) => { posed[n] = worldQ; const pw = posed[SK[n].parent] || SK[SK[n].parent].quat;
      const lq = pw.clone().invert().multiply(worldQ); ch.push({node: n, path: "rotation", times: [0, 1], values: [...lq.toArray(), ...lq.toArray()]}); };
    FINGERS.forEach((F, fi) => {
      for (let k = 1; k <= 3; k++) {
        const n = `${side}Hand${F}${k}`, b = SK[n];
        // the parent's turn so far (world), then this joint's own: about the knuckle line (+ towards the palm), and at the
        // knuckle a spread about the palm's normal (+ away from the middle finger)
        const parentTurn = posed[b.parent] ? posed[b.parent].clone().multiply(SK[b.parent].quat.clone().invert()) : new THREE.Quaternion();
        const d = new THREE.Vector3(0, 1, 0).applyQuaternion(b.quat).applyQuaternion(parentTurn), pn = palm.clone().applyQuaternion(parentTurn);
        let turn = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3().crossVectors(d, pn).normalize(), P.curl[fi][k - 1] * deg);
        if (k === 1) { const away = Math.sign(new THREE.Vector3().crossVectors(pn, d).dot(b.pos.clone().sub(mid))) || 0;
          turn = turn.multiply(new THREE.Quaternion().setFromAxisAngle(pn, away * P.spread[fi] * deg)); }
        put(n, turn.multiply(parentTurn).multiply(b.quat).normalize());
      }
    });
    // thumb: its base swung towards the palm (base[0]) and towards the fingers (base[1]), turned about itself (base[2],
    // + rolls its pad towards the fingers); then its joints flex towards the palm
    const t1 = SK[`${side}HandThumb1`], d1 = new THREE.Vector3(0, 1, 0).applyQuaternion(t1.quat), roll = S === "R" ? -1 : 1;
    const base = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3().crossVectors(d1, hy).normalize(), P.thumb.base[1] * deg)
      .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3().crossVectors(d1, palm).normalize(), P.thumb.base[0] * deg))
      .multiply(new THREE.Quaternion().setFromAxisAngle(d1, roll * P.thumb.base[2] * deg));
    put(`${side}HandThumb1`, base.clone().multiply(t1.quat));
    for (const k of [2, 3]) {
      const n = `${side}HandThumb${k}`, b = SK[n], parentTurn = posed[b.parent].clone().multiply(SK[b.parent].quat.clone().invert());
      const d = new THREE.Vector3(0, 1, 0).applyQuaternion(b.quat).applyQuaternion(parentTurn);
      const axis = new THREE.Vector3().crossVectors(d, palm).normalize();
      put(n, new THREE.Quaternion().setFromAxisAngle(axis, P.thumb.flex[k - 2] * deg).multiply(parentTurn).multiply(b.quat).normalize());
    }
  }
  return ch;
}

// ------------------------------------------------------------------ write
const report = [];
async function finish(d, file) {
  await d.transform(dedup(), prune({keepLeaves: true, keepAttributes: true}), meshopt({encoder: MeshoptEncoder, level: "medium"}));
  await io.write(file, d); const kb = fs.statSync(file).size / 1024; report.push(`${path.basename(file)} ${kb.toFixed(0)} KB`); return kb;
}
const sit = await readClip(path.join(WEB, "boy.glb"));
const buf = root.listBuffers()[0] || doc.createBuffer();
for (const c of sit) { const r = retarget(c); addClip(doc, nodes, r.name, r.channels); }
// a blink: 0.22 s, closing fast and opening a little slower (room.html fires it every few seconds)
addClip(doc, {boy2: meshNode}, "blink", [{node: "boy2", path: "weights", times: [0, 0.07, 0.1, 0.22], values: [0, 1, 1, 0]}]);
await doc.transform(weld());
const kbMain = await finish(doc, path.join(WEB, "boy2.glb"));
// every other clip file: the same skeleton (no mesh), the retargeted clip
const clipFiles = fs.readdirSync(WEB).filter(f => /^boy_[a-z0-9_]+\.glb$/.test(f)).sort();
for (const f of clipFiles) {
  const d = new (await import("@gltf-transform/core")).Document(); d.createBuffer(); const sc = d.createScene();
  const {nodes: ns} = buildSkeleton(d, sc);
  for (const c of await readClip(path.join(WEB, f))) { const r = retarget(c); addClip(d, ns, r.name, r.channels); }
  await finish(d, path.join(WEB, f.replace(/^boy_/, "boy2_")));
}
{
  const d = new (await import("@gltf-transform/core")).Document(); d.createBuffer(); const sc = d.createScene();
  const {nodes: ns} = buildSkeleton(d, sc);
  for (const [name, spec] of Object.entries(POSES)) addClip(d, ns, name, poseChannels(spec));
  await finish(d, path.join(WEB, "boy2_hands.glb"));
}
UAL = await loadUAL();
if (UAL) {
  // all the new motion in one file, one animation per name of the room's list
  const off = canonical(UAL), rows = [];
  const d = new (await import("@gltf-transform/core")).Document(); d.createBuffer(); const sc = d.createScene();
  const {nodes: ns} = buildSkeleton(d, sc);
  for (const [as, name] of Object.entries(UAL_CLIPS)) {
    if (!UAL.anims[name]) { console.warn("  UAL has no", name); continue; }
    const r = fromUAL(UAL, off, name, as); addClip(d, ns, r.name, r.channels);
    rows.push(`  ${as} <- UAL ${name}: ${r.duration.toFixed(2)} s, hips at frame 0 [${r.hips0.map(v => v.toFixed(3)).join(", ")}] m`);
  }
  await finish(d, path.join(WEB, "boy2_motion.glb"));
  console.log("boy2_motion.glb:\n" + rows.join("\n"));
}
const tris = mesh.listPrimitives().reduce((s, p) => s + p.getIndices().getCount() / 3, 0);
console.log(`boy2: ${tris} triangles, ${mesh.listPrimitives().length} materials, ${joints.length} joints`);
console.log(report.join(", "));
if (kbMain > 3 * 1024) throw new Error("boy2.glb is over 3 MB");
if (tris > 25000) throw new Error("over 25k triangles");
