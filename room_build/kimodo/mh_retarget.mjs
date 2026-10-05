// node mh_retarget.mjs <mh_clip.glb> <v5.glb> <out.glb> [opts.json]
// MakeHuman room clips (preview/room-mh web/room/mh/*.glb: G2's rig, world-aligned rest pose facing +Z, fingers) onto the
// v5 Tripo rig (41 bones, faces +X; plus finger bones when the GLB has them, MakeHuman names finger1-1.L ... finger5-3.R).
// 1) every mapped bone takes its MakeHuman bone's world rotation, the source turned to face +X (C = 90° about Y), with the
//    two rest poses aligned per bone (the minimal rotation from the source rest direction to the target's);
// 2) the Hip follows the midpoint of the MakeHuman hip joints: horizontally unscaled (props_g2.json and the choreography
//    are in the clip's metres), vertically by the leg-length ratio, ankle heights matched;
// 3) zero-phase smoothing (Gaussian, sigma 1 frame limbs / 1.7 spine-neck-head), then two-bone IK: the wrists onto the
//    MakeHuman wrists (so hands stay on the keyboard, mouse, book, phone, spoon, cup), the ankles onto the MakeHuman
//    ankles (feet planted where his were), soles above the floor; a last smoothing pass with the IK re-solved.
// Output: the bare v5 rig with one animation (all bones + Hip translation, 30 fps), in the rig's frame: the rig faces +X,
// so a v5 root turned by (MH heading - 90°) about Y plays it where the MakeHuman clip played.
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";
import { resample, prune } from "@gltf-transform/functions";
import * as THREE from "three";
const [,, SRC, CHAR, OUT, OPTF] = process.argv;
const O = OPTF ? JSON.parse(fs.readFileSync(OPTF)) : {};
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const V = a => new THREE.Vector3(a[0], a[1], a[2]);
const FPS = O.fps || 30;

// ---------- the MakeHuman clip, sampled at FPS, world transforms per frame
const sdoc = await io.read(SRC), sroot = sdoc.getRoot();
const sNodes = new Map(sroot.listNodes().map(n => [n.getName(), n]));
const sPar = new Map(); for (const n of sroot.listNodes()) for (const c of n.listChildren()) sPar.set(c, n);
const sDepth = n => { let k = 0; while ((n = sPar.get(n))) k++; return k; };
const sTD = sroot.listNodes().slice().sort((a, b) => sDepth(a) - sDepth(b));
const anim = sroot.listAnimations()[0]; const chans = new Map();
let dur = 0; for (const c of anim.listChannels()) { const s = c.getSampler(), inp = s.getInput().getArray(), out = s.getOutput().getArray();
  chans.set(c.getTargetNode().getName() + ":" + c.getTargetPath(), {inp, out, n: c.getTargetPath() === "rotation" ? 4 : 3}); dur = Math.max(dur, inp[inp.length - 1]); }
function sample(ch, t){ const {inp, out, n} = ch; let i = 0; while (i + 1 < inp.length && inp[i + 1] <= t) i++;
  const j = Math.min(i + 1, inp.length - 1), u = inp[j] > inp[i] ? Math.min(1, Math.max(0, (t - inp[i]) / (inp[j] - inp[i]))) : 0;
  if (n === 4) { const a = new THREE.Quaternion().fromArray(out, i * 4), b = new THREE.Quaternion().fromArray(out, j * 4); return a.slerp(b, u); }
  return new THREE.Vector3().fromArray(out, i * 3).lerp(new THREE.Vector3().fromArray(out, j * 3), u); }
const T = Math.round(dur * FPS) + 1;
const C = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 2), Ci = C.clone().invert();
function sFK(t){ const W = new Map(), P = new Map();
  for (const n of sTD) { const nm = n.getName(), p = sPar.get(n);
    const q = chans.has(nm + ":rotation") ? sample(chans.get(nm + ":rotation"), t) : new THREE.Quaternion(...n.getRotation());
    const tr = chans.has(nm + ":translation") ? sample(chans.get(nm + ":translation"), t) : V(n.getTranslation());
    if (!p) { W.set(nm, q); P.set(nm, tr); continue; }
    const pw = W.get(p.getName()); W.set(nm, pw.clone().multiply(q)); P.set(nm, tr.applyQuaternion(pw).add(P.get(p.getName()))); }
  return {W, P}; }
const sRest = sFK(-1); for (const n of sTD) { /* rest = the nodes' own transforms */ }
const sRestP = new Map(); { const W = new Map(); for (const n of sTD) { const p = sPar.get(n), q = new THREE.Quaternion(...n.getRotation()), tr = V(n.getTranslation());
  if (!p) { W.set(n.getName(), q); sRestP.set(n.getName(), tr); continue; } const pw = W.get(p.getName()); W.set(n.getName(), pw.clone().multiply(q)); sRestP.set(n.getName(), tr.applyQuaternion(pw).add(sRestP.get(p.getName()))); } }
const srcP = nm => sRestP.get(nm).clone().applyQuaternion(C);

// ---------- the v5 rig
const doc = await io.read(CHAR), root = doc.getRoot();
const nodes = new Map(root.listNodes().map(n => [n.getName(), n]));
const parentOf = new Map(); for (const n of root.listNodes()) for (const c of n.listChildren()) parentOf.set(c, n);
const depth = n => { let k = 0; while ((n = parentOf.get(n))) k++; return k; };
const skinJoints = root.listSkins()[0].listJoints();
const bonesTD = root.listNodes().filter(n => skinJoints.includes(n) || n.getName() === "Armature").sort((a, b) => depth(a) - depth(b));
const restL = new Map(bonesTD.map(n => [n, new THREE.Quaternion(...n.getRotation())])), restT = new Map(bonesTD.map(n => [n, V(n.getTranslation())])), restS = new Map(bonesTD.map(n => [n, n.getScale()[0]]));
function fk(localQ, hipT){ const W = new Map(), P = new Map(), S = new Map();
  for (const n of bonesTD) { const p = parentOf.get(n), q = localQ.get(n) || restL.get(n), t = (n.getName() === "Hip" && hipT) ? hipT : restT.get(n);
    if (!p || !W.has(p)) { W.set(n, q.clone()); P.set(n, t.clone()); S.set(n, restS.get(n)); continue; }
    W.set(n, W.get(p).clone().multiply(q)); P.set(n, t.clone().multiplyScalar(S.get(p)).applyQuaternion(W.get(p)).add(P.get(p))); S.set(n, S.get(p) * restS.get(n)); }
  return {W, P, S}; }
const rest = fk(new Map()); const B = nm => nodes.get(nm); const restP = nm => rest.P.get(B(nm)).clone();
const HAS_FINGERS = !!B("finger2-1.L");

// target <- [source, source child for the direction, target child]
const MAP = {Hip: ["Hips", "spine04", "Spine01"], Waist: ["spine04", "spine02", "Spine01"], Spine01: ["spine02", "Spine", "Spine02"],
  Spine02: ["Spine", "neck", "NeckTwist01"], NeckTwist01: ["neck", "Head", "NeckTwist02"], NeckTwist02: ["neck", "Head", "Head"], Head: ["Head", "head_end", null], Pelvis: ["Hips", null, null]};
for (const [s, S, x] of [["L", "Left", "L"], ["R", "Right", "R"]]) {
  Object.assign(MAP, {[`${s}_Clavicle`]: [`${S}Shoulder`, `${S}Arm`, `${s}_Upperarm`], [`${s}_Upperarm`]: [`${S}Arm`, `${S}ForeArm`, `${s}_Forearm`],
    [`${s}_Forearm`]: [`${S}ForeArm`, `${S}Hand`, `${s}_Hand`], [`${s}_Hand`]: [`${S}Hand`, `finger3-1.${x}`, HAS_FINGERS ? `finger3-1.${x}` : null],
    [`${s}_Thigh`]: [`${S}UpLeg`, `${S}Leg`, `${s}_Calf`], [`${s}_Calf`]: [`${S}Leg`, `${S}Foot`, `${s}_Foot`],
    [`${s}_Foot`]: [`${S}Foot`, `${S}ToeBase`, `${s}_ToeBase`], [`${s}_ToeBase`]: [`${S}ToeBase`, `toe1-2.${x}`, null]});
  if (HAS_FINGERS) for (let f = 1; f <= 5; f++) for (let j = 1; j <= 3; j++) { const nm = `finger${f}-${j}.${x}`; if (!B(nm)) continue;
    const nx = j < 3 ? `finger${f}-${j + 1}.${x}` : null; MAP[nm] = [nm, nx, nx && B(nx) ? nx : null]; }
}
for (const k of Object.keys(MAP)) if (!B(k) || !sNodes.has(MAP[k][0])) delete MAP[k];
const order = Object.keys(MAP).sort((a, b) => depth(B(a)) - depth(B(b)));
const ALIGN = {};
for (const b of order) { const [src, sc, tc] = MAP[b];
  let ds = sc && sNodes.has(sc) ? srcP(sc).sub(srcP(src)).normalize() : null, dt = tc ? restP(tc).sub(restP(b)).normalize() : null;
  if (b === "Head") dt = new THREE.Vector3(0, 1, 0);
  if (ds && dt && ds.lengthSq() > 0.5 && dt.lengthSq() > 0.5) ALIGN[b] = new THREE.Quaternion().setFromUnitVectors(ds, dt);
  else { let a = null; for (let n = parentOf.get(B(b)); n && !a; n = parentOf.get(n)) a = ALIGN[n.getName()]; ALIGN[b] = a ? a.clone() : new THREE.Quaternion(); } }

// scale and ankle offset
const srcLeg = srcP("LeftUpLeg").distanceTo(srcP("LeftLeg")) + srcP("LeftLeg").distanceTo(srcP("LeftFoot"));
const tgtLeg = restP("L_Thigh").distanceTo(restP("L_Calf")) + restP("L_Calf").distanceTo(restP("L_Foot"));
const k = tgtLeg / srcLeg, srcAnkle = sRestP.get("LeftFoot").y, tgtAnkle = (restP("L_Foot").y + restP("R_Foot").y) / 2;

// ---------- per frame
const frames = [];
for (let f = 0; f < T; f++) { const t = Math.min(f / FPS, dur), s = sFK(t), W = {};
  for (const b of order) W[b] = C.clone().multiply(s.W.get(MAP[b][0])).multiply(Ci).multiply(ALIGN[b].clone().invert()).multiply(rest.W.get(B(b)));
  const hm = s.P.get("LeftUpLeg").clone().add(s.P.get("RightUpLeg")).multiplyScalar(0.5).applyQuaternion(C);
  const hip = new THREE.Vector3(hm.x, (hm.y - srcAnkle) * k + tgtAnkle, hm.z);
  const eff = {}; for (const [n, sn] of [["L_Hand", "LeftHand"], ["R_Hand", "RightHand"], ["L_Foot", "LeftFoot"], ["R_Foot", "RightFoot"]]) {
    const p = s.P.get(sn).clone().applyQuaternion(C); if (n.endsWith("Foot")) p.y = p.y - srcAnkle + tgtAnkle; eff[n] = p; }
  frames.push({W, hip, eff}); }
function toLocal(Wmap, hipWorld){ const L = new Map(), Wc = new Map();
  for (const n of bonesTD) { const p = parentOf.get(n), name = n.getName(), pw = p ? Wc.get(p) : new THREE.Quaternion();
    const w = Wmap[name] ? Wmap[name] : pw.clone().multiply(restL.get(n)); Wc.set(n, w); if (Wmap[name]) L.set(n, pw.clone().invert().multiply(w)); }
  const pr = parentOf.get(B("Hip")), ht = hipWorld.clone().sub(rest.P.get(pr)).applyQuaternion(rest.W.get(pr).clone().invert()).multiplyScalar(1 / rest.S.get(pr));
  return {L, ht}; }
let seq = frames.map(f => toLocal(f.W, f.hip));

function twoBone(L, ht, a, b, c, goal, w = 1){
  const st = fk(L, ht), A = st.P.get(B(a)), Bp = st.P.get(B(b)), Cp = st.P.get(B(c));
  const la = A.distanceTo(Bp), lb = Bp.distanceTo(Cp); let d = Math.min(A.distanceTo(goal), (la + lb) * 0.999); const cur = A.distanceTo(Cp);
  const ang = x => Math.acos(THREE.MathUtils.clamp((la * la + lb * lb - x * x) / (2 * la * lb), -1, 1));
  const axis = Bp.clone().sub(A).cross(Cp.clone().sub(Bp)); if (axis.lengthSq() < 1e-10) axis.set(0, 0, 1).applyQuaternion(st.W.get(B(a))); axis.normalize();
  const qb = new THREE.Quaternion().setFromAxisAngle(axis, ang(cur) - ang(d)), Wb = qb.clone().multiply(st.W.get(B(b)));
  const Cn = Cp.clone().sub(Bp).applyQuaternion(qb).add(Bp);
  const qa = new THREE.Quaternion().setFromUnitVectors(Cn.clone().sub(A).normalize(), goal.clone().sub(A).normalize());
  const Wa = qa.clone().multiply(st.W.get(B(a))), Wb2 = qa.clone().multiply(Wb), Wc = st.W.get(B(c)).clone();
  const chainW = (from, Wtop, to) => { let w = Wtop; const path = []; for (let x = parentOf.get(B(to)); x !== B(from); x = parentOf.get(x)) path.unshift(x); for (const x of path) w = w.clone().multiply(L.get(x) || restL.get(x)); return w; };
  const La = st.W.get(parentOf.get(B(a))).clone().invert().multiply(Wa), Lb = chainW(a, Wa, b).invert().multiply(Wb2), Lc = chainW(b, Wb2, c).invert().multiply(Wc);
  for (const [n, q] of [[a, La], [b, Lb], [c, Lc]]) { const c0 = L.get(B(n)) || restL.get(B(n)); L.set(B(n), c0.clone().slerp(q, w)); } }
function smoothSeq(sigL, sigS){ const SP = new Set(["Hip", "Waist", "Spine01", "Spine02", "NeckTwist01", "NeckTwist02", "Head", "Pelvis"]);
  const kern = sg => { const r = Math.ceil(sg * 3), w = []; for (let j = -r; j <= r; j++) w.push(Math.exp(-j * j / (2 * sg * sg))); return {r, w}; };
  const KL = kern(sigL), KS = kern(sigS), out = seq.map(f => ({L: new Map(f.L), ht: f.ht.clone()}));
  for (const n of bonesTD) { if (!seq[0].L.has(n)) continue; const K = SP.has(n.getName()) ? KS : KL;
    for (let f = 0; f < T; f++) { const c = seq[f].L.get(n), acc = new THREE.Vector4(0, 0, 0, 0);
      for (let j = -K.r; j <= K.r; j++) { const q = seq[Math.min(T - 1, Math.max(0, f + j))].L.get(n), w = K.w[j + K.r], sg = (q.x * c.x + q.y * c.y + q.z * c.z + q.w * c.w) < 0 ? -1 : 1;
        acc.x += sg * w * q.x; acc.y += sg * w * q.y; acc.z += sg * w * q.z; acc.w += sg * w * q.w; }
      out[f].L.set(n, new THREE.Quaternion(acc.x, acc.y, acc.z, acc.w).normalize()); } }
  for (let f = 0; f < T; f++) { const acc = new THREE.Vector3(); let ws = 0; for (let j = -KS.r; j <= KS.r; j++) { const w = KS.w[j + KS.r]; acc.add(seq[Math.min(T - 1, Math.max(0, f + j))].ht.clone().multiplyScalar(w)); ws += w; } out[f].ht = acc.multiplyScalar(1 / ws); }
  seq = out; }
// the effector targets smoothed too (so the pins don't chatter)
for (const n of ["L_Hand", "R_Hand", "L_Foot", "R_Foot"]) { const raw = frames.map(f => f.eff[n].clone());
  frames.forEach((f, i) => { const a = new THREE.Vector3(); let ws = 0; for (let j = -3; j <= 3; j++) { const w = Math.exp(-j * j / 2); a.add(raw[Math.min(T - 1, Math.max(0, i + j))].clone().multiplyScalar(w)); ws += w; } f.eff[n] = a.multiplyScalar(1 / ws); }); }
function pins(){ const FLOOR = 0;
  for (let f = 0; f < T; f++) {
    for (const s of ["L", "R"]) { if (O.hands !== false) twoBone(seq[f].L, seq[f].ht, `${s}_Upperarm`, `${s}_Forearm`, `${s}_Hand`, frames[f].eff[`${s}_Hand`], O.handW ?? 1);
      if (O.feet !== false) { const g = frames[f].eff[`${s}_Foot`].clone(); g.y = Math.max(g.y, FLOOR + tgtAnkle * 0.95); twoBone(seq[f].L, seq[f].ht, `${s}_Thigh`, `${s}_Calf`, `${s}_Foot`, g, O.footW ?? 1); } } } }
const jit = () => { const o = {}; const P = seq.map(f => fk(f.L, f.ht).P);
  for (const n of ["L_Hand", "R_Hand", "Head", "Hip"]) { const x = P.map(m => m.get(B(n)).clone()), r = x.map((_, i) => { const a = new THREE.Vector3(); let ws = 0; for (let j = -12; j <= 12; j++) { const w = Math.exp(-j * j / 32); a.add(x[Math.min(T - 1, Math.max(0, i + j))].clone().multiplyScalar(w)); ws += w; } return x[i].clone().sub(a.multiplyScalar(1 / ws)); });
    let s2 = 0; for (let i = 1; i < T - 1; i++) s2 += r[i - 1].clone().add(r[i + 1]).sub(r[i].clone().multiplyScalar(2)).multiplyScalar(FPS * FPS).lengthSq(); o[n] = +Math.sqrt(s2 / Math.max(1, T - 2)).toFixed(3); } return o; };
const jitterBefore = jit();
smoothSeq(O.sigma ?? 1.0, O.sigmaSpine ?? 1.7); pins();
smoothSeq(O.post ?? 1.0, (O.post ?? 1.0) * 1.5); pins();
const jitterAfter = jit();
// effector error after the pins (m)
let errH = 0, errF = 0; seq.forEach((f, i) => { const P = fk(f.L, f.ht).P; for (const s of ["L", "R"]) { errH = Math.max(errH, P.get(B(`${s}_Hand`)).distanceTo(frames[i].eff[`${s}_Hand`])); errF = Math.max(errF, P.get(B(`${s}_Foot`)).distanceTo(frames[i].eff[`${s}_Foot`])); } });

// ---------- write
for (const a of root.listAnimations()) a.dispose();
for (const n of root.listNodes()) if (n.getMesh()) { n.setMesh(null); n.setSkin(null); n.dispose(); }
for (const m of root.listMeshes()) m.dispose(); for (const s of root.listSkins()) s.dispose(); for (const m of root.listMaterials()) m.dispose(); for (const t of root.listTextures()) t.dispose();
for (const e of root.listExtensionsUsed()) e.dispose();
const buf = root.listBuffers()[0], name = O.name || anim.getName();
const an = doc.createAnimation(name), tin = doc.createAccessor().setArray(new Float32Array(seq.map((_, i) => i / FPS))).setType("SCALAR").setBuffer(buf);
const add = (node, pth, arr, type) => { const s = doc.createAnimationSampler().setInput(tin).setInterpolation("LINEAR").setOutput(doc.createAccessor().setArray(arr).setType(type).setBuffer(buf)); an.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(node).setTargetPath(pth).setSampler(s)); };
for (const n of bonesTD) { if (n.getName() === "Armature") continue; const arr = new Float32Array(T * 4); let prev = null;
  seq.forEach((f, i) => { const q = (f.L.get(n) || restL.get(n)).clone().normalize(); if (prev && q.dot(prev) < 0) { q.x = -q.x; q.y = -q.y; q.z = -q.z; q.w = -q.w; } q.toArray(arr, i * 4); prev = q; }); add(n, "rotation", arr, "VEC4"); }
const hip = new Float32Array(T * 3); seq.forEach((f, i) => f.ht.toArray(hip, i * 3)); add(B("Hip"), "translation", hip, "VEC3");
await doc.transform(resample({tolerance: 2e-4}), prune({keepLeaves: true}));
await io.write(OUT, doc);
const rep = {clip: name, frames: T, fps: FPS, fingers: HAS_FINGERS, legScale: +k.toFixed(3), mapped: order.length, maxWristErr: +errH.toFixed(3), maxAnkleErr: +errF.toFixed(3), jitterBefore, jitterAfter};
if (O.report) fs.writeFileSync(O.report, JSON.stringify(rep, null, 1));
console.log(JSON.stringify(rep));
