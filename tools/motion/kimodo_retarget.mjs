// node retarget.mjs <clip.json> <char.glb> <out.glb> [opts.json]
// Kimodo SOMA-77 motion (npz2json.py: global rotations + joint positions + foot contacts) retargeted onto the Tripo
// biped rig of char_tripo_v4.glb (41 bones, faces +X): the source is first turned to face +X (Kimodo faces +Z), then
// each mapped bone takes the source joint's world rotation with the two rest poses aligned per bone (the minimal
// rotation taking the source rest direction to the rig's rest direction; SOMA rests in a T-pose, the rig in an A-pose);
// twist bones keep their rest pose. The Hip translation is the source hips scaled by the leg-length ratio. Then, in the
// rig's own space: feet locked while Kimodo's contact labels say they are planted (two-bone leg IK, so no sliding), the
// soles kept above the floor, and optional hand targets (two-bone arm IK, blended in/out) for the keyboard, mouse,
// book or phone. Writes a GLB of the rig with one animation (all 41 bones' rotations + the Hip translation, 30 fps).
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";
import { resample, prune } from "@gltf-transform/functions";
import * as THREE from "three";

const [,, CLIP, CHAR, OUT, OPTF] = process.argv;
const O = OPTF ? JSON.parse(fs.readFileSync(OPTF)) : {};
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const SK = JSON.parse(fs.readFileSync(new URL("./soma77.json", import.meta.url)));
const JI = Object.fromEntries(SK.joints.map((n, i) => [n, i]));
const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);

// target bone <- [source joint, source child for its direction, target child for the rig's direction]
const MAP = {
  Hip: ["Hips", "Spine1", "Spine01"], Waist: ["Spine1", "Spine2", "Spine01"], Spine01: ["Spine2", "Chest", "Spine02"],
  Spine02: ["Chest", "Neck1", "NeckTwist01"], NeckTwist01: ["Neck1", "Neck2", "NeckTwist02"], NeckTwist02: ["Neck2", "Head", "Head"],
  Head: ["Head", "HeadEnd", null], Pelvis: ["Hips", null, null],
};
for (const [s, S] of [["L", "Left"], ["R", "Right"]]) Object.assign(MAP, {
  [`${s}_Clavicle`]: [`${S}Shoulder`, `${S}Arm`, `${s}_Upperarm`], [`${s}_Upperarm`]: [`${S}Arm`, `${S}ForeArm`, `${s}_Forearm`],
  [`${s}_Forearm`]: [`${S}ForeArm`, `${S}Hand`, `${s}_Hand`], [`${s}_Hand`]: [`${S}Hand`, null, null],
  [`${s}_Thigh`]: [`${S}Leg`, `${S}Shin`, `${s}_Calf`], [`${s}_Calf`]: [`${S}Shin`, `${S}Foot`, `${s}_Foot`],
  [`${s}_Foot`]: [`${S}Foot`, `${S}ToeBase`, `${s}_ToeBase`], [`${s}_ToeBase`]: [`${S}ToeBase`, null, null],
});

// ---------- the rig at rest
const doc = await io.read(CHAR), root = doc.getRoot();
const nodes = new Map(root.listNodes().map(n => [n.getName(), n]));
const parentOf = new Map(); for (const n of root.listNodes()) for (const c of n.listChildren()) parentOf.set(c, n);
const depth = n => { let k = 0; while ((n = parentOf.get(n))) k++; return k; };
const skinJoints = root.listSkins()[0].listJoints();
const bonesTD = root.listNodes().filter(n => skinJoints.includes(n) || n.getName() === "Armature").sort((a, b) => depth(a) - depth(b));
const restL = new Map(bonesTD.map(n => [n, new THREE.Quaternion(...n.getRotation())]));
const restT = new Map(bonesTD.map(n => [n, V(n.getTranslation())]));
const restS = new Map(bonesTD.map(n => [n, n.getScale()[0]]));
function fk(localQ, hipT){                      // world rotation, position (m), scale for every bone; localQ: Map node->quat
  const W = new Map(), P = new Map(), S = new Map();
  for (const n of bonesTD) {
    const p = parentOf.get(n), q = localQ.get(n) || restL.get(n), t = (n.getName() === "Hip" && hipT) ? hipT : restT.get(n);
    if (!p || !W.has(p)) { W.set(n, q.clone()); P.set(n, t.clone().multiplyScalar(1)); S.set(n, restS.get(n)); continue; }
    W.set(n, W.get(p).clone().multiply(q)); P.set(n, t.clone().multiplyScalar(S.get(p)).applyQuaternion(W.get(p)).add(P.get(p))); S.set(n, S.get(p) * restS.get(n));
  }
  return {W, P, S};
}
const rest = fk(new Map());
const B = name => nodes.get(name);
const restP = name => rest.P.get(B(name)).clone();

// ---------- the source at rest (identity rotations = SOMA's T-pose), turned to face +X
const C = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI / 2), Ci = C.clone().invert();
const neutral = SK.neutral.map(p => V(p).applyQuaternion(C));
const srcLeg = neutral[JI.LeftLeg].distanceTo(neutral[JI.LeftShin]) + neutral[JI.LeftShin].distanceTo(neutral[JI.LeftFoot]);
const tgtLeg = restP("L_Thigh").distanceTo(restP("L_Calf")) + restP("L_Calf").distanceTo(restP("L_Foot"));
const scale = O.scale || tgtLeg / srcLeg;
const ALIGN = {};
const order = Object.keys(MAP).sort((a, b) => depth(B(a)) - depth(B(b)));
for (const b of order) {
  const [src, sc, tc] = MAP[b];
  let ds = sc ? neutral[JI[sc]].clone().sub(neutral[JI[src]]).normalize() : null;
  let dt = tc ? restP(tc).sub(restP(b)).normalize() : null;
  if (b === "Head") dt = new THREE.Vector3(0, 1, 0);
  if (ds && dt) ALIGN[b] = new THREE.Quaternion().setFromUnitVectors(ds, dt);
  else { const p = parentOf.get(B(b)); let a = null; for (let n = p; n && !a; n = parentOf.get(n)) a = ALIGN[n.getName()]; ALIGN[b] = a ? a.clone() : new THREE.Quaternion(); }
}

// ---------- per frame
const CL = JSON.parse(fs.readFileSync(CLIP)), T = CL.T, fps = CL.fps;
const SEATW = (t) => { if (!O.seated) return 1; let w = 0; for (const [a, b] of O.seated) { const r = 0.5;
  w = Math.max(w, t < a - r || t > b + r ? 0 : t < a ? (t - a + r) / r : t > b ? (b + r - t) / r : 1); } return w * w * (3 - 2 * w); };
const off = new THREE.Vector3();
const seatOff = O.offset ? V(O.offset) : new THREE.Vector3();          // where the source's origin goes in the rig's space (m)
// the rig's Hip sits at its thigh joints (SOMA's Hips root is 8 cm above its hip joints): the Hip follows the midpoint of
// SOMA's two hip joints; and the rig's ankle is lower above its soles than SOMA's (scaled): the whole body goes down by that
const srcAnkle = neutral[JI.LeftFoot].y - Math.min(neutral[JI.LeftToeEnd].y, neutral[JI.LeftToeBase].y);
const tgtAnkle = (restP("L_Foot").y + restP("R_Foot").y) / 2;
off.y += tgtAnkle - scale * srcAnkle;
const frames = [];
for (let t = 0; t < T; t++) {
  const G = CL.quat[t].map(q => C.clone().multiply(new THREE.Quaternion(q[0], q[1], q[2], q[3])).multiply(Ci));
  const Pw = CL.pos[t].map(p => V(p).applyQuaternion(C));
  const W = {};
  for (const b of order) W[b] = G[JI[MAP[b][0]]].clone().multiply(ALIGN[b].clone().invert()).multiply(rest.W.get(B(b)));
  const sw = SEATW(t / fps);
  const rgt = Pw[JI.RightLeg].clone().sub(Pw[JI.LeftLeg]).setY(0).normalize(), fwd = new THREE.Vector3(0, 1, 0).cross(rgt);
  // leanCurve [[t, rad], ...]: a measured torso pitch over time (+ = forward), added to O.lean; headCurve likewise for the head
  const curve = (c, tt) => { if (!c) return 0; let i = 0; while (i + 1 < c.length && c[i + 1][0] <= tt) i++; const a = c[i], b = c[Math.min(i + 1, c.length - 1)]; return b[0] > a[0] ? a[1] + (b[1] - a[1]) * Math.min(1, Math.max(0, (tt - a[0]) / (b[0] - a[0]))) : a[1]; };
  const leanT = (O.lean || 0) + curve(O.leanCurve, t / fps), headT = curve(O.headCurve, t / fps);
  if (leanT || headT) {                          // the torso (Waist and everything above it) pitched forward about the rig's lateral axis
    const lq = new THREE.Quaternion().setFromAxisAngle(rgt, -leanT * sw);
    const hq = new THREE.Quaternion().setFromAxisAngle(rgt, ((O.leanHead ?? 0) * leanT - headT) * sw);   // the neck and head turned back up by a share of it (+ the measured head change)
    const under = (b, root) => { let n = B(b); while (n) { if (n.getName() === root) return true; n = parentOf.get(n); } return false; };
    for (const b of order) { if (under(b, "Waist")) W[b].premultiply(lq); if (under(b, "NeckTwist01")) W[b].premultiply(hq); }
  }
  // rollCurve [[t, rad], ...]: a measured sideways torso lean (+ = toward his left), the head turned back by rollHead of it
  const rollT = curve(O.rollCurve, t / fps);
  if (rollT) {
    const under = (b, root) => { let n = B(b); while (n) { if (n.getName() === root) return true; n = parentOf.get(n); } return false; };
    const rq = new THREE.Quaternion().setFromAxisAngle(fwd, -rollT * sw), hq = new THREE.Quaternion().setFromAxisAngle(fwd, (O.rollHead ?? 0) * rollT * sw);
    for (const b of order) { if (under(b, "Waist")) W[b].premultiply(rq); if (under(b, "NeckTwist01")) W[b].premultiply(hq); }
  }
  // sideCurve [[t, m], ...]: the hips slid sideways on the seat (+ = toward his left), the measured weight shift's pelvis part
  const sideT = curve(O.sideCurve, t / fps);
  if (O.rootKeys) {                             // timed root offsets (rig space, m): [[t, dx, dy, dz], ...], smoothstep between keys
    const K = O.rootKeys, tt = t / fps; let i = 0; while (i + 1 < K.length && K[i + 1][0] <= tt) i++;
    const a = K[i], b = K[Math.min(i + 1, K.length - 1)]; let u = b[0] > a[0] ? Math.min(1, Math.max(0, (tt - a[0]) / (b[0] - a[0]))) : 0; u = u * u * (3 - 2 * u);
    frames.rk = new THREE.Vector3(a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u);
  } else frames.rk = new THREE.Vector3();
  const hip = Pw[JI.LeftLeg].clone().add(Pw[JI.RightLeg]).multiplyScalar(0.5 * scale).add(off).add(fwd.clone().multiplyScalar(seatOff.x)).add(new THREE.Vector3(0, seatOff.y * sw, 0)).add(rgt.clone().multiplyScalar(seatOff.z - sideT)).add(frames.rk);
  frames.push({W, hip, Pw, fwd});
}
function toLocal(Wmap, hipWorld){                // world rotations of mapped bones -> local quats (Map), Hip local translation
  const L = new Map(), Wc = new Map();
  for (const n of bonesTD) {
    const p = parentOf.get(n), name = n.getName();
    const pw = p ? Wc.get(p) : new THREE.Quaternion();
    const w = Wmap[name] ? Wmap[name] : pw.clone().multiply(restL.get(n));
    Wc.set(n, w); if (Wmap[name]) L.set(n, pw.clone().invert().multiply(w));
  }
  // Hip translation: its parent's (Root) world transform inverted
  const pr = parentOf.get(B("Hip")), pw = rest.W.get(pr), pp = rest.P.get(pr), ps = rest.S.get(pr);
  const ht = hipWorld.clone().sub(pp).applyQuaternion(pw.clone().invert()).multiplyScalar(1 / ps);
  return {L, ht};
}
let seq = frames.map(f => toLocal(f.W, f.hip));

// jitter: RMS of the 2nd derivative (m/s^2) of the wrists' and head's positions (rig space), before and after
const JIT = ["L_Hand", "R_Hand", "Head", "Hip"];
function jitter(sq){ const P = sq.map(f => fk(f.L, f.ht).P); const o = {};
  // high-frequency part only: the track minus its Gaussian-smoothed self (sigma 4 frames, ~1.2 Hz and up kept out), so
  // deliberate motion (a reach, a step) does not count as jitter
  for (const n of JIT) { const x = P.map(m => m.get(B(n)).clone()), r = x.map((_, k) => { const a = new THREE.Vector3(); let ws = 0;
      for (let j = -12; j <= 12; j++) { const kk = Math.min(x.length - 1, Math.max(0, k + j)), w = Math.exp(-j * j / 32); a.add(x[kk].clone().multiplyScalar(w)); ws += w; }
      return x[k].clone().sub(a.multiplyScalar(1 / ws)); });
    let s2 = 0; for (let k = 1; k < r.length - 1; k++) s2 += r[k - 1].clone().add(r[k + 1]).sub(r[k].clone().multiplyScalar(2)).multiplyScalar(fps * fps).lengthSq();
    o[n] = +Math.sqrt(s2 / Math.max(1, r.length - 2)).toFixed(3); }
  return o; }
const jitterBefore = jitter(seq);
// zero-phase smoothing: a Gaussian kernel over time (both directions, so no lag), rotations averaged in quaternion space
// (sign-aligned to the centre frame, normalised; for small angles that is the slerp average), the Hip translation too.
// Cut-off ~5 Hz on the limbs (sigma 1 frame), ~3 Hz on the spine, neck and head (sigma 1.7 frames)
function smoothSeq(sigL, sigS) {
  const SPINE = new Set(["Hip", "Waist", "Spine01", "Spine02", "NeckTwist01", "NeckTwist02", "Head", "Pelvis"]);
  const kern = sg => { const r = Math.ceil(sg * 3), w = []; for (let j = -r; j <= r; j++) w.push(Math.exp(-j * j / (2 * sg * sg))); return {r, w}; };
  const KL = kern(sigL), KS = kern(sigS);
  const out = seq.map(f => ({L: new Map(f.L), ht: f.ht.clone()}));
  for (const n of bonesTD) { const name = n.getName(); if (!seq[0].L.has(n)) continue; const K = SPINE.has(name) ? KS : KL;
    for (let k = 0; k < T; k++) { const c = seq[k].L.get(n), acc = new THREE.Vector4(0, 0, 0, 0); let ws = 0;
      for (let j = -K.r; j <= K.r; j++) { const kk = Math.min(T - 1, Math.max(0, k + j)), q = seq[kk].L.get(n), w = K.w[j + K.r];
        const sgn = (q.x * c.x + q.y * c.y + q.z * c.z + q.w * c.w) < 0 ? -1 : 1; acc.x += sgn * w * q.x; acc.y += sgn * w * q.y; acc.z += sgn * w * q.z; acc.w += sgn * w * q.w; ws += w; }
      out[k].L.set(n, new THREE.Quaternion(acc.x, acc.y, acc.z, acc.w).normalize()); } }
  for (let k = 0; k < T; k++) { const acc = new THREE.Vector3(); let ws = 0;
    for (let j = -KS.r; j <= KS.r; j++) { const kk = Math.min(T - 1, Math.max(0, k + j)), w = KS.w[j + KS.r]; acc.add(seq[kk].ht.clone().multiplyScalar(w)); ws += w; }
    out[k].ht = acc.multiplyScalar(1 / ws); }
  seq = out;
}
if (O.smooth !== false) smoothSeq(O.smoothSigma ?? 1.0, O.smoothSigmaSpine ?? 1.7);
// seat height: per-frame Hip offsets (m, world y) measured on the skin against the seat by the scene (seat.mjs), applied
// in the seated windows
if (O.hipDY) { const pr = parentOf.get(B("Hip"));
  seq.forEach((f, k) => { const x = Math.min(O.hipDY.length - 1, (k / fps) / 0.1), i = Math.floor(x), u = x - i, d = (O.hipDY[i] * (1 - u) + O.hipDY[Math.min(i + 1, O.hipDY.length - 1)] * u) * SEATW(k / fps);
    f.ht.add(new THREE.Vector3(0, d / rest.S.get(pr), 0).applyQuaternion(rest.W.get(pr).clone().invert())); }); }

// ---------- two-bone IK (rig space): bend a-b-c so that c reaches `goal`, the bend plane kept by the current mid joint
function twoBone(L, ht, a, b, c, goal, w = 1){
  const st = fk(L, ht), A = st.P.get(B(a)), Bp = st.P.get(B(b)), Cp = st.P.get(B(c));
  const la = A.distanceTo(Bp), lb = Bp.distanceTo(Cp); let d = A.distanceTo(goal); d = Math.min(d, (la + lb) * 0.999);
  const cur = A.distanceTo(Cp);
  // 1) the mid joint's angle so |A C| = d
  const ang = (x) => Math.acos(THREE.MathUtils.clamp((la * la + lb * lb - x * x) / (2 * la * lb), -1, 1));
  const axis = Bp.clone().sub(A).cross(Cp.clone().sub(Bp)); if (axis.lengthSq() < 1e-10) axis.set(0, 0, 1).applyQuaternion(st.W.get(B(a)));
  axis.normalize();
  const dTheta = ang(cur) - ang(d);              // more bend -> shorter
  const qb = new THREE.Quaternion().setFromAxisAngle(axis, dTheta);
  const Wb = qb.clone().multiply(st.W.get(B(b)));
  // 2) swing the upper bone so C lands on the goal
  const Cn = Cp.clone().sub(Bp).applyQuaternion(qb).add(Bp);
  const qa = new THREE.Quaternion().setFromUnitVectors(Cn.clone().sub(A).normalize(), goal.clone().sub(A).normalize());
  const Wa = qa.clone().multiply(st.W.get(B(a)));
  const Wb2 = qa.clone().multiply(Wb);
  const Wc = st.W.get(B(c)).clone();               // keep the end bone's world rotation
  const pa = st.W.get(parentOf.get(B(a)));
  const La = pa.clone().invert().multiply(Wa);
  // b's parent chain may include twist bones (identity local): walk it
  const chainW = (n, Wtop) => { let w = Wtop; const path = []; for (let x = parentOf.get(B(n)); x !== B(a); x = parentOf.get(x)) path.unshift(x); for (const x of path) w = w.clone().multiply(L.get(x) || restL.get(x)); return w; };
  const pbW = chainW(b, Wa), Lb = pbW.clone().invert().multiply(Wb2);
  const pcW = (() => { let w = Wb2; const path = []; for (let x = parentOf.get(B(c)); x !== B(b); x = parentOf.get(x)) path.unshift(x); for (const x of path) w = w.clone().multiply(L.get(x) || restL.get(x)); return w; })();
  const Lc = pcW.clone().invert().multiply(Wc);
  for (const [n, q] of [[a, La], [b, Lb], [c, Lc]]) { const cur0 = L.get(B(n)) || restL.get(B(n)); L.set(B(n), cur0.clone().slerp(q, w)); }
}

// bed: O.bed = {x0, x1, z0, z1, top} (world) with O.place = [x, y, z, ry] (the rig's placement in the room): while a body bone
// is over the mattress, the root rises until that bone's underside (bone height minus its radius) is on the mattress top;
// the lift is smoothed over 0.3 s and kept on while it is needed
if (O.bed && O.place) {
  const R = {Hip: 0.13, Waist: 0.15, Spine01: 0.17, Spine02: 0.17, NeckTwist02: 0.12, Head: 0.13, L_ThighTwist02: 0.09, R_ThighTwist02: 0.09, L_ThighTwist01: 0.10, R_ThighTwist01: 0.10};
  const pq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), O.place[3]), pp = V(O.place.slice(0, 3)), bd = O.bed;
  const need = seq.map(f => { const st = fk(f.L, f.ht); let m = 0;
    for (const [n, r] of Object.entries(R)) { const w = st.P.get(B(n)).clone().applyQuaternion(pq).add(pp);
      if (w.x > bd.x0 + 0.03 && w.x < bd.x1 - 0.03 && w.z > bd.z0 + 0.03 && w.z < bd.z1 - 0.03) m = Math.max(m, bd.top + r - w.y); }
    return m; });
  const n = 9, lift = need.map((_, k) => { let mx = 0; for (let j = -n; j <= n; j++) if (need[k + j] != null) mx = Math.max(mx, need[k + j] * (1 - Math.abs(j) / (n + 1))); return mx; });
  const pr = parentOf.get(B("Hip"));
  seq.forEach((f, k) => { f.ht.add(new THREE.Vector3(0, lift[k] / rest.S.get(pr), 0).applyQuaternion(rest.W.get(pr).clone().invert())); f.bedLift = lift[k]; });
  console.log("bed lift max", Math.max(...lift).toFixed(3), "m");
}
// ---------- foot contacts: lock planted feet (sole points) and keep them above the floor
const FLOOR = O.floor ?? 0;
const ankleH = {L: restP("L_Foot").y, R: restP("R_Foot").y};
if (CL.contacts && O.footlock !== false) {
  for (const [s, ci] of [["L", [0, 1]], ["R", [2, 3]]]) {
    const lowA = seq.map(f => fk(f.L, f.ht).P.get(B(`${s}_Foot`)).y < FLOOR + ankleH[s] + 0.10);   // the ankle near the floor (not up on a bed)
    const on = CL.contacts.map((c, k) => Math.max(c[ci[0]], c[ci[1]]) > 0.5 && lowA[k]), heel = CL.contacts.map(c => c[ci[0]] > 0.5);
    let t = 0;
    while (t < T) {
      if (!on[t]) { t++; continue; }
      let e = t; while (e + 1 < T && on[e + 1]) e++;
      // the planted ankle: its mean position over the run (xz), y not below the rest ankle height
      const ps = []; for (let k = t; k <= e; k++) ps.push(fk(seq[k].L, seq[k].ht).P.get(B(`${s}_Foot`)));
      const m = ps.reduce((a, p) => a.add(p), new THREE.Vector3()).multiplyScalar(1 / ps.length);
      if (m.y > FLOOR + ankleH[s] + 0.12) { t = e + 1; continue; }   // planted on the bed, not the floor: no floor lock
      if (O.footShift) m.add(frames[Math.round((t + e) / 2)].fwd.clone().multiplyScalar(O.footShift[0] * SEATW((t + e) / 2 / fps)));          // planted feet moved (rig space), e.g. further forward under a tall seat
      for (let k = Math.max(0, t - 3); k <= Math.min(T - 1, e + 3); k++) {
        const w = k < t ? (k - t + 4) / 4 : k > e ? (e + 4 - k) / 4 : 1;
        const cur = fk(seq[k].L, seq[k].ht).P.get(B(`${s}_Foot`));
        // heel down: the ankle at its rest height over the floor; toe only: where it is, not below that
        const HL = (O.heelLift || 0) * SEATW(k / fps);
        const goal = new THREE.Vector3(m.x, heel[Math.min(Math.max(k, t), e)] ? FLOOR + ankleH[s] + HL : Math.max(cur.y, FLOOR + ankleH[s] * 0.97), m.z);
        if (cur.distanceTo(goal) > 0.002) twoBone(seq[k].L, seq[k].ht, `${s}_Thigh`, `${s}_Calf`, `${s}_Foot`, goal, w);
        if (HL) {                                    // heels raised: the foot pitched down until the toe joint is back on the floor
          const st = fk(seq[k].L, seq[k].ht), A = st.P.get(B(`${s}_Foot`)), To = st.P.get(B(`${s}_ToeBase`));
          const fw = To.clone().sub(A).setY(0).normalize(), ax = new THREE.Vector3(0, 1, 0).cross(fw).normalize();
          const len = To.distanceTo(A), want = FLOOR + restP(`${s}_ToeBase`).y - A.y;     // the toe joint's height relative to the ankle
          const now = To.y - A.y, ang = (Math.asin(THREE.MathUtils.clamp(-want / len, -1, 1)) - Math.asin(THREE.MathUtils.clamp(-now / len, -1, 1))) * w;
          const fq = new THREE.Quaternion().setFromAxisAngle(ax, ang), Wf = fq.multiply(st.W.get(B(`${s}_Foot`)));
          const pw = st.W.get(parentOf.get(B(`${s}_Foot`))); seq[k].L.set(B(`${s}_Foot`), pw.clone().invert().multiply(Wf));
        }
      }
      t = e + 1;
    }
  }
}
// seated feet: O.feetPin = {fwd, side} (m): in the seated windows both feet are planted flat at the hips' position + fwd
// along his facing, +-side to his left/right (soles on the floor, the foot pitched so its toe joint is down too)
if (O.feetPin) for (let k = 0; k < T; k++) {
  const w = SEATW(k / fps); if (w <= 0) continue;
  const st0 = fk(seq[k].L, seq[k].ht), hp = st0.P.get(B("Hip")), fw = frames[k].fwd, rg = new THREE.Vector3(0, 1, 0).cross(fw).multiplyScalar(-1);
  for (const [sd, sg] of [["L", -1], ["R", 1]]) {
    const cur = fk(seq[k].L, seq[k].ht).P.get(B(`${sd}_Foot`));
    const goal = hp.clone().add(fw.clone().multiplyScalar(O.feetPin.fwd)).add(rg.clone().multiplyScalar(sg * O.feetPin.side)); goal.y = FLOOR + ankleH[sd];
    twoBone(seq[k].L, seq[k].ht, `${sd}_Thigh`, `${sd}_Calf`, `${sd}_Foot`, cur.clone().lerp(goal, w), 1);
    const st = fk(seq[k].L, seq[k].ht), A = st.P.get(B(`${sd}_Foot`)), To = st.P.get(B(`${sd}_ToeBase`));
    const fdir = To.clone().sub(A).setY(0).normalize(), ax = new THREE.Vector3(0, 1, 0).cross(fdir).normalize(), len = To.distanceTo(A);
    const want = FLOOR + restP(`${sd}_ToeBase`).y - A.y, now = To.y - A.y;
    const ang = (Math.asin(THREE.MathUtils.clamp(-want / len, -1, 1)) - Math.asin(THREE.MathUtils.clamp(-now / len, -1, 1))) * w;
    const Wf = new THREE.Quaternion().setFromAxisAngle(ax, ang).multiply(st.W.get(B(`${sd}_Foot`)));
    seq[k].L.set(B(`${sd}_Foot`), st.W.get(parentOf.get(B(`${sd}_Foot`))).clone().invert().multiply(Wf));
  }
}
// floor: lift the hips by any sole under the floor (smoothed)
{
  const pen = seq.map(f => { const st = fk(f.L, f.ht); let m = 0; for (const s of ["L", "R"]) { m = Math.max(m, FLOOR + ankleH[s] * 0.9 - st.P.get(B(`${s}_Foot`)).y, FLOOR + 0.015 - st.P.get(B(`${s}_ToeBase`)).y); } return m; });
  seq.forEach((f, t) => { let s = 0, n = 0; for (let k = -3; k <= 3; k++) if (pen[t + k] != null) { s += pen[t + k]; n++; } f.lift = s / n; });
  if (O.floorLift !== false) seq.forEach(f => { const pr = parentOf.get(B("Hip")); f.ht.add(new THREE.Vector3(0, f.lift / rest.S.get(pr), 0).applyQuaternion(rest.W.get(pr).clone().invert())); });
}
// hand targets: [{hand: "L"|"R", from, to (s), ramp (s), pos: [x,y,z] rig space | path: [[t,x,y,z],...]}]
// loop: the last `loop` seconds ease into the first frame (the next cycle's), rotations and the Hip translation
if (O.loop) {
  const n = Math.min(T - 1, Math.round(O.loop * fps));
  for (let k = T - n; k < T; k++) { let w = (k - (T - n) + 1) / n; w = w * w * (3 - 2 * w);
    for (const [nd, q] of seq[k].L) seq[k].L.set(nd, q.clone().slerp(seq[0].L.get(nd) || restL.get(nd), w));
    seq[k].ht.lerp(seq[0].ht, w); }
}
// the hand's own direction (wrist towards the knuckles) in its bone frame: the rest forearm-to-wrist direction
const handDir = Object.fromEntries(["L", "R"].map(sd => [sd, restP(`${sd}_Hand`).sub(restP(`${sd}_Forearm`)).normalize().applyQuaternion(rest.W.get(B(`${sd}_Hand`)).clone().invert())]));
function runHands(){
for (const h of O.hands || []) {
  // keepDetail: Kimodo's own small wrist motion (its offset from its 1 s running mean) rides on the target
  let det = null;
  if (h.keepDetail) { const wp = seq.map(f => fk(f.L, f.ht).P.get(B(`${h.hand}_Hand`)));
    const raw = wp.map((p, k) => { const m = new THREE.Vector3(); let n = 0; for (let j = Math.max(0, k - 15); j <= Math.min(T - 1, k + 15); j++) { m.add(wp[j]); n++; } return p.clone().sub(m.multiplyScalar(1 / n)).multiplyScalar(h.keepDetail); });
    det = raw.map((_, k) => { const a = new THREE.Vector3(); let ws = 0; for (let j = -12; j <= 12; j++) { const kk = Math.min(T - 1, Math.max(0, k + j)), w = Math.exp(-j * j / 32); a.add(raw[kk].clone().multiplyScalar(w)); ws += w; } return a.multiplyScalar(1 / ws); }); }
  for (let k = 0; k < T; k++) {
    const t = k / fps; if (t < h.from - h.ramp || t > h.to + h.ramp) continue;
    const w = t < h.from ? (t - h.from + h.ramp) / h.ramp : t > h.to ? (h.to + h.ramp - t) / h.ramp : 1;
    let g; if (h.path) { let i = 0; while (i + 1 < h.path.length && h.path[i + 1][0] <= t) i++; const a = h.path[i], b = h.path[Math.min(i + 1, h.path.length - 1)];
      let u = b[0] > a[0] ? THREE.MathUtils.clamp((t - a[0]) / (b[0] - a[0]), 0, 1) : 0; const ue = u * u * u * (u * (6 * u - 15) + 10);   // smootherstep: ease in and out
      g = V(a.slice(1, 4)).lerp(V(b.slice(1, 4)), ue); if (b[4]) g.y += b[4] * Math.sin(Math.PI * ue); } else g = V(h.pos);
    if (h.relHip) g.add(fk(seq[k].L, seq[k].ht).P.get(B("Hip")));
    if (det) g.add(det[k]);
    const ws = w * w * (3 - 2 * w);
    twoBone(seq[k].L, seq[k].ht, `${h.hand}_Upperarm`, `${h.hand}_Forearm`, `${h.hand}_Hand`, g, ws);
    if (h.pitch != null) {
      const st = fk(seq[k].L, seq[k].ht), Wh = st.W.get(B(`${h.hand}_Hand`)), dl = handDir[h.hand].clone().applyQuaternion(Wh);
      const want = dl.clone().setY(0).normalize().multiplyScalar(Math.cos(h.pitch)).setY(Math.sin(h.pitch));
      const q = new THREE.Quaternion().slerpQuaternions(new THREE.Quaternion(), new THREE.Quaternion().setFromUnitVectors(dl, want), ws);
      const pw = st.W.get(parentOf.get(B(`${h.hand}_Hand`))); seq[k].L.set(B(`${h.hand}_Hand`), pw.clone().invert().multiply(q.multiply(Wh)));
    }
  }
}
}
runHands();

// hands on the bed rest on the mattress, not in it
if (O.bed && O.place) {
  const pq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), O.place[3]), pqi = pq.clone().invert(), pp = V(O.place.slice(0, 3)), bd = O.bed;
  for (let k = 0; k < T; k++) for (const sd of ["L", "R"]) {
    const st = fk(seq[k].L, seq[k].ht), w = st.P.get(B(`${sd}_Hand`)).clone().applyQuaternion(pq).add(pp);
    if (w.x > bd.x0 && w.x < bd.x1 && w.z > bd.z0 && w.z < bd.z1 && w.y < bd.top + 0.08) {
      w.y = bd.top + 0.08; twoBone(seq[k].L, seq[k].ht, `${sd}_Upperarm`, `${sd}_Forearm`, `${sd}_Hand`, w.sub(pp).applyQuaternion(pqi), 1); }
  }
}
// hands over the desk rest on its top, not in it (O.desk {x0, x1, z0, z1, top} in the room, O.place the rig's root there)
if (O.desk && O.place) {
  const pq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), O.place[3]), pqi = pq.clone().invert(), pp = V(O.place.slice(0, 3)), dk = O.desk;
  for (let k = 0; k < T; k++) for (const sd of ["L", "R"]) {
    const st = fk(seq[k].L, seq[k].ht), w = st.P.get(B(`${sd}_Hand`)).clone().applyQuaternion(pq).add(pp);
    if (w.x > dk.x0 - 0.05 && w.x < dk.x1 + 0.05 && w.z > dk.z0 && w.z < dk.z1 + 0.06 && w.y < dk.top + 0.045) {
      w.y = dk.top + 0.045; twoBone(seq[k].L, seq[k].ht, `${sd}_Upperarm`, `${sd}_Forearm`, `${sd}_Hand`, w.sub(pp).applyQuaternion(pqi), 1); }
  }
}
// final pass: the joins, foot locks and lifts above can leave small pops; a last zero-phase smoothing of every bone and the
// Hip, then the hand pins re-solved so the contacts stay exact
if (O.postSmooth) { smoothSeq(O.postSmooth, O.postSmooth * 1.5); runHands(); }
// ---------- held finger poses (Kimodo has no fingers): photo-referenced shapes, as in mh_retarget.mjs
const HAS_FINGERS = !!B("finger2-1.L");
const HAND_POSES = {
  // fingers together, a gentle dome, tips resting on the letter keys; thumb down toward the space bar
  keys:  {flex: {2: [25, 35, 15], 3: [28, 38, 15], 4: [30, 40, 18], 5: [32, 42, 18]}, spread: {2: 3, 3: 0, 4: -3, 5: -6}, thumb: [0.060, 0.030, 0.040], orient: {pitch: -12, yaw: 12}},
  // palm grip: index and middle nearly straight on the buttons, ring and little finger curled round the far side, thumb flat along the near side
  mouse: {flex: {2: [8, 12, 6], 3: [8, 12, 6], 4: [28, 40, 20], 5: [35, 45, 25]}, spread: {2: 4, 3: 0, 4: -6, 5: -10}, thumb: [0.065, 0.045, 0.025], orient: {pitch: -8, yaw: 0}},
  // at rest (on the thigh or the desk): loosely curled
  relax: {flex: {2: [15, 25, 10], 3: [17, 27, 10], 4: [19, 29, 12], 5: [21, 31, 12]}, spread: {2: 4, 3: 0, 4: -4, 5: -8}, thumb: [0.070, 0.035, 0.030]}};
const HB = {}; for (const s of ["L", "R"]) { if (!B(`finger3-1.${s}`)) continue;
  const w = restP(`${s}_Hand`), x = restP(`finger3-1.${s}`).sub(w).normalize(), y0 = restP(`finger5-1.${s}`).sub(restP(`finger2-1.${s}`));
  const y = y0.sub(x.clone().multiplyScalar(y0.dot(x))).normalize(), z = x.clone().cross(y), th = restP(`finger1-1.${s}`).sub(w);
  HB[s] = {x, t: y.clone().negate(), n: z.clone().multiplyScalar(z.dot(th) > 0 ? 1 : -1)}; }
// the hand's own turn as in the photographs: palm down, fingers forward along the desk (rig +X), pitched down `pitch` deg,
// turned `yaw` deg inward (toward his middle); the page's wrist pin only turns the arm a little from there
function orientHand(L, ht, s, o){ const DEG = Math.PI / 180, st = fk(L, ht), Hn = B(`${s}_Hand`);
  const inward = s === "L" ? 1 : -1;                                    // left = -Z: inward is +Z for the left hand
  const x = new THREE.Vector3(Math.cos(o.pitch * DEG), Math.sin(o.pitch * DEG), 0).applyAxisAngle(new THREE.Vector3(0, 1, 0), -inward * o.yaw * DEG).normalize();
  const n0 = new THREE.Vector3(0, -1, 0), n = n0.sub(x.clone().multiplyScalar(n0.dot(x))).normalize();
  const bas = (a, b) => new THREE.Matrix4().makeBasis(a, b, a.clone().cross(b));
  const R = new THREE.Quaternion().setFromRotationMatrix(bas(x, n).multiply(bas(HB[s].x, HB[s].n).transpose()));
  L.set(Hn, st.W.get(B(`${s}_Forearm`)).clone().invert().multiply(R.multiply(rest.W.get(Hn)))); }
function poseHand(L, ht, s, P){ const DEG = Math.PI / 180; if (P.orient) orientHand(L, ht, s, P.orient); let st = fk(L, ht); const Hn = B(`${s}_Hand`);
  const Rh = st.W.get(Hn).clone().multiply(rest.W.get(Hn).clone().invert()), xw = HB[s].x.clone().applyQuaternion(Rh), tw = HB[s].t.clone().applyQuaternion(Rh);
  const nn = HB[s].n.clone().applyQuaternion(Rh); nn.sub(xw.clone().multiplyScalar(nn.dot(xw))).normalize();
  for (let m = 1; m <= 4; m++) { const mb = B(`metacarpal${m}.${s}`); if (mb) L.set(mb, restL.get(mb).clone()); }
  st = fk(L, ht);
  for (let f = 2; f <= 5; f++) { let parW = st.W.get(parentOf.get(B(`finger${f}-1.${s}`))), phi = 0;
    const toThumb = xw.clone().cross(tw).dot(nn) > 0 ? 1 : -1;            // the spread's sign: + turns toward the thumb
    const df = xw.clone().applyAxisAngle(nn, toThumb * (P.spread[f] || 0) * DEG), ax = df.clone().cross(nn).normalize();
    for (let j = 1; j <= 3; j++) { const b = B(`finger${f}-${j}.${s}`); let W = parW.clone().multiply(restL.get(b));
      const dir = (j < 3 ? restP(`finger${f}-${j + 1}.${s}`).sub(restP(`finger${f}-${j}.${s}`)) : restP(`finger${f}-3.${s}`).sub(restP(`finger${f}-2.${s}`))).normalize().applyQuaternion(rest.W.get(b).clone().invert()).applyQuaternion(W);
      phi += P.flex[f][j - 1] * DEG; const want = df.clone().applyAxisAngle(ax, phi);
      W = new THREE.Quaternion().setFromUnitVectors(dir, want).multiply(W); L.set(b, parW.clone().invert().multiply(W)); parW = W; } }
  const TB = [1, 2, 3].map(j => B(`finger1-${j}.${s}`)); for (const b of TB) L.set(b, restL.get(b).clone());
  const goal = st.P.get(Hn).clone().add(xw.clone().multiplyScalar(P.thumb[0])).add(tw.clone().multiplyScalar(P.thumb[1])).add(nn.clone().multiplyScalar(P.thumb[2]));
  const tip = s2 => { const a = B(`finger1-3.${s}`), off = restP(`finger1-3.${s}`).sub(restP(`finger1-2.${s}`)).multiplyScalar(0.85);
    return s2.P.get(a).clone().add(off.applyQuaternion(rest.W.get(a).clone().invert()).applyQuaternion(s2.W.get(a))); };
  for (let it = 0; it < 12; it++) for (let j = 2; j >= 0; j--) { const s2 = fk(L, ht), pj = s2.P.get(TB[j]), a = tip(s2).sub(pj).normalize(), g = goal.clone().sub(pj).normalize();
    let q = new THREE.Quaternion().setFromUnitVectors(a, g); const ang = 2 * Math.acos(Math.min(1, Math.abs(q.w))); if (ang > 0.35) q = new THREE.Quaternion().slerp(q, 0.35 / ang);
    const Wj = q.multiply(s2.W.get(TB[j])); L.set(TB[j], s2.W.get(parentOf.get(TB[j])).clone().invert().multiply(Wj)); } }
if (O.handPose && HAS_FINGERS) for (let f = 0; f < T; f++) for (const s of ["L", "R"]) if (O.handPose[s]) poseHand(seq[f].L, seq[f].ht, s, HAND_POSES[O.handPose[s]]);
// hipTo [x, y, z]: the Hip translation moved so the clip starts with the hips where another clip has them (desk_watch)
if (O.hipTo) { const d = new THREE.Vector3(...O.hipTo).sub(seq[0].ht); for (const f of seq) f.ht.add(d); }
// hipLift (m): the hips raised in the rig's space (onto the cushion rather than into it), after the alignment
if (O.hipLift) { const pr = parentOf.get(B("Hip")), d = new THREE.Vector3(0, O.hipLift / rest.S.get(pr), 0).applyQuaternion(rest.W.get(pr).clone().invert()); for (const f of seq) f.ht.add(d); }
// ---------- write: the rig without its mesh, one animation
for (const a of root.listAnimations()) a.dispose();
for (const n of root.listNodes()) if (n.getMesh()) { n.setMesh(null); n.setSkin(null); n.dispose(); }
for (const m of root.listMeshes()) m.dispose(); for (const s of root.listSkins()) s.dispose();
for (const m of root.listMaterials()) m.dispose(); for (const t of root.listTextures()) t.dispose();
for (const e of root.listExtensionsUsed()) e.dispose();
const buf = root.listBuffers()[0];
const name = O.name || "clip";
const anim = doc.createAnimation(name), tin = doc.createAccessor().setArray(new Float32Array(seq.map((_, t) => t / fps))).setType("SCALAR").setBuffer(buf);
const add = (node, pth, arr, type) => { const s = doc.createAnimationSampler().setInput(tin).setInterpolation("LINEAR")
  .setOutput(doc.createAccessor().setArray(arr).setType(type).setBuffer(buf)); anim.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(node).setTargetPath(pth).setSampler(s)); };
for (const n of bonesTD) { if (n.getName() === "Armature") continue;
  const arr = new Float32Array(T * 4); let prev = null;
  seq.forEach((f, t) => { const q = (f.L.get(n) || restL.get(n)).clone().normalize(); if (prev && q.dot(prev) < 0) { q.x = -q.x; q.y = -q.y; q.z = -q.z; q.w = -q.w; } q.toArray(arr, t * 4); prev = q; });
  add(n, "rotation", arr, "VEC4"); }
const hip = new Float32Array(T * 3); seq.forEach((f, t) => f.ht.toArray(hip, t * 3)); add(B("Hip"), "translation", hip, "VEC3");
const jitterAfter = jitter(seq);
console.log("jitter (RMS 2nd derivative, m/s^2) before", JSON.stringify(jitterBefore), "after", JSON.stringify(jitterAfter));
if (O.report) fs.writeFileSync(O.report, JSON.stringify({jitterBefore, jitterAfter}));
await doc.transform(resample({tolerance: 2e-4}), prune({keepLeaves: true}));
await io.write(OUT, doc);
console.log(`${name}: ${T} frames @${fps}, scale ${scale.toFixed(3)}, ankle dy ${(tgtAnkle - scale * srcAnkle).toFixed(3)}, ${(fs.statSync(OUT).size / 1024).toFixed(0)} KB, max floor lift ${(Math.max(...seq.map(f => f.lift)) * 100).toFixed(1)} cm`);
