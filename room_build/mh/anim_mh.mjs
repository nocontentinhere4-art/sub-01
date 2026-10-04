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
// root: MakeHuman's root bone points forward (toward spine05), the source Hips up; aligning those turned the pelvis
// ~80 deg and lifted the hip joints 9 cm (feet floating). so the hips align by the hips -> neck line (ROOTFIX=0: the old way)
const MAP = [process.env.ROOTFIX !== "0" ? ["root", "Hips", "Neck", "neck01"] : ["root", "Hips", "Spine1", "spine05"], ["spine05", "Spine1", "Spine2", "spine04"], ["spine04", "Spine2", "Spine3", "spine03"],
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
mixer.setTime(process.env.FACE_AT ? +process.env.FACE_AT : start); obj.updateMatrixWorld(true);   // FACE_AT: face +z at that time
const sideNow = sp("RightThigh").sub(sp("LeftThigh")).applyQuaternion(Y0).setY(0).normalize();
let H0q = new THREE.Quaternion().setFromUnitVectors(sideNow, tSide);
if (process.env.WALKDIR) {   // walks: face along the clip's travel (start -> end), not the hips' side axis at the start
  const p0w = sp("Hips").applyQuaternion(Y0); mixer.setTime(Math.min(start + dur, obj.animations[0].duration)); obj.updateMatrixWorld(true);
  const p1w = sp("Hips").applyQuaternion(Y0); mixer.setTime(start); obj.updateMatrixWorld(true);
  H0q = new THREE.Quaternion().setFromUnitVectors(p1w.sub(p0w).setY(0).normalize(), new THREE.Vector3(0, 0, 1)); }
const H = H0q.clone().premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), +(process.env.YAW || 0) * Math.PI / 180));
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
    // THUMBTAP=rate: texting — the thumbs tap the screen in bursts (2-5 s of ~rate taps/s, alternating hands, then
    // 1-3 s still while reading), each tap bending the thumb's two joints ~22 deg down and back in 0.18 s
    if (process.env.THUMBTAP) { const t = frames.length / fps, rate = +process.env.THUMBTAP;
      if (!IKT._tt) { let x = 4242, tt = 0.4; const out = []; const rnd = () => (x = (x * 48271) % 2147483647) / 2147483647;
        while (tt < 600) { const burst = 2 + 3 * rnd(), end = tt + burst; let side = rnd() < 0.5 ? "L" : "R";
          while (tt < end) { out.push([tt, side]); side = rnd() < 0.75 ? (side === "L" ? "R" : "L") : side; tt += (0.6 + 0.8 * rnd()) / rate; }
          tt += 1 + 2 * rnd(); }
        IKT._tt = out; }
      let pulse = 0; for (const [t0, sd] of IKT._tt) { if (t0 > t) break; if (sd !== s) continue; const u = t - t0; const TD = +(process.env.TAP_DUR || 0.18); if (u < TD) pulse = Math.max(pulse, Math.sin(Math.PI * u / TD)); }
      for (const n of [`finger1-2.${s}`, `finger1-3.${s}`]) L[n] = curlQ(n, 22 * pulse).multiply(L[n]); }
    const keep = { up: L[up].clone(), lo: L[lo].clone() };
    let dy = 0;
    for (let it = 0; it < 4; it++) { L[up] = keep.up.clone(); L[lo] = keep.lo.clone(); solveSide(Wq, L, rootPos, s, dy);
      // KEYTOP: no fingertip below the keycaps' top (+3 mm): lift the pin by the deepest tip's depth
      const top = +(process.env["KEYTOP_" + s] || process.env.KEYTOP || -1); if (top < 0) break;
      // the bones run through the finger's middle: SKIN (default 9 mm) of pad under every joint and tip
      const sk = +(process.env.SKIN || 0.009); let low = 1e9;
      for (let f = 1; f <= 5; f++) for (const j of [2, 3]) { const n = `finger${f}-${j}.${s}`; low = Math.min(low, bonePos(L, rootPos, n).y, bonePos(L, rootPos, n, true).y); }
      low -= sk; if (low >= top + 0.002) break; dy += top + 0.003 - low; }
    // TAPS: real key presses on top of the resting typing pose: each finger fires short pulses (down 50 ms, hold 30 ms,
    // up 70 ms) at its own random rate; a press bends the knuckle and middle joint until the tip is 4 mm below the
    // keycap top (the key's travel), never deeper
    if (process.env.TAPS && process.env.KEYTOP) { const top = +(process.env["KEYTOP_" + s] || process.env.KEYTOP), t = frames.length / fps;
      const rate = { 2: 2.0, 3: 1.6, 4: 1.0, 5: 0.7 };
      for (let f = 2; f <= 5; f++) { const pulse = tapPulse(s + f, t); if (pulse <= 0) continue;
        const mcp = `finger${f}-1.${s}`, pip = `finger${f}-2.${s}`, tip = `finger${f}-3.${s}`, m0 = L[mcp].clone(), p0 = L[pip].clone();
        const at = a => { L[mcp] = curlQ(mcp, a * 0.6).multiply(m0); L[pip] = curlQ(pip, a).multiply(p0); return bonePos(L, rootPos, tip, true).y; };
        const goal = top + +(process.env.SKIN || 0.009) - 0.004;   // the pad's skin goes 4 mm down: the key's travel
        let lo_ = 0, hi_ = 40; if (at(hi_) > goal) { at(hi_ * pulse); continue; }
        for (let j = 0; j < 14; j++) { const m = (lo_ + hi_) / 2; if (at(m) > goal) lo_ = m; else hi_ = m; }
        at(lo_ * pulse); } }
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
// tap pulses: deterministic random tap times per key (seeded by the finger), shape 0 -> 1 -> 0 over 150 ms
const TAPS_CACHE = {};
// one hand's key events: about TAP_RATE presses per second (default 1.5), each on ONE finger picked by weight
// (index 0.4, middle 0.3, ring 0.2, little 0.1); a press goes down in 90 ms, holds 50 ms and comes back in 140 ms
function tapPulse(key, t) {
  const hand = key[0], f = +key.slice(1);
  if (!TAPS_CACHE[hand]) { let x = (hand === "L" ? 9173 : 31337), tt = 0.3; const out = [];
    const rnd = () => (x = (x * 48271) % 2147483647) / 2147483647, rate = +(process.env.TAP_RATE || 1.5);
    while (tt < 600) { tt += Math.max(+(process.env.TAP_GAP || 0.3), -Math.log(1 - rnd()) / rate); const r = rnd(); out.push([tt, r < 0.4 ? 2 : r < 0.7 ? 3 : r < 0.9 ? 4 : 5]); }
    TAPS_CACHE[hand] = out; }
  for (const [t0, ff] of TAPS_CACHE[hand]) { const u = t - t0; if (u < 0) break; if (ff !== f) continue;
    const [dn, hd, upt] = (process.env.TAP_MS || "90,50,140").split(",").map(x => +x / 1000);
    if (u < dn) return 0.5 - 0.5 * Math.cos(Math.PI * u / dn); if (u < dn + hd) return 1; if (u < dn + hd + upt) return 0.5 + 0.5 * Math.cos(Math.PI * (u - dn - hd) / upt); }
  return 0;
}
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
  // path<s>=[[t, dx, dy, dz], ...]: keyed offsets of the pin (smoothstep between keys), e.g. a page turn
  if (IKT["path" + s]) { const P = IKT["path" + s], tt = frames.length / fps; let o = [0, 0, 0];
    if (tt <= P[0][0]) o = P[0].slice(1); else if (tt >= P[P.length - 1][0]) o = P[P.length - 1].slice(1);
    else for (let i = 0; i < P.length - 1; i++) if (tt >= P[i][0] && tt <= P[i + 1][0]) { const u = (tt - P[i][0]) / (P[i + 1][0] - P[i][0]), w = u * u * (3 - 2 * u);
      o = [1, 2, 3].map(k => P[i][k] + (P[i + 1][k] - P[i][k]) * w); break; }
    T.x += o[0]; T.y += o[1]; T.z += o[2]; }
  // WANDER=a (m): the hands slowly travel over the keys like a real typist's (two slow sines per axis, per hand), so
  // the forearms and elbows move instead of staying locked
  if (process.env.WANDER) { const a = +process.env.WANDER, tt = frames.length / fps, ph = s === "L" ? 0 : 1.7;
    T.x += a * (0.7 * Math.sin(2 * Math.PI * 0.11 * tt + ph) + 0.3 * Math.sin(2 * Math.PI * 0.37 * tt + 2 * ph));
    T.z += a * 0.5 * (0.6 * Math.sin(2 * Math.PI * 0.07 * tt + 0.5 + ph) + 0.4 * Math.sin(2 * Math.PI * 0.23 * tt + ph));
    T.y += a * 0.15 * Math.sin(2 * Math.PI * 0.19 * tt + ph); }
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
  const fwd = IKT["fwd" + s] ? V3(IKT["fwd" + s]).normalize() : new THREE.Vector3(yaw, IKT["pitch" + s] !== undefined ? IKT["pitch" + s] : -0.04, 1).normalize();
  const rDir = V3(rest.head[`finger3-1.${s}`]).sub(V3(rest.head[wr])), rAcr = side("t", s);
  const tAcr = IKT["acr" + s] ? V3(IKT["acr" + s]) : new THREE.Vector3(s === "L" ? 1 : -1, -(IKT["roll" + s] || 0), 0.2);   // roll: little-finger side down; fwd<s>/acr<s>: explicit finger and index->little directions
  const Hw = new THREE.Quaternion().setFromRotationMatrix(basis(fwd, tAcr).multiply(basis(rDir, rAcr).transpose()));
  const Hrec = Wq[wr].clone(); if (!IKT["_h0" + s]) IKT["_h0" + s] = Hrec.clone();
  const Hlive = Hrec.multiply(IKT["_h0" + s].clone().invert());
  const Hw2 = new THREE.Quaternion().slerp(Hlive, +(process.env["HANDK_" + s] || process.env.HANDK || 0.5)).multiply(Hw);
  L[wr] = R2.clone().multiply(l2).invert().multiply(Hw2);
}
// HANDSOUT=r: hands resting on the thighs stay ON them. Each thigh is a capsule (hip -> knee joint, radius r); if the
// wrist, the palm's middle or the middle knuckle is inside (+1.2 cm of skin), the arm (two bones) moves the wrist out
// along the capsule's normal, and the hand keeps its world rotation.
function wlq(L, n) { const path = []; for (let b = n; b; b = par[b]) path.unshift(b); let W = new THREE.Quaternion(); for (const b of path) W = W.clone().multiply(L[b]); return W; }
function handsOut(L, rootPos, r) { for (const s of ["L", "R"]) handsOutSide(L, rootPos, r, s); }
function handsOutSide(L, rootPos, r, s1) {
  const caps = ["L", "R"].map(sd => [bonePos(L, rootPos, `upperleg01.${sd}`), bonePos(L, rootPos, `lowerleg01.${sd}`)]);
  const seg = new THREE.Line3(), q = new THREE.Vector3();
  for (const s of [s1]) {
    const up = `upperarm01.${s}`, lo = `lowerarm01.${s}`, wr = `wrist.${s}`;
    for (let it = 0; it < 12; it++) {
      const W0 = bonePos(L, rootPos, wr), K0 = bonePos(L, rootPos, `finger3-1.${s}`), E0 = bonePos(L, rootPos, lo);
      const pts = [W0, W0.clone().lerp(K0, 0.5), K0, bonePos(L, rootPos, `finger3-3.${s}`, true), bonePos(L, rootPos, `finger2-3.${s}`, true),
        bonePos(L, rootPos, `finger5-3.${s}`, true), E0.clone().lerp(W0, 0.5), E0.clone().lerp(W0, 0.8)];
      let corr = new THREE.Vector3();
      // the thigh tapers: radius r*1.3 at the hip joint down to r*0.8 at the knee
      for (const [a, b] of caps) { seg.set(a, b); for (const p of pts) { const tt = seg.closestPointToPointParameter(p, true); seg.at(tt, q);
        const d = p.distanceTo(q), need = r * (1.3 - 0.5 * tt) + 0.012;
        if (d < need) { const n = p.clone().sub(q); if (n.lengthSq() < 1e-8) n.set(0, 1, 0); n.normalize(); const c = n.multiplyScalar(need - d); if (c.length() > corr.length()) corr = c; } } }
      if (corr.length() < 0.002) break;
      const Hw = wlq(L, wr), A = bonePos(L, rootPos, up), T = W0.clone().add(corr);
      const a = A.distanceTo(bonePos(L, rootPos, lo)), b = bonePos(L, rootPos, lo).distanceTo(W0);
      let d = T.clone().sub(A); const dl = Math.min(d.length(), a + b - 1e-3); d.normalize();
      const x = (a * a - b * b + dl * dl) / (2 * dl), h = Math.sqrt(Math.max(0, a * a - x * x));
      const Kc = bonePos(L, rootPos, lo), pole = Kc.clone().sub(A).sub(d.clone().multiplyScalar(Kc.clone().sub(A).dot(d))).normalize();
      const E = A.clone().addScaledVector(d, x).addScaledVector(pole, h), Cn = A.clone().addScaledVector(d, dl);
      const R1 = new THREE.Quaternion().setFromUnitVectors(Kc.clone().sub(A).normalize(), E.clone().sub(A).normalize()).multiply(wlq(L, up));
      L[up] = wlq(L, par[up]).invert().multiply(R1);
      const Kn = bonePos(L, rootPos, lo), Cc = bonePos(L, rootPos, wr);
      const R2 = new THREE.Quaternion().setFromUnitVectors(Cc.clone().sub(Kn).normalize(), Cn.clone().sub(Kn).normalize()).multiply(wlq(L, lo));
      L[lo] = wlq(L, par[lo]).invert().multiply(R2);
      L[wr] = wlq(L, par[wr]).invert().multiply(Hw);
    }
  }
}
// move a wrist to T with the two arm bones (elbow kept on its side), the hand keeping its world rotation
function moveWrist(L, rootPos, s, T) {
  const up = `upperarm01.${s}`, lo = `lowerarm01.${s}`, wr = `wrist.${s}`;
  const Hw = wlq(L, wr), A = bonePos(L, rootPos, up), Kc = bonePos(L, rootPos, lo), W0 = bonePos(L, rootPos, wr);
  const a = A.distanceTo(Kc), b = Kc.distanceTo(W0);
  let d = T.clone().sub(A); const dl = Math.min(d.length(), a + b - 1e-3); d.normalize();
  const x = (a * a - b * b + dl * dl) / (2 * dl), h = Math.sqrt(Math.max(0, a * a - x * x));
  const pole = Kc.clone().sub(A).sub(d.clone().multiplyScalar(Kc.clone().sub(A).dot(d))).normalize();
  const E = A.clone().addScaledVector(d, x).addScaledVector(pole, h), Cn = A.clone().addScaledVector(d, dl);
  const R1 = new THREE.Quaternion().setFromUnitVectors(Kc.clone().sub(A).normalize(), E.clone().sub(A).normalize()).multiply(wlq(L, up));
  L[up] = wlq(L, par[up]).invert().multiply(R1);
  const Kn = bonePos(L, rootPos, lo), Cc = bonePos(L, rootPos, wr);
  const R2 = new THREE.Quaternion().setFromUnitVectors(Cc.clone().sub(Kn).normalize(), Cn.clone().sub(Kn).normalize()).multiply(wlq(L, lo));
  L[lo] = wlq(L, par[lo]).invert().multiply(R2);
  L[wr] = wlq(L, par[wr]).invert().multiply(Hw);
}
function legDown(Wq, L, rootPos, sd, w) {
  const up = `upperleg01.${sd}`, lo = `lowerleg01.${sd}`, ft = `foot.${sd}`;
  const Wl = n => { const path = []; for (let b = n; b; b = par[b]) path.unshift(b); let W = new THREE.Quaternion(); for (const b of path) W = W.clone().multiply(L[b]); return W; };
  const A = bonePos(L, rootPos, up), K = bonePos(L, rootPos, lo), C = bonePos(L, rootPos, ft);
  const a = A.distanceTo(K), b = K.distanceTo(C);
  const T = C.clone(); T.y = C.y + (Math.max(0.09, C.y - 0.0) === C.y ? 0 : 0) ; T.y = C.y * (1 - w) + 0.09 * w;
  T.x = C.x; T.z = C.z + (K.z - C.z) * 0;               // straight down from where the foot was
  let d = T.clone().sub(A); const dl = Math.min(d.length(), a + b - 1e-3); d.normalize();
  const x = (a * a - b * b + dl * dl) / (2 * dl), h = Math.sqrt(Math.max(0, a * a - x * x));
  const pole = K.clone().sub(A).sub(d.clone().multiplyScalar(K.clone().sub(A).dot(d))).normalize();
  const E = A.clone().addScaledVector(d, x).addScaledVector(pole, h), Cn = A.clone().addScaledVector(d, dl);
  const Wup = Wl(up), Wlo = Wl(lo);
  const R1 = new THREE.Quaternion().setFromUnitVectors(K.clone().sub(A).normalize(), E.clone().sub(A).normalize()).multiply(Wup);
  const parUp = Wl(par[up]); L[up] = parUp.clone().invert().multiply(R1);
  const Wlo1 = Wl(lo), Kn = bonePos(L, rootPos, lo), Cc = bonePos(L, rootPos, ft);
  const R2 = new THREE.Quaternion().setFromUnitVectors(Cc.clone().sub(Kn).normalize(), Cn.clone().sub(Kn).normalize()).multiply(Wlo1);
  L[lo] = Wl(par[lo]).clone().invert().multiply(R2);
}
const frames = []; let p0 = null;
// WARP=[[outT, srcT], ...] (seconds from start): sample the recording on a piecewise-linear time map, to slow a
// moment down (a 1 s pour held for 3 s) without touching the rest
const srcTimes = []; if (process.env.WARP) { const P = JSON.parse(process.env.WARP), end = P[P.length - 1][0];
  for (let u = 0; u < end; u += 1 / fps) { let sT = P[P.length - 1][1]; for (let i = 0; i < P.length - 1; i++) if (u >= P[i][0] && u <= P[i + 1][0]) { sT = P[i][1] + (u - P[i][0]) / (P[i + 1][0] - P[i][0]) * (P[i + 1][1] - P[i][1]); break; }
    srcTimes.push(start + sT); } }
else for (let t = start; t < Math.min(start + dur, obj.animations[0].duration); t += 1 / fps) srcTimes.push(t);
for (const t of srcTimes) {
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
  // LIFT=[[srcHipsY, dy], ...]: piecewise-linear lift by the source hips' height, so a clip recorded on a low bed puts
  // him on a taller one (standing keeps 0, sitting on the edge and lying get raised)
  let lift = 0; if (process.env.LIFT) { const P = JSON.parse(process.env.LIFT), h = sp("Hips").y;
    if (h >= P[0][0]) lift = P[0][1]; else if (h <= P[P.length - 1][0]) lift = P[P.length - 1][1];
    else for (let i = 0; i < P.length - 1; i++) if (h <= P[i][0] && h >= P[i + 1][0]) { const u = (P[i][0] - h) / (P[i][0] - P[i + 1][0]); lift = P[i][1] + u * (P[i + 1][1] - P[i][1]); } }
  // LIFTT=[[t, dy], ...]: extra lift by clip time (piecewise linear), for contacts the hips' height alone can't tell apart
  if (process.env.LIFTT) { const P = JSON.parse(process.env.LIFTT), tt = frames.length / fps;
    if (tt <= P[0][0]) lift += P[0][1]; else if (tt >= P[P.length - 1][0]) lift += P[P.length - 1][1];
    else for (let i = 0; i < P.length - 1; i++) if (tt >= P[i][0] && tt <= P[i + 1][0]) { lift += P[i][1] + (tt - P[i][0]) / (P[i + 1][0] - P[i][0]) * (P[i + 1][1] - P[i][1]); break; } }
  // FEETDOWN=[lyingH, seatedH]: when the lift raises him while seated (source hips between those heights), the legs
  // reach down so the feet hang toward the floor instead of riding up with the hips (two-bone IK, knee kept forward)
  if (process.env.FEETDOWN && lift > 0 && (!process.env.FEETDOWN_T || (t => t >= JSON.parse(process.env.FEETDOWN_T)[0] && t <= JSON.parse(process.env.FEETDOWN_T)[1])(frames.length / fps))) {   // FEETDOWN_T=[t0,t1]: only then
    const [hl, hs] = JSON.parse(process.env.FEETDOWN), h = sp("Hips").y;
    const w = Math.max(0, Math.min(1, (h - hl) / (hs - hl))) * Math.max(0, Math.min(1, (0.85 - h) / 0.1));
    if (w > 0) { const rp = [ (hp.x - (p0 ? p0.x : hp.x)) * k + rest.head.root[0], hp.y * k + lift, (hp.z - (p0 ? p0.z : hp.z)) * k + rest.head.root[2] ];
      for (const sd of ["L", "R"]) legDown(Wq, L, rp, sd, w); } }
  frames.push({ L, root: [ (hp.x - p0.x) * k + rest.head.root[0], hp.y * k + +(process.env.DY || 0) + lift, (hp.z - p0.z) * k + rest.head.root[2] ] });
}
// HANDSOUT post pass: solve each frame's wrist correction on a copy, then spread it in time (a max over +-5 frames so
// the hand moves out BEFORE contact, then a Gaussian, sigma 4 frames) and apply the smoothed corrections, so the hands
// glide instead of jumping when the collision switches on and off
if (process.env.HANDSOUT) { const r = +process.env.HANDSOUT;
  for (const sd of ["L", "R"]) {
    const corr = frames.map(f => { const Lc = Object.fromEntries(Object.entries(f.L).map(([n, q]) => [n, q.clone()]));
      const w0 = bonePos(Lc, f.root, `wrist.${sd}`); handsOutSide(Lc, f.root, r, sd); return bonePos(Lc, f.root, `wrist.${sd}`).sub(w0); });
    const n = corr.length, dil = corr.map((_, i) => { let best = corr[i]; for (let j = Math.max(0, i - 5); j <= Math.min(n - 1, i + 5); j++) if (corr[j].length() > best.length()) best = corr[j]; return best; });
    const sm = dil.map((_, i) => { const acc = new THREE.Vector3(); let ws = 0; for (let j = Math.max(0, i - 12); j <= Math.min(n - 1, i + 12); j++) { const w = Math.exp(-((j - i) ** 2) / 32); acc.addScaledVector(dil[j], w); ws += w; } return acc.multiplyScalar(1 / ws); });
    frames.forEach((f, i) => { if (sm[i].length() > 1e-4) moveWrist(f.L, f.root, sd, bonePos(f.L, f.root, `wrist.${sd}`).add(sm[i])); });
  } }
// MATTRESS=[x0,x1,z0,z1,top]: a hand pressing on the bed stays on the mattress (palm skin 1.2 cm over its top); the
// wrist moves up by the deepest point's depth, spread in time like HANDSOUT so it glides
if (process.env.MATTRESS) { const [x0, x1, z0, z1, top] = JSON.parse(process.env.MATTRESS);
  for (const sd of ["L", "R"]) {
    const pts = ["wrist", "finger3-1", "finger2-3", "finger3-3", "finger4-3", "finger5-3", "finger1-3"].map(b => `${b}.${sd}`);
    const corr = frames.map(f => { let dy = 0; for (const b of pts) for (const tl of [false, true]) { const q = bonePos(f.L, f.root, b, tl);
      if (q.x > x0 && q.x < x1 && q.z > z0 && q.z < z1) dy = Math.max(dy, top + 0.012 - q.y); } return new THREE.Vector3(0, dy, 0); });
    const n = corr.length, dil = corr.map((_, i) => { let best = corr[i]; for (let j = Math.max(0, i - 5); j <= Math.min(n - 1, i + 5); j++) if (corr[j].y > best.y) best = corr[j]; return best; });
    const sm = dil.map((_, i) => { let acc = 0, ws = 0; for (let j = Math.max(0, i - 12); j <= Math.min(n - 1, i + 12); j++) { const w = Math.exp(-((j - i) ** 2) / 32); acc += dil[j].y * w; ws += w; } return acc / ws; });
    frames.forEach((f, i) => { if (sm[i] > 1e-4) moveWrist(f.L, f.root, sd, bonePos(f.L, f.root, `wrist.${sd}`).add(new THREE.Vector3(0, sm[i], 0))); });
  } }
// MOUTH=side (R, L or RL): when the hand comes up to the face, the point between thumb and index tips is pulled onto
// the mouth (G2: lips 4 cm below and 11.8 cm in front of the head joint; MOUTH_OFF overrides), so food and cups reach
// the lips on our body's proportions instead of the recorded actor's; the pull fades in over 25 cm and is smoothed
// MOUTH_PT={"L":[x,y,z]}: pull this point (in the wrist's frame, e.g. a held glass's rim) to the mouth instead
if (process.env.MOUTH) { const MPT = JSON.parse(process.env.MOUTH_PT || "{}"), off = V3(JSON.parse(process.env.MOUTH_OFF || "[0,-0.04,0.118]")), R = +(process.env.MOUTH_R || 0.25), gap = +(process.env.MOUTH_GAP || 0.02);
  for (const sd of process.env.MOUTH.split("")) {
    const corr = frames.map(f => { const hq = wlq(f.L, "head"), m = bonePos(f.L, f.root, "head").add(off.clone().applyQuaternion(hq));
      const fp = MPT[sd] ? bonePos(f.L, f.root, `wrist.${sd}`).add(V3(MPT[sd]).applyQuaternion(wlq(f.L, `wrist.${sd}`)))
        : bonePos(f.L, f.root, `finger1-3.${sd}`, true).add(bonePos(f.L, f.root, `finger2-3.${sd}`, true)).multiplyScalar(0.5);
      const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(hq), tgt = m.clone().addScaledVector(fwd, gap), d = fp.distanceTo(tgt);
      const w = d >= R ? 0 : d <= R * 0.5 ? 1 : (u => u * u * (3 - 2 * u))((R - d) / (R * 0.5)); return tgt.sub(fp).multiplyScalar(w); });
    const n = corr.length, sm = corr.map((_, i) => { const acc = new THREE.Vector3(); let ws = 0; for (let j = Math.max(0, i - 8); j <= Math.min(n - 1, i + 8); j++) { const w = Math.exp(-((j - i) ** 2) / 18); acc.addScaledVector(corr[j], w); ws += w; } return acc.multiplyScalar(1 / ws); });
    frames.forEach((f, i) => { if (sm[i].length() > 1e-4) moveWrist(f.L, f.root, sd, bonePos(f.L, f.root, `wrist.${sd}`).add(sm[i])); });
  } }
// MOVEW={"R":[[t, dx, dy, dz], ...]}: keyed world offsets of a wrist (two-bone arm IK, the hand keeps its rotation),
// e.g. bringing the bottle's mouth over the glass
if (process.env.MOVEW) { const MW = JSON.parse(process.env.MOVEW);
  for (const sd of Object.keys(MW)) { const P = MW[sd];
    frames.forEach((f, i) => { const tt = i / fps; let o = P[P.length - 1].slice(1);
      if (tt <= P[0][0]) o = P[0].slice(1); else for (let j = 0; j < P.length - 1; j++) if (tt >= P[j][0] && tt <= P[j + 1][0]) { const u = (tt - P[j][0]) / (P[j + 1][0] - P[j][0]), w = u * u * (3 - 2 * u); o = [1, 2, 3].map(k => P[j][k] + (P[j + 1][k] - P[j][k]) * w); break; }
      if (Math.hypot(...o) < 1e-4) return; moveWrist(f.L, f.root, sd, bonePos(f.L, f.root, `wrist.${sd}`).add(V3(o))); }); } }
// HROT={"R":[[t, deg], ...]}: extra roll of the hand about the forearm (keyed, smoothstep), e.g. tilting a bottle to pour
if (process.env.HROT) { const HR = JSON.parse(process.env.HROT);
  for (const sd of Object.keys(HR)) { const P = HR[sd];
    frames.forEach((f, i) => { const tt = i / fps; let a = P[P.length - 1][1];
      if (tt <= P[0][0]) a = P[0][1]; else for (let j = 0; j < P.length - 1; j++) if (tt >= P[j][0] && tt <= P[j + 1][0]) { const u = (tt - P[j][0]) / (P[j + 1][0] - P[j][0]); a = P[j][1] + (P[j + 1][1] - P[j][1]) * u * u * (3 - 2 * u); break; }
      if (Math.abs(a) < 1e-3) return; const wr = `wrist.${sd}`, ax = bonePos(f.L, f.root, wr).sub(bonePos(f.L, f.root, `lowerarm01.${sd}`)).normalize();
      const Wn = new THREE.Quaternion().setFromAxisAngle(ax, a * D2R).multiply(wlq(f.L, wr)); f.L[wr] = wlq(f.L, par[wr]).invert().multiply(Wn); }); } }
// WDEV={"R":[[t, deg], ...]}: bend the hand within its own plane at the wrist (about the palm normal; radial/ulnar
// deviation, keyed, smoothstep), e.g. a carried bottle's neck tipped up
if (process.env.WDEV) { const WD = JSON.parse(process.env.WDEV);
  for (const sd of Object.keys(WD)) { const P = WD[sd];
    frames.forEach((f, i) => { const tt = i / fps; let a = P[P.length - 1][1];
      if (tt <= P[0][0]) a = P[0][1]; else for (let j = 0; j < P.length - 1; j++) if (tt >= P[j][0] && tt <= P[j + 1][0]) { const u = (tt - P[j][0]) / (P[j + 1][0] - P[j][0]); a = P[j][1] + (P[j + 1][1] - P[j][1]) * u * u * (3 - 2 * u); break; }
      if (Math.abs(a) < 1e-3) return; const wr = `wrist.${sd}`, Wn = wlq(f.L, wr), ax = PALM[sd].clone().applyQuaternion(Wn).normalize();
      f.L[wr] = wlq(f.L, par[wr]).invert().multiply(new THREE.Quaternion().setFromAxisAngle(ax, a * D2R).multiply(Wn)); }); } }
// ELBOWSW={"L":[[t, deg], ...]}: swing the elbow about the shoulder -> wrist line (keyed, smoothstep), the wrist staying
// where it is with its world rotation, e.g. lifting an elbow that the recorded actor tucked into a slimmer chest
if (process.env.ELBOWSW) { const ES = JSON.parse(process.env.ELBOWSW);
  for (const sd of Object.keys(ES)) { const P = ES[sd];
    frames.forEach((f, i) => { const tt = i / fps; let a = P[P.length - 1][1];
      if (tt <= P[0][0]) a = P[0][1]; else for (let j = 0; j < P.length - 1; j++) if (tt >= P[j][0] && tt <= P[j + 1][0]) { const u = (tt - P[j][0]) / (P[j + 1][0] - P[j][0]); a = P[j][1] + (P[j + 1][1] - P[j][1]) * u * u * (3 - 2 * u); break; }
      if (Math.abs(a) < 1e-3) return; const up = `upperarm01.${sd}`, wr = `wrist.${sd}`, Hw = wlq(f.L, wr);
      const ax = bonePos(f.L, f.root, wr).sub(bonePos(f.L, f.root, up)).normalize();
      f.L[up] = wlq(f.L, par[up]).invert().multiply(new THREE.Quaternion().setFromAxisAngle(ax, a * D2R).multiply(wlq(f.L, up)));
      f.L[wr] = wlq(f.L, par[wr]).invert().multiply(Hw); }); } }
// GRASP={"L":obj,"R":obj}: the hand closes on a real object. obj = {shape: cyl (axis = its y) | box, size, frame:
// "world" (the clip's frame) or a bone (e.g. "wrist.L": the object rides on the hand), pos, rot (deg, XYZ)} or, for a
// cylinder in a power grip, auto: "palm" (centred on the palm, touching it, axis along index -> little; shift slides it
// along that axis, e.g. so a glass's rim stands above the thumb). Each finger
// (and the thumb) curls from open until its pads touch the surface (signed distance, 9-10 mm pad), smoothed in time.
// The object's final local pose is printed (GRASP_OUT) so the page can attach the same prop to the same bone.
// together: the rest pose fans the fingers apart; swing each proximal phalanx (about the palm normal) by this fraction of
// its angle to the middle finger so they lie side by side as in a real grip
const togetherQ = (sd, fi, k) => { const N = PALM[sd], pr = v => v.clone().sub(N.clone().multiplyScalar(v.dot(N))).normalize();
  const a = pr(fdir(`finger${fi}-1.${sd}`)), m = pr(fdir(`finger3-1.${sd}`)), ang = Math.atan2(a.clone().cross(m).dot(N), a.dot(m));
  return new THREE.Quaternion().setFromAxisAngle(N, ang * k); };
if (process.env.GRASP) { const G = JSON.parse(process.env.GRASP), out = {};
  const sdfOf = (o, q) => { if (o.shape === "cyl") { const r = o.size[0], h = o.size[1] / 2, dr = Math.hypot(q.x, q.z) - r, dy = Math.abs(q.y) - h;
      return Math.min(Math.max(dr, dy), 0) + Math.hypot(Math.max(dr, 0), Math.max(dy, 0)); }
    const d = [Math.abs(q.x) - o.size[0] / 2, Math.abs(q.y) - o.size[1] / 2, Math.abs(q.z) - o.size[2] / 2];
    return Math.min(Math.max(...d), 0) + Math.hypot(...d.map(v => Math.max(v, 0))); };
  for (const sd of Object.keys(G)) { const o = G[sd];
    let lpos = V3(o.pos || [0, 0, 0]), lq = new THREE.Quaternion().setFromEuler(new THREE.Euler(...(o.rot || [0, 0, 0]).map(d => d * D2R)));
    if (o.auto === "palm") { const w = V3(rest.head[`wrist.${sd}`]), kn = V3(rest.head[`finger3-1.${sd}`]);
      const across = V3(rest.head[`finger5-1.${sd}`]).sub(V3(rest.head[`finger2-1.${sd}`])).normalize();
      lpos = kn.clone().sub(w).multiplyScalar(o.along ?? 0.55).addScaledVector(PALM[sd], o.size[0] + (o.gap ?? 0.016));
      lq = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), across); lpos.addScaledVector(across, o.shift ?? 0); }
    out[sd] = { frame: o.frame || "world", pos: lpos.toArray().map(x => +x.toFixed(4)), rot: new THREE.Euler().setFromQuaternion(lq).toArray().slice(0, 3).map(r => +(r / D2R).toFixed(2)), shape: o.shape, size: o.size };
    const prev = {};
    for (const f of frames) {
      const M = new THREE.Matrix4().compose(lpos, lq, new THREE.Vector3(1, 1, 1));
      if (o.frame && o.frame !== "world") M.premultiply(new THREE.Matrix4().compose(bonePos(f.L, f.root, o.frame), wlq(f.L, o.frame), new THREE.Vector3(1, 1, 1)));
      // avoid="L": the other hand's finger bones (already solved this frame) are obstacles too (capsules, r 8 mm), so
      // the fingers of the two hands rest on each other instead of passing through
      const caps = [];
      if (o.avoid) for (let ff = 1; ff <= 5; ff++) for (const nn of (ff === 1 ? [2, 3] : [1, 2, 3])) { const bn = `finger${ff}-${nn}.${o.avoid}`;
        caps.push([bonePos(f.L, f.root, bn), bonePos(f.L, f.root, bn, true)]); }
      const capD = p => { let d = 1e9; for (const [a, b] of caps) { const ab = b.clone().sub(a), t = Math.max(0, Math.min(1, p.clone().sub(a).dot(ab) / ab.lengthSq()));
        d = Math.min(d, p.distanceTo(a.clone().addScaledVector(ab, t)) - 0.008); } return d; };
      const Minv = M.clone().invert(), sdf = p => Math.min(sdfOf(o, p.clone().applyMatrix4(Minv)), caps.length ? capD(p) : 1e9);
      // fromRest: the palm's own bones (metacarpals) go back to rest too, or the recorded spread keeps the knuckles apart
      if (o.fromRest) for (let m = 1; m <= 4; m++) f.L[`metacarpal${m}.${sd}`] = new THREE.Quaternion();
      if (o.oppose !== undefined) { const t1 = `finger1-1.${sd}`; f.L[t1] = new THREE.Quaternion().setFromAxisAngle(PALM[sd], (sd === "L" ? -1 : 1) * (o.swing ?? 0) * D2R).multiply(new THREE.Quaternion().setFromAxisAngle(fdir(`finger2-1.${sd}`), (sd === "L" ? -1 : 1) * o.oppose * D2R)).multiply(o.fromRest ? new THREE.Quaternion() : f.L[t1]); }
      for (let fi = 1; fi <= 5; fi++) { if (o.fingers && !o.fingers.includes(fi)) continue;
        const names = fi === 1 ? [`finger1-2.${sd}`, `finger1-3.${sd}`] : [`finger${fi}-1.${sd}`, `finger${fi}-2.${sd}`, `finger${fi}-3.${sd}`];
        const ratio = fi === 1 ? [1, 0.8] : [0.75, 1, 0.7], base = names.map(n => o.fromRest ? new THREE.Quaternion() : f.L[n].clone()),
          _tg = fi > 1 && o.together ? (base[0] = togetherQ(sd, fi, o.together).multiply(base[0])) : null, pad = fi === 1 ? 0.010 + (o.thumbHover ?? 0) : 0.009;
        const set = e => names.forEach((n, j) => { f.L[n] = _tg && j === 0 ? base[0].clone().multiply(curlQ(n, e * ratio[j])) : curlQ(n, e * ratio[j]).multiply(base[j]); });
        const dist = e => { set(e); const ps = (o.tipOnly && fi > 1 ? names.slice(-1) : names.slice(1)).map(n => bonePos(f.L, f.root, n)); ps.push(bonePos(f.L, f.root, names[names.length - 1], true));
          // keepSide=+1/-1: this hand's fingers stay on their own side of the object's middle (local x), so the two
          // hands' fingers meet behind a phone instead of passing through each other
          const side = o.keepSide ? Math.min(...ps.map(p => o.keepSide * p.clone().applyMatrix4(Minv).x)) - pad : 1e9;
          return Math.min(Math.min(...ps.map(sdf)) - pad, side); };
        // off=[[t0, t1], ...]: windows where this hand lets go (e.g. turning a page): fingers ease to a relaxed curl
        const tNow = frames.indexOf(f) / fps;
        if (o.off && o.off.some(([a, b]) => tNow >= a && tNow <= b)) { let e = o.relax ?? 20; const key = "k" + fi;
          if (prev[key] !== undefined) e = prev[key] + (e - prev[key]) * 0.2; prev[key] = e; set(e); continue; }
        const mc = fi === 1 ? (o.thumbMinCurl ?? o.minCurl ?? -10) : (o.minCurl ?? -10); let best = mc, bestD = 1e9, hit = null, pe = mc;
        for (let e = mc; e <= (o.maxCurl ?? 95); e += 5) { const d = dist(e); if (Math.abs(d) < bestD) { bestD = Math.abs(d); best = e; } if (d <= 0) { hit = [pe, e]; break; } pe = e; }
        let e = best; if (hit) { let a = hit[0], b = hit[1]; if (a === b) e = a; else { for (let j = 0; j < 14; j++) { const m = (a + b) / 2; if (dist(m) > 0) a = m; else b = m; } e = a; } }
        const key = "k" + fi; if (prev[key] !== undefined) e = prev[key] + (e - prev[key]) * 0.35; prev[key] = e; set(e);
        // thumbHover + thumbTap: the thumb rests just above the screen and taps it (THUMBTAP's bursts) after the solve
        if (fi === 1 && o.thumbTap && IKT && IKT._tt) { const t = frames.indexOf(f) / fps; let pulse = 0;
          for (const [t0, s2] of IKT._tt) { if (t0 > t) break; if (s2 !== sd) continue; const uu = t - t0; const TD = +(process.env.TAP_DUR || 0.18); if (uu < TD) pulse = Math.max(pulse, Math.sin(Math.PI * uu / TD)); }
          if (pulse > 0) names.forEach((n, j) => { f.L[n] = curlQ(n, o.thumbTap * pulse * ratio[j]).multiply(f.L[n]); }); }
        // swipe={every:[a, b], dur, amp, lift}: scrolling a feed — every a-b s the thumb slides up the screen (swinging
        // about the palm normal, in contact) and comes back lifted off the glass
        if (fi === 1 && o.swipe) { const S = o.swipe, t = frames.indexOf(f) / fps;
          if (!S._t) { let x = 977 + (sd === "R" ? 1 : 0), tt = 0.8; S._t = []; const rnd = () => (x = (x * 48271) % 2147483647) / 2147483647;
            while (tt < 600) { S._t.push(tt); tt += S.every[0] + (S.every[1] - S.every[0]) * rnd(); } }
          let ang = 0, lift = 0; for (const t0 of S._t) { const u = (t - t0) / S.dur; if (u < 0 || u > 1) continue;
            const ss = w => w * w * (3 - 2 * w);
            if (u < 0.25) { const w = u / 0.25; ang = -S.amp / 2 * ss(w); lift = Math.sin(Math.PI * w); }          // down, off the glass
            else if (u < 0.7) { const w = (u - 0.25) / 0.45; ang = -S.amp / 2 + S.amp * ss(w); }                  // slides up on it
            else { const w = (u - 0.7) / 0.3; ang = S.amp / 2 * (1 - ss(w)); lift = Math.sin(Math.PI * w) * 0.6; } } // back to rest
          const th1 = `finger1-1.${sd}`;
          if (ang || lift) { const nW = new THREE.Vector3(0, 0, 1).transformDirection(M), nL = nW.applyQuaternion(wlq(f.L, par[th1]).invert()).normalize();
            f.L[th1] = new THREE.Quaternion().setFromAxisAngle(nL, ang * D2R).multiply(f.L[th1]);
            names.forEach((n, j) => { f.L[n] = curlQ(n, (S.lift ?? 12) * lift * ratio[j]).multiply(f.L[n]); }); } }
        if (process.env.GRASP_DBG && frames.indexOf(f) % 30 === 0) (out.dbg ||= []).push([sd, frames.indexOf(f) / fps, fi, +e.toFixed(0), +(dist(e) * 1000).toFixed(1), bonePos(f.L, f.root, names[names.length - 1], true).applyMatrix4(Minv).toArray().map(v => +(v * 1000).toFixed(0)).join(",")]); } } }
  if (out.dbg) { for (const r of out.dbg) console.log("GRASP_DBG", ...r); delete out.dbg; }
  console.log("GRASP_OUT " + JSON.stringify(out)); }
// INPLACE: remove the travel (straight line from the first to the last frame) so the clip loops on the spot; the page
// moves the root along his path at the reported speed
if (process.env.INPLACE) { const n = frames.length - 1, a0 = frames[0].root, a1 = frames[n].root;
  const sp_ = Math.hypot(a1[0] - a0[0], a1[2] - a0[2]) / (n / fps);
  frames.forEach((f, i) => { f.root[0] -= (a1[0] - a0[0]) * i / n; f.root[2] -= (a1[2] - a0[2]) * i / n; });
  console.log("in place: travel speed", sp_.toFixed(3), "m/s"); }
// DUMP=bone,bone:file.json — per-frame world positions (bone heads; "name~" = tail), for props that follow the hands
if (process.env.DUMP) { const [list, file] = process.env.DUMP.split(":"), names = list.split(",");
  fs.writeFileSync(file, JSON.stringify({ fps, frames: frames.map(f => Object.fromEntries(names.map(n => [n, bonePos(f.L, f.root, n.replace("~", ""), n.endsWith("~")).toArray().map(x => +x.toFixed(4))]))) })); }
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
