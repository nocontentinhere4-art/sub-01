// node anim_mh.mjs <src.fbx> <mh.glb> <out.glb> <start_s> <dur_s> [fps]
// Rokoko mocap (fingers included) onto the MakeHuman default skeleton. Bones in mh.glb rest world-aligned (identity).
// Per mapped bone: the source's world rotation since its rest (yaw-aligned to the target), times a rest alignment that
// turns the target's rest bone (A-pose) onto the source's rest bone (T-pose) using its direction plus a side axis.
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import * as THREE from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
const [,, FBX, GLB, OUT, START, DUR, FPSA] = process.argv; const start = +START, dur = +DUR, fps = +(FPSA || 30);
const rest = JSON.parse(fs.readFileSync(GLB.replace(/\.glb$/, "_rest.json")));
const V3 = a => new THREE.Vector3(...a);
const buf = fs.readFileSync(FBX);
const obj = new FBXLoader().parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), "");
const B = {}; obj.traverse(o => { if (o.isBone) B[o.name] = o; });
obj.updateMatrixWorld(true);
const sp = n => B[n].getWorldPosition(new THREE.Vector3()).multiplyScalar(0.01);
const sq = n => B[n].getWorldQuaternion(new THREE.Quaternion());
// [target, source, source child (direction), target direction end (bone name or 'tail')]
const MAP = [["root", "Hips", "Spine1", "spine05"], ["spine05", "Spine1", "Spine2", "spine04"], ["spine04", "Spine2", "Spine3", "spine03"],
  ["spine03", "Spine3", "Spine4", "spine02"], ["spine02", "Spine4", "Neck", "neck01"], ["neck01", "Neck", "Head", "head"], ["head", "Head", null, null]];
for (const [s, m] of [["L", "Left"], ["R", "Right"]]) {
  MAP.push([`clavicle.${s}`, `${m}Shoulder`, `${m}Arm`, `upperarm01.${s}`], [`upperarm01.${s}`, `${m}Arm`, `${m}ForeArm`, `lowerarm01.${s}`],
    [`lowerarm01.${s}`, `${m}ForeArm`, `${m}Hand`, `wrist.${s}`], [`wrist.${s}`, `${m}Hand`, `${m}Finger3Proximal`, `finger3-1.${s}`],
    [`upperleg01.${s}`, `${m}Thigh`, `${m}Shin`, `lowerleg01.${s}`], [`lowerleg01.${s}`, `${m}Shin`, `${m}Foot`, `foot.${s}`],
    [`foot.${s}`, `${m}Foot`, `${m}Toe`, "tail"],
    [`finger1-1.${s}`, `${m}Finger1Metacarpal`, `${m}Finger1Proximal`, `finger1-2.${s}`], [`finger1-2.${s}`, `${m}Finger1Proximal`, `${m}Finger1Distal`, `finger1-3.${s}`],
    [`finger1-3.${s}`, `${m}Finger1Distal`, `${m}Finger1Tip`, "tail"]);
  for (let f = 2; f <= 5; f++) MAP.push([`metacarpal${f - 1}.${s}`, `${m}Finger${f}Metacarpal`, `${m}Finger${f}Proximal`, `finger${f}-1.${s}`],
    [`finger${f}-1.${s}`, `${m}Finger${f}Proximal`, `${m}Finger${f}Medial`, `finger${f}-2.${s}`], [`finger${f}-2.${s}`, `${m}Finger${f}Medial`, `${m}Finger${f}Distal`, `finger${f}-3.${s}`],
    [`finger${f}-3.${s}`, `${m}Finger${f}Distal`, `${m}Finger${f}Tip`, "tail"]);
}
const miss = MAP.filter(r => !B[r[1]] || (r[2] && !B[r[2]])).map(r => r[1] + "/" + r[2]); if (miss.length) console.log("missing source", miss);
// yaw that turns the source's rest facing onto the target's (+z forward); side axis = left -> right hip
const sSide = sp("RightThigh").sub(sp("LeftThigh")).setY(0).normalize(), tSide = V3(rest.head["upperleg01.R"]).sub(V3(rest.head["upperleg01.L"])).setY(0).normalize();
const Y0 = new THREE.Quaternion().setFromUnitVectors(sSide, tSide);
const side = (who, s) => who === "s" ? (s === "L" ? sp("LeftFinger5Proximal").sub(sp("LeftFinger2Proximal")) : sp("RightFinger5Proximal").sub(sp("RightFinger2Proximal"))).applyQuaternion(Y0)
  : V3(rest.head[`finger5-1.${s}`]).sub(V3(rest.head[`finger2-1.${s}`]));
const basis = (d, s) => { d = d.clone().normalize(); s = s.clone().sub(d.clone().multiplyScalar(s.dot(d))).normalize();
  return new THREE.Matrix4().makeBasis(d, s, new THREE.Vector3().crossVectors(d, s)); };
const align = {}, sRestInv = {};
for (const [t, s, sc, te] of MAP) {
  sRestInv[t] = sq(s).invert();
  if (!sc) { align[t] = new THREE.Quaternion(); continue; }
  const ds = sp(sc).sub(sp(s)).applyQuaternion(Y0), dt = V3(te === "tail" ? rest.tail[t] : rest.head[te]).sub(V3(rest.head[t]));
  const sd = /\.(L|R)$/.test(t) && /clavicle|arm|wrist|finger|metacarpal/.test(t) ? t.slice(-1) : null;
  const ss = sd ? side("s", sd) : sSide.clone().applyQuaternion(Y0), ts = sd ? side("t", sd) : tSide.clone();
  align[t] = new THREE.Quaternion().setFromRotationMatrix(basis(ds, ss).multiply(basis(dt, ts).transpose()));
}
const hipH = sp("Hips").y, tHipH = rest.head.root[1], k = tHipH / hipH;
const mixer = new THREE.AnimationMixer(obj); mixer.clipAction(obj.animations[0]).play();
const T = rest.order, par = rest.parent, mapped = new Map(MAP.map(r => [r[0], r[1]]));
// heading: the clip's facing at its start (hips' side axis) turned onto the target's, plus YAW (deg) from the env
mixer.setTime(start); obj.updateMatrixWorld(true);
const sideNow = sp("RightThigh").sub(sp("LeftThigh")).applyQuaternion(Y0).setY(0).normalize();
const H = new THREE.Quaternion().setFromUnitVectors(sideNow, tSide).premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), +(process.env.YAW || 0) * Math.PI / 180));
// HANDPOSE=type|mouse|relax: the gloves' finger data is coarse (wrists flex, fingers claw), so for desk work the
// wrist is set in line with the forearm and the fingers get a relaxed curl from reference photos, with small key presses
// (type) or index clicks on the right hand (mouse). Flexion axis per bone = its rest direction x the palm normal (-y).
const HP = process.env.HANDPOSE, D2R = Math.PI / 180;
const fdir = n => V3(rest.tail[n]).sub(V3(rest.head[n])).normalize();
// the rest palm normal per side (MakeHuman's A-pose hands face the thighs, not the floor): dir x across (right),
// across x dir (left), with dir = wrist -> middle knuckle and across = index -> little knuckle
const palmN = sd => { const d = V3(rest.head[`finger3-1.${sd}`]).sub(V3(rest.head[`wrist.${sd}`])).normalize(),
  a = V3(rest.head[`finger5-1.${sd}`]).sub(V3(rest.head[`finger2-1.${sd}`])).normalize();
  return (sd === "R" ? d.clone().cross(a) : a.clone().cross(d)).normalize(); };
const PALM = { L: palmN("L"), R: palmN("R") };
const curlQ = (n, deg) => new THREE.Quaternion().setFromAxisAngle(fdir(n).cross(PALM[n.slice(-1)]).normalize(), deg * D2R);
const rnd = (i) => { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); };
function handPose(L, t) {
  for (const s of ["L", "R"]) {
    const mode = HP === "mouse" ? (s === "R" ? "mouse" : "rest") : HP === "type" ? "type" : "rest";
    L[`wrist.${s}`] = curlQ(`wrist.${s}`, mode === "mouse" ? -8 : mode === "type" ? -12 : 5);        // slight extension
    for (let f = 1; f <= 5; f++) {
      const chain = f === 1 ? [`finger1-1.${s}`, `finger1-2.${s}`, `finger1-3.${s}`] : [`metacarpal${f - 1}.${s}`, `finger${f}-1.${s}`, `finger${f}-2.${s}`, `finger${f}-3.${s}`];
      let base = f === 1 ? [8, 10, 8] : mode === "mouse" ? [0, 14 + f * 2, 22, 10] : mode === "type" ? [0, 22, 38, 16] : [0, 18, 30, 15];
      let press = 0;
      if (mode === "type" && f > 1) press = Math.max(0, Math.sin(t * (5 + rnd(f * 7 + (s === "L" ? 1 : 2)) * 4) + rnd(f + 9) * 6)) ** 8 * 14;
      if (mode === "mouse" && f === 2) press = Math.max(0, Math.sin(t * 1.3)) ** 30 * 10;               // a click now and then
      chain.forEach((n, k) => { L[n] = curlQ(n, base[k] + (k >= 1 ? press * (k === 1 ? 1 : 0.6) : 0)); });
    }
  }
}
// IK={"L":[x,y,z],"R":[x,y,z]}: pin each wrist on a world target (the keyboard's home row), elbows bent down and in,
// like the owner's reference photo; the recorded wrist/finger rotations stay (only the arm's two bones turn).
const IKT = process.env.IK ? JSON.parse(process.env.IK) : null;
const fk = (Wq, rootPos, n) => { const path = []; for (let b = n; b; b = par[b]) path.unshift(b);
  const p = V3(rootPos); for (let i = 1; i < path.length; i++) p.add(V3(rest.head[path[i]]).sub(V3(rest.head[path[i - 1]])).applyQuaternion(Wq[path[i - 1]])); return p; };
const fdir2 = n => V3(rest.tail[n]).sub(V3(rest.head[n])).normalize();
function armIK(Wq, L, rootPos) {
  for (const s of ["L", "R"]) { if (!IKT[s]) continue;
    const up = `upperarm01.${s}`, lo = `lowerarm01.${s}`, wr = `wrist.${s}`;
    // fingers: the recorded curl at FINGERK strength, thumbs swung toward the space bar
    const fk_ = +(process.env["FINGERK_" + s] || process.env.FINGERK || 1);
    if (fk_ !== 1) for (const n of rest.order) if (n.endsWith("." + s) && /finger|metacarpal/.test(n)) L[n] = new THREE.Quaternion().slerp(L[n], fk_);
    const th = `finger1-1.${s}`; L[th] = new THREE.Quaternion().setFromAxisAngle(fdir2(th).cross(new THREE.Vector3(0, -1, 0)).normalize(), +(process.env["THUMB_" + s] || 0.35)).multiply(L[th]);
    // GRIP_<side>=[mcp,pip,dip] degrees: a grip that follows the mouse's dome (palm on its back, fingers down its front),
    // over the reduced recorded motion; the index clicks now and then
    if (process.env["GRIP_" + s]) { const g = JSON.parse(process.env["GRIP_" + s]); const t = frames.length / fps;
      for (let f = 2; f <= 5; f++) { const click = f === 2 ? Math.max(0, Math.sin(t * 1.7)) ** 40 * 8 : 0;
        [`finger${f}-1.${s}`, `finger${f}-2.${s}`, `finger${f}-3.${s}`].forEach((n, k) => { L[n] = curlQ(n, g[k] + (f - 2) * 4 * (k === 0) + (k ? click : 0)).multiply(L[n]); }); }
      L[`finger1-2.${s}`] = curlQ(`finger1-2.${s}`, 15).multiply(L[`finger1-2.${s}`]);
      L[`finger1-1.${s}`] = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), (s === "R" ? -1 : 1) * +(process.env["THUMBOUT_" + s] || 0)).multiply(L[`finger1-1.${s}`]);
      // fingers together (the rest pose fans them): ring and little finger toward the index, about the palm normal
      [[3, 3], [4, 7], [5, 12]].forEach(([f, deg]) => { const n = `finger${f}-1.${s}`;
        L[n] = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), (s === "R" ? 1 : -1) * deg * D2R * +(process.env["ADDUCT_" + s] || 0)).multiply(L[n]); }); }
    const keep = { up: L[up].clone(), lo: L[lo].clone() };
    let dy = 0;
    for (let it = 0; it < 4; it++) { L[up] = keep.up.clone(); L[lo] = keep.lo.clone(); solveSide(Wq, L, rootPos, s, dy);
      // KEYTOP: no fingertip below the keycaps' top (+3 mm): lift the pin by the deepest tip's depth
      const top = +(process.env["KEYTOP_" + s] || process.env.KEYTOP || -1); if (top < 0) break;
      let low = 1e9; for (let f = 1; f <= 5; f++) low = Math.min(low, tipY(L, rootPos, `finger${f}-3.${s}`));
      if (low >= top + 0.002) break; dy += top + 0.003 - low; }
    if (MOUSE && s === "R") {
      // the palm rests on the mouse's back: lower (or lift) the pin until a point 60% from the wrist to the middle
      // knuckle touches the dome (1.6 cm of palm under the bone)
      let dyM = 0;
      for (let it = 0; it < 6; it++) { L[up] = keep.up.clone(); L[lo] = keep.lo.clone(); solveSide(Wq, L, rootPos, s, dyM);
        const w = bonePos(L, rootPos, wr), k = bonePos(L, rootPos, `finger3-1.${s}`), pp = w.lerp(k, 0.6);
        let lo_ = -0.08, hi_ = 0.08; for (let j = 0; j < 20; j++) { const m = (lo_ + hi_) / 2; if (dome(pp.clone().setY(pp.y + m), 0.016) > 0) hi_ = m; else lo_ = m; }
        if (Math.abs(lo_) < 0.001) break; dyM += lo_; }
      // each finger curls (middle and end joints) until its tip meets the dome's skin (8 mm pad); ring and little
      // finger may wrap further down the side
      const base = {}; for (const n of rest.order) if (/finger[2-5]-[23]\.R$/.test(n)) base[n] = L[n].clone();
      const SOLVE = (process.env.SOLVE_R || "2,3,4,5").split(",").map(Number);
      for (let f = 2; f <= 5; f++) { const pip = `finger${f}-2.R`, dip = `finger${f}-3.R`;
        // CURL_R_<f>=[mcp,pip,dip]: a set pose instead of the contact solve (ring and little finger tucked along the side)
        if (process.env["CURL_R_" + f]) { const c = JSON.parse(process.env["CURL_R_" + f]), mcp = `finger${f}-1.R`, m0 = L[mcp].clone();
          const setK = k => [mcp, pip, dip].forEach((n, j) => { L[n] = curlQ(n, c[j] * k).multiply(j ? base[n] : m0); });
          // DESK_Y: the finger's underside stays on the desk/pad (+1.1 cm for the finger's half thickness): ease the curl
          const floor = +(process.env.DESK_Y || -1) + 0.011, low = () => Math.min(bonePos(L, rootPos, dip, true).y, bonePos(L, rootPos, dip).y, bonePos(L, rootPos, pip).y);
          setK(1); if (floor > 0 && low() < floor) { let a = 0, b = 1; for (let j = 0; j < 14; j++) { const m = (a + b) / 2; setK(m); if (low() < floor) b = m; else a = m; } setK(a); }
          continue; }
        if (!SOLVE.includes(f)) continue;
        const at = e => { L[pip] = curlQ(pip, e).multiply(base[pip]); L[dip] = curlQ(dip, e * 0.6).multiply(base[dip]); return dome(bonePos(L, rootPos, dip, true), 0.008); };
        // scan from straight to curled for the first touch; if none, the closest pass
        let prev = -20, best = -20, bestD = 1e9, hit = null;
        for (let e = -20; e <= 70; e += 5) { const d = at(e); if (Math.abs(d) < bestD) { bestD = Math.abs(d); best = e; }
          if (d <= 0) { hit = [prev, e]; break; } prev = e; }
        let e;
        if (!hit) e = best; else if (hit[0] === hit[1]) e = hit[0];
        else { let a = hit[0], b = hit[1]; for (let j = 0; j < 16; j++) { const m = (a + b) / 2; if (at(m) > 0) a = m; else b = m; } e = a; }
        // smooth over time so the solve doesn't flick between contact points frame to frame
        const key = "_e" + f; e = IKT[key] === undefined ? e : IKT[key] + (e - IKT[key]) * +(process.env.SMOOTH || 0.25); IKT[key] = e; at(e); }
    }
  }
}
// world position of a bone's tail from the local rotations (rest is world-aligned, so offsets are rest differences)
function bonePos(L, rootPos, n, tail) { const path = []; for (let b = n; b; b = par[b]) path.unshift(b);
  const p = V3(rootPos); let W = new THREE.Quaternion();
  for (let i = 0; i < path.length; i++) { if (i) p.add(V3(rest.head[path[i]]).sub(V3(rest.head[path[i - 1]])).applyQuaternion(W)); W = W.clone().multiply(L[path[i]]); }
  return tail ? p.add(V3(rest.tail[n]).sub(V3(rest.head[n])).applyQuaternion(W)) : p; }
// MOUSE={"c":[x,y,z],"r":[rx,ry,rz]}: an ellipsoid dome; >0 outside, <0 inside (radii inflated by the skin's thickness)
const MOUSE = process.env.MOUSE ? JSON.parse(process.env.MOUSE) : null;
// r = [rx, ry, rz front, rz back]: the hump sits toward the back, the buttons slope gently to the front
// yaw (rad): the mouse turned about y like the hand on it (+z rotated toward +x)
const dome = (p, pad) => { const [cx, cy, cz] = MOUSE.c, [rx, ry, rzf, rzb] = MOUSE.r, t = -(MOUSE.yaw || 0);
  const dx = p.x - cx, dz = p.z - cz, lx = dx * Math.cos(t) + dz * Math.sin(t), lz = -dx * Math.sin(t) + dz * Math.cos(t);
  const rz = lz >= 0 ? rzf : (rzb || rzf);
  return Math.hypot(lx / (rx + pad), (Math.max(p.y, cy) - cy) / (ry + pad), lz / (rz + pad)) - 1; };
function tipY(L, rootPos, n) { const path = []; for (let b = n; b; b = par[b]) path.unshift(b);
  const p = V3(rootPos); let W = new THREE.Quaternion();
  for (let i = 0; i < path.length; i++) { if (i) p.add(V3(rest.head[path[i]]).sub(V3(rest.head[path[i - 1]])).applyQuaternion(W)); W = W.clone().multiply(L[path[i]]); }
  return p.add(V3(rest.tail[n]).sub(V3(rest.head[n])).applyQuaternion(W)).y; }
function solveSide(Wq, L, rootPos, s, dy) {
  const up = `upperarm01.${s}`, lo = `lowerarm01.${s}`, wr = `wrist.${s}`;
  const A = fk(Wq, rootPos, up), a = V3(rest.head[lo]).distanceTo(V3(rest.head[up])), b = V3(rest.head[wr]).distanceTo(V3(rest.head[lo]));
  // the recorded wrist's drift (relative to its first frame) moves the pin, so the hands wander over the keys
  const Wm = fk(Wq, rootPos, wr); if (!IKT["_w0" + s]) IKT["_w0" + s] = Wm.clone();
  const T = V3(IKT[s]).addScaledVector(Wm.clone().sub(IKT["_w0" + s]), +(process.env.DRIFT || 0.7)); T.y += dy;
  let d = T.clone().sub(A); const dl = Math.min(d.length(), a + b - 1e-3); d.normalize();
  const x = (a * a - b * b + dl * dl) / (2 * dl), h = Math.sqrt(Math.max(0, a * a - x * x));
  const pole = new THREE.Vector3(s === "L" ? 0.35 : -0.35, -1, -0.15); pole.sub(d.clone().multiplyScalar(pole.dot(d))).normalize();
  const E = A.clone().addScaledVector(d, x).addScaledVector(pole, h), C = A.clone().addScaledVector(d, dl);
  const restU = V3(rest.head[lo]).sub(V3(rest.head[up])).normalize(), restF = V3(rest.head[wr]).sub(V3(rest.head[lo])).normalize();
  const u2 = L[`upperarm02.${s}`] || new THREE.Quaternion(), l2 = L[`lowerarm02.${s}`] || new THREE.Quaternion();
  const curU = restU.clone().applyQuaternion(Wq[up]), R1 = new THREE.Quaternion().setFromUnitVectors(curU, E.clone().sub(A).normalize()).multiply(Wq[up]);
  const W2old = R1.clone().multiply(u2).multiply(L[lo]);
  const curF = restF.clone().applyQuaternion(W2old);
  const R2 = new THREE.Quaternion().setFromUnitVectors(curF, C.clone().sub(E).normalize()).multiply(W2old);
  L[up] = Wq[par[up]].clone().invert().multiply(R1);
  L[lo] = R1.clone().multiply(u2).invert().multiply(R2);
  // the hand points forward, a little inward, palm down; it keeps part of the recorded hand's turn since frame 0
  const yaw = IKT["yaw" + s] !== undefined ? IKT["yaw" + s] : (s === "L" ? -0.25 : 0.25);
  const fwd = new THREE.Vector3(yaw, IKT["pitch" + s] !== undefined ? IKT["pitch" + s] : -0.04, 1).normalize();
  const rDir = V3(rest.head[`finger3-1.${s}`]).sub(V3(rest.head[wr])), rAcr = side("t", s);
  const tAcr = new THREE.Vector3(s === "L" ? 1 : -1, -(IKT["roll" + s] || 0), 0.2);   // roll: little-finger side down
  const Hw = new THREE.Quaternion().setFromRotationMatrix(basis(fwd, tAcr).multiply(basis(rDir, rAcr).transpose()));
  const Hrec = Wq[wr].clone(); if (!IKT["_h0" + s]) IKT["_h0" + s] = Hrec.clone();
  const Hlive = Hrec.multiply(IKT["_h0" + s].clone().invert());
  const Hw2 = new THREE.Quaternion().slerp(Hlive, +(process.env["HANDK_" + s] || process.env.HANDK || 0.5)).multiply(Hw);
  L[wr] = R2.clone().multiply(l2).invert().multiply(Hw2);
}
const frames = []; let p0 = null;
for (let t = start; t < Math.min(start + dur, obj.animations[0].duration); t += 1 / fps) {
  mixer.setTime(t); obj.updateMatrixWorld(true);
  const Wq = {}, L = {};
  for (const n of T) {
    if (mapped.has(n)) Wq[n] = H.clone().multiply(Y0).multiply(sq(mapped.get(n))).multiply(sRestInv[n]).multiply(Y0.clone().invert()).multiply(align[n]);
    else Wq[n] = par[n] ? Wq[par[n]].clone() : new THREE.Quaternion();
    L[n] = par[n] ? Wq[par[n]].clone().invert().multiply(Wq[n]) : Wq[n].clone();
  }
  if (HP) handPose(L, frames.length / fps);
  if (IKT) armIK(Wq, L, [ (sp("Hips").applyQuaternion(Y0).applyQuaternion(H).x - (p0 ? p0.x : sp("Hips").applyQuaternion(Y0).applyQuaternion(H).x)) * k + rest.head.root[0],
    sp("Hips").applyQuaternion(Y0).applyQuaternion(H).y * k + +(process.env.DY || 0), (sp("Hips").applyQuaternion(Y0).applyQuaternion(H).z - (p0 ? p0.z : sp("Hips").applyQuaternion(Y0).applyQuaternion(H).z)) * k + rest.head.root[2] ]);
  const hp = sp("Hips").applyQuaternion(Y0).applyQuaternion(H); if (!p0) p0 = hp.clone();
  frames.push({ L, root: [ (hp.x - p0.x) * k + rest.head.root[0], hp.y * k + +(process.env.DY || 0), (hp.z - p0.z) * k + rest.head.root[2] ] });
}
const io = new NodeIO(), doc = await io.read(GLB), root = doc.getRoot(), b0 = root.listBuffers()[0];
const byName = new Map(root.listNodes().map(n => [n.getName(), n]));
const anim = doc.createAnimation("clip");
const tin = doc.createAccessor().setArray(new Float32Array(frames.map((_, i) => i / fps))).setType("SCALAR").setBuffer(b0);
for (const n of T) {
  if (!mapped.has(n)) continue;                                   // unmapped bones keep identity local rotations: no track
  const a = new Float32Array(frames.length * 4); let prev = null;
  frames.forEach((f, i) => { const q = f.L[n]; if (prev && q.dot(prev) < 0) q.set(-q.x, -q.y, -q.z, -q.w); q.toArray(a, i * 4); prev = q; });
  const s = doc.createAnimationSampler().setInput(tin).setOutput(doc.createAccessor().setArray(a).setType("VEC4").setBuffer(b0)).setInterpolation("LINEAR");
  anim.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(byName.get(n)).setTargetPath("rotation").setSampler(s));
}
const tr = new Float32Array(frames.length * 3); frames.forEach((f, i) => tr.set(f.root, i * 3));
const s = doc.createAnimationSampler().setInput(tin).setOutput(doc.createAccessor().setArray(tr).setType("VEC3").setBuffer(b0)).setInterpolation("LINEAR");
anim.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(byName.get("root")).setTargetPath("translation").setSampler(s));
if (process.env.ANIMONLY) { for (const m of root.listMeshes()) m.dispose(); for (const sk of root.listSkins()) sk.dispose();
  const { prune } = await import("@gltf-transform/functions"); await doc.transform(prune({ keepLeaves: true }));
  anim.setName(process.env.NAME || "clip"); }
await io.write(OUT, doc);
console.log("frames", frames.length, "mapped", MAP.length, "->", OUT, (fs.statSync(OUT).size / 1e6).toFixed(2), "MB");
