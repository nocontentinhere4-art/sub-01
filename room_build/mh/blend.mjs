// node blend.mjs A.glb B.glb out.glb [blend_s] — one continuous clip: A (moved and turned so its walk ends where and
// how B's walk begins), then B, with a cross-fade (slerp per bone, lerp of the root) at the best-matching gait frames
import { NodeIO } from "@gltf-transform/core";
import * as THREE from "three";
const [,, FA, FB, OUT, BL] = process.argv, blend = +(BL || 0.5);
const io = new NodeIO();
const read = async f => { const d = await io.read(f), an = d.getRoot().listAnimations()[0], tr = {};
  for (const c of an.listChannels()) { const s = c.getSampler(); tr[c.getTargetNode().getName() + "|" + c.getTargetPath()] = { t: s.getInput().getArray(), v: s.getOutput().getArray() }; }
  return { d, tr, n: Object.values(tr)[0].t.length, fps: 1 / (Object.values(tr)[0].t[1]) }; };
const A = await read(FA), B = await read(FB), fps = A.fps;
const rq = (C, n, i) => { const v = C.tr[n + "|rotation"].v; return new THREE.Quaternion(v[i * 4], v[i * 4 + 1], v[i * 4 + 2], v[i * 4 + 3]); };
const rp = (C, i) => { const v = C.tr["root|translation"].v; return new THREE.Vector3(v[i * 3], v[i * 3 + 1], v[i * 3 + 2]); };
const bones = Object.keys(A.tr).filter(k => k.endsWith("|rotation")).map(k => k.split("|")[0]);
const cmp = ["upperleg01.L", "upperleg01.R", "lowerleg01.L", "lowerleg01.R", "foot.L", "foot.R", "upperarm01.L", "upperarm01.R"];
const dirAt = (C, i) => rp(C, Math.min(C.n - 1, i + 6)).sub(rp(C, Math.max(0, i - 6))).setY(0).normalize();
// search: A in its last 1.5 s, B in its first 0.8 s
let best = null;
for (let ia = A.n - Math.round(1.5 * fps); ia < A.n - 1; ia++) for (let ib = 0; ib < Math.round(0.8 * fps); ib++) {
  let c = 0; for (const b of cmp) c += rq(A, b, ia).angleTo(rq(B, b, ib)); if (!best || c < best.c) best = { c, ia, ib }; }
const { ia, ib } = best, dA = dirAt(A, ia), dB = dirAt(B, ib);
const yaw = Math.atan2(dB.x, dB.z) - Math.atan2(dA.x, dA.z), Q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
const pA = rp(A, ia).applyQuaternion(Q), off = rp(B, ib).sub(pA); off.y = 0;
const nb = Math.round(blend * fps), out = [];          // frames: A[0..ia), cross-fade A[ia..ia+nb) with B[ib..ib+nb), then B
const frameA = i => ({ root: rp(A, i).applyQuaternion(Q).add(off), rot: Object.fromEntries(bones.map(b => [b, b === "root" ? Q.clone().multiply(rq(A, b, i)) : rq(A, b, i)])) });
const frameB = i => ({ root: rp(B, i), rot: Object.fromEntries(bones.map(b => [b, rq(B, b, i)])) });
for (let i = 0; i < ia; i++) out.push(frameA(i));
for (let k = 0; k < nb; k++) { const a = frameA(Math.min(A.n - 1, ia + k)), b = frameB(ib + k), w = 0.5 - 0.5 * Math.cos(Math.PI * (k + 1) / (nb + 1));
  out.push({ root: a.root.clone().lerp(b.root, w), rot: Object.fromEntries(bones.map(n => [n, a.rot[n].clone().slerp(b.rot[n], w)])) }); }
for (let i = ib + nb; i < B.n; i++) out.push(frameB(i));
// write into B's document
const doc = B.d, an = doc.getRoot().listAnimations()[0], tin = new Float32Array(out.map((_, i) => i / fps));
for (const c of an.listChannels()) { const s = c.getSampler(), n = c.getTargetNode().getName(), p = c.getTargetPath();
  s.getInput().setArray(tin);
  if (p === "rotation") { const a = new Float32Array(out.length * 4); let prev = null;
    out.forEach((f, i) => { const q = f.rot[n]; if (prev && q.dot(prev) < 0) q.set(-q.x, -q.y, -q.z, -q.w); q.toArray(a, i * 4); prev = q; }); s.getOutput().setArray(a); }
  else if (p === "translation" && n === "root") { const a = new Float32Array(out.length * 3); out.forEach((f, i) => f.root.toArray(a, i * 3)); s.getOutput().setArray(a); } }
// tie all channels to one input accessor
await io.write(OUT, doc);
console.log(JSON.stringify({ ia, ib, tA: (ia / fps).toFixed(2), tB: (ib / fps).toFixed(2), cost: best.c.toFixed(2), yaw: yaw.toFixed(3), off: off.toArray().map(x => +x.toFixed(3)), frames: out.length, cutAt_s: (ia / fps).toFixed(2), Bstart_s: ((ia + nb - ib - nb) / fps).toFixed(2) }));
