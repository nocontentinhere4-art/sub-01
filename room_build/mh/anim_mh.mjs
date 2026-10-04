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
const curlQ = (n, deg) => new THREE.Quaternion().setFromAxisAngle(fdir(n).cross(new THREE.Vector3(0, -1, 0)).normalize(), deg * D2R);
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
