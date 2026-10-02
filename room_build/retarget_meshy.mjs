// retarget_meshy.mjs <old rig glb> <new rig glb> <clip glb (or the old rig itself)> <out glb> [embed]
// world-space rest-relative retarget: each bone keeps the clip's world rotation change from the old rest pose,
// applied on the new rest pose; Hips translation scaled by the hip-height ratio. No scale tracks.
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer';
import * as THREE from 'three';
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder});
const [oldRig, newRig, clipF, out, embed] = process.argv.slice(2);
const O = await io.read(oldRig), N = await io.read(newRig), C = await io.read(clipF);
const rest = doc => { const m = new Map(); for (const n of doc.getRoot().listNodes()) m.set(n.getName(), n); return m; };
const ro = rest(O), rn = rest(N);
const parentName = (doc, name) => { for (const n of doc.getRoot().listNodes()) if (n.listChildren().some(c => c.getName() === name)) return n.getName(); return null; };
const BONES = [...ro.keys()].filter(n => rn.has(n) && n !== 'Armature' && !ro.get(n).getMesh());
// world rest rotation (rotation only), walking parents up
const worldRest = (m, doc, name) => { let q = new THREE.Quaternion(); let n = name;
  const chain = []; while (n) { chain.unshift(n); n = parentName(doc, n); }
  for (const c of chain) q.multiply(new THREE.Quaternion(...m.get(c).getRotation())); return q; };
const WO = {}, WN = {}, PO = {}, PN = {};
for (const b of BONES) { WO[b] = worldRest(ro, O, b); WN[b] = worldRest(rn, N, b); PO[b] = parentName(O, b); PN[b] = parentName(N, b); }
const order = [...BONES].sort((a, b) => { const d = x => { let k = 0, n = x; while ((n = parentName(N, n))) k++; return k; }; return d(a) - d(b); });
const parentWorldRestN = b => PN[b] ? (WN[PN[b]] || worldRest(rn, N, PN[b])) : new THREE.Quaternion();
const parentWorldRestO = b => PO[b] ? (WO[PO[b]] || worldRest(ro, O, PO[b])) : new THREE.Quaternion();
const hipRatio = rn.get('Hips').getTranslation()[1] / ro.get('Hips').getTranslation()[1];
const cache = new Map();
const floats = acc => { if (!cache.has(acc)) { const n = acc.getCount(), k = acc.getElementSize(), f = new Float32Array(n * k), e = [];
  for (let i = 0; i < n; i++) { acc.getElement(i, e); for (let j = 0; j < k; j++) f[i * k + j] = e[j]; } cache.set(acc, f); } return cache.get(acc); };
const src = C.getRoot().listAnimations()[0];
const tracks = {}; let times = null;
for (const ch of src.listChannels()) { const n = ch.getTargetNode().getName(), p = ch.getTargetPath();
  tracks[n + '.' + p] = ch.getSampler(); const t = floats(ch.getSampler().getInput()); if (!times || t.length > times.length) times = t; }
const sample = (s, t, size) => { const ti = floats(s.getInput()), v = floats(s.getOutput());
  let i = 0; while (i < ti.length - 1 && ti[i + 1] <= t) i++; const j = Math.min(i + 1, ti.length - 1);
  const f = j === i ? 0 : (t - ti[i]) / (ti[j] - ti[i]);
  if (size === 4) { const a = new THREE.Quaternion().fromArray(v, i * 4), b = new THREE.Quaternion().fromArray(v, j * 4); return a.slerp(b, f); }
  return new THREE.Vector3().fromArray(v, i * 3).lerp(new THREE.Vector3().fromArray(v, j * 3), f); };
const outQ = {}, outHip = [];
for (const b of order) outQ[b] = new Float32Array(times.length * 4);
for (let k = 0; k < times.length; k++) { const t = times[k], AO = {}, AN = {};
  const oldWorld = b => { if (AO[b]) return AO[b]; const s = tracks[b + '.rotation'];
    const local = s ? sample(s, t, 4) : new THREE.Quaternion(...ro.get(b).getRotation());
    const p = PO[b] && BONES.includes(PO[b]) ? oldWorld(PO[b]) : parentWorldRestO(b); return (AO[b] = p.clone().multiply(local)); };
  for (const b of order) {
    const A = oldWorld(b).clone().multiply(WO[b].clone().invert()).multiply(WN[b]);   // same world delta, new rest
    AN[b] = A; const p = PN[b] && BONES.includes(PN[b]) ? AN[PN[b]] : parentWorldRestN(b);
    p.clone().invert().multiply(A).toArray(outQ[b], k * 4); }
  const hs = tracks['Hips.translation']; if (hs) { const v = sample(hs, t, 3), r0 = new THREE.Vector3(...ro.get('Hips').getTranslation()), r1 = new THREE.Vector3(...rn.get('Hips').getTranslation());
    // hips offset from rest, in the armature's frame; old and new armature share orientation and scale here
    outHip.push(...v.sub(r0).multiplyScalar(hipRatio).add(r1).toArray()); } }
// write into the target doc: either the new rig (embed) or a copy of the clip file with retargeted channels
const D = embed ? N : C, byName = rest(D), buf = D.getRoot().listBuffers()[0];
const name = src.getName();
if (embed) for (const a of D.getRoot().listAnimations()) a.dispose(); else for (const a of D.getRoot().listAnimations()) a.dispose();
const A = D.createAnimation(name), tin = D.createAccessor().setArray(new Float32Array(times)).setType('SCALAR').setBuffer(buf);
const add = (node, path, arr, type) => { const s = D.createAnimationSampler().setInput(tin).setInterpolation('LINEAR')
  .setOutput(D.createAccessor().setArray(arr).setType(type).setBuffer(buf)); A.addSampler(s).addChannel(D.createAnimationChannel().setTargetNode(node).setTargetPath(path).setSampler(s)); };
for (const b of order) if (byName.get(b) && tracks[b + '.rotation']) add(byName.get(b), 'rotation', outQ[b], 'VEC4');   // only the source's own bones (partial clips stay partial)
if (outHip.length) add(byName.get('Hips'), 'translation', new Float32Array(outHip), 'VEC3');
await D.transform(prune({keepLeaves: true})); await io.write(out, D);
console.log(out.split('/').pop(), name, 'frames', times.length, 'bones', order.length, 'hipRatio', hipRatio.toFixed(3));
