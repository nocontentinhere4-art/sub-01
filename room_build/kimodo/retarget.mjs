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
  if (O.lean) {                                  // the torso (Waist and everything above it) pitched forward about the rig's lateral axis
    const lq = new THREE.Quaternion().setFromAxisAngle(rgt, -O.lean * sw);
    const hq = new THREE.Quaternion().setFromAxisAngle(rgt, (O.leanHead ?? 0) * O.lean * sw);   // the neck and head turned back up by a share of it
    const under = (b, root) => { let n = B(b); while (n) { if (n.getName() === root) return true; n = parentOf.get(n); } return false; };
    for (const b of order) { if (under(b, "Waist")) W[b].premultiply(lq); if (under(b, "NeckTwist01")) W[b].premultiply(hq); }
  }
  if (O.rootKeys) {                             // timed root offsets (rig space, m): [[t, dx, dy, dz], ...], smoothstep between keys
    const K = O.rootKeys, tt = t / fps; let i = 0; while (i + 1 < K.length && K[i + 1][0] <= tt) i++;
    const a = K[i], b = K[Math.min(i + 1, K.length - 1)]; let u = b[0] > a[0] ? Math.min(1, Math.max(0, (tt - a[0]) / (b[0] - a[0]))) : 0; u = u * u * (3 - 2 * u);
    frames.rk = new THREE.Vector3(a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u);
  } else frames.rk = new THREE.Vector3();
  const hip = Pw[JI.LeftLeg].clone().add(Pw[JI.RightLeg]).multiplyScalar(0.5 * scale).add(off).add(fwd.clone().multiplyScalar(seatOff.x)).add(new THREE.Vector3(0, seatOff.y * sw, 0)).add(rgt.clone().multiplyScalar(seatOff.z)).add(frames.rk);
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
for (const h of O.hands || []) {
  // keepDetail: Kimodo's own small wrist motion (its offset from its 1 s running mean) rides on the target
  let det = null;
  if (h.keepDetail) { const wp = seq.map(f => fk(f.L, f.ht).P.get(B(`${h.hand}_Hand`)));
    det = wp.map((p, k) => { const m = new THREE.Vector3(); let n = 0; for (let j = Math.max(0, k - 15); j <= Math.min(T - 1, k + 15); j++) { m.add(wp[j]); n++; } return p.clone().sub(m.multiplyScalar(1 / n)).multiplyScalar(h.keepDetail); }); }
  for (let k = 0; k < T; k++) {
    const t = k / fps; if (t < h.from - h.ramp || t > h.to + h.ramp) continue;
    const w = t < h.from ? (t - h.from + h.ramp) / h.ramp : t > h.to ? (h.to + h.ramp - t) / h.ramp : 1;
    let g; if (h.path) { let i = 0; while (i + 1 < h.path.length && h.path[i + 1][0] <= t) i++; const a = h.path[i], b = h.path[Math.min(i + 1, h.path.length - 1)];
      const u = b[0] > a[0] ? THREE.MathUtils.clamp((t - a[0]) / (b[0] - a[0]), 0, 1) : 0; g = V(a.slice(1)).lerp(V(b.slice(1)), u); } else g = V(h.pos);
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

// hands on the bed rest on the mattress, not in it
if (O.bed && O.place) {
  const pq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), O.place[3]), pqi = pq.clone().invert(), pp = V(O.place.slice(0, 3)), bd = O.bed;
  for (let k = 0; k < T; k++) for (const sd of ["L", "R"]) {
    const st = fk(seq[k].L, seq[k].ht), w = st.P.get(B(`${sd}_Hand`)).clone().applyQuaternion(pq).add(pp);
    if (w.x > bd.x0 && w.x < bd.x1 && w.z > bd.z0 && w.z < bd.z1 && w.y < bd.top + 0.08) {
      w.y = bd.top + 0.08; twoBone(seq[k].L, seq[k].ht, `${sd}_Upperarm`, `${sd}_Forearm`, `${sd}_Hand`, w.sub(pp).applyQuaternion(pqi), 1); }
  }
}
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
await doc.transform(resample({tolerance: 2e-4}), prune({keepLeaves: true}));
await io.write(OUT, doc);
console.log(`${name}: ${T} frames @${fps}, scale ${scale.toFixed(3)}, ankle dy ${(tgtAnkle - scale * srcAnkle).toFixed(3)}, ${(fs.statSync(OUT).size / 1024).toFixed(0)} KB, max floor lift ${(Math.max(...seq.map(f => f.lift)) * 100).toFixed(1)} cm`);
