// node breathclip.mjs <v5.glb> <curve.json> <out.glb>: the breath as a small v5 clip (rest pose + breath deltas, for
// AnimationUtils.makeClipAdditive with frame 0 = rest): chest extension (Spine01 + Spine02) sized so the sternum rises
// ~4 mm at the subject's median breath (De Groote et al. 1997: 3-5 mm cranial/ventral at the sternum, seated), the neck
// and head counter-turned so the head stays where it was, the clavicles lifting ~1 deg (shoulders up a few mm)
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer"; import { prune } from "@gltf-transform/functions"; import * as THREE from "three";
const [,, CHAR, CURVE, OUT] = process.argv; await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder});
const doc = await io.read(CHAR), root = doc.getRoot(), C = JSON.parse(fs.readFileSync(CURVE));
const par = new Map(); for (const n of root.listNodes()) for (const c of n.listChildren()) par.set(c, n);
const B = nm => root.listNodes().find(n => n.getName() === nm);
const W = new Map(); const rw = n => { if (W.has(n)) return W.get(n); const q = new THREE.Quaternion(...n.getRotation()), p = par.get(n); const w = p ? rw(p).clone().multiply(q) : q; W.set(n, w); return w; };
const D = Math.PI / 180, E = JSON.parse(process.env.BREATH || "{}"), A = {Spine01: (E.s1 ?? 0.2) * D, Spine02: (E.s2 ?? 0.45) * D, NeckTwist01: (E.n ?? -0.45) * D, Head: (E.h ?? -0.2) * D}, CLAV = (E.c ?? 3.4) * D;
const Z = new THREE.Vector3(0, 0, 1), X = new THREE.Vector3(1, 0, 0);
const chainOrder = ["Spine01", "Spine02", "NeckTwist01", "Head"];
const T = C.frames, tracks = {}; for (const nm of [...chainOrder, "L_Clavicle", "R_Clavicle"]) tracks[nm] = new Float32Array(T * 4);
for (let f = 0; f < T; f++) { const v = C.value[f]; let acc = 0; const Wn = {};
  for (const nm of chainOrder) { acc += A[nm] * v; Wn[nm] = new THREE.Quaternion().setFromAxisAngle(Z, acc).multiply(rw(B(nm))); }   // + about Z: the top back (extension)
  for (const [nm, s] of [["L_Clavicle", 1], ["R_Clavicle", -1]]) { const n = B(nm), pw = Wn[par.get(n).getName()] || rw(par.get(n));
    const restRel = rw(par.get(n)).clone().invert().multiply(rw(n));                     // its rest local
    Wn[nm] = new THREE.Quaternion().setFromAxisAngle(X, s * CLAV * v).multiply(pw.clone().multiply(restRel)); }
  for (const nm of Object.keys(tracks)) { const n = B(nm), p = par.get(n), pw = Wn[p.getName()] || rw(p); pw.clone().invert().multiply(Wn[nm]).normalize().toArray(tracks[nm], f * 4); } }
for (const a of root.listAnimations()) a.dispose();
for (const n of root.listNodes()) if (n.getMesh()) { n.setMesh(null); n.setSkin(null); }
for (const m of root.listMeshes()) m.dispose(); for (const s of root.listSkins()) s.dispose(); for (const m of root.listMaterials()) m.dispose(); for (const t of root.listTextures()) t.dispose();
for (const e of root.listExtensionsUsed()) e.dispose();
const buf = root.listBuffers()[0], an = doc.createAnimation("breath"), tin = doc.createAccessor().setArray(new Float32Array(Array.from({length: T}, (_, i) => i / C.fps))).setType("SCALAR").setBuffer(buf);
for (const [nm, arr] of Object.entries(tracks)) { const s = doc.createAnimationSampler().setInput(tin).setInterpolation("LINEAR").setOutput(doc.createAccessor().setArray(arr).setType("VEC4").setBuffer(buf)); an.addSampler(s).addChannel(doc.createAnimationChannel().setTargetNode(B(nm)).setTargetPath("rotation").setSampler(s)); }
await doc.transform(prune({keepLeaves: true})); await io.write(OUT, doc);
// sternum check: a point 0.15 m in front of Spine02 at the deepest breath
const vmax = Math.max(...C.value); console.log(JSON.stringify({frames: T, seconds: C.seconds, maxValue: vmax, chestExtension_deg: +((A.Spine01 + A.Spine02) / D).toFixed(2), clavicle_deg: +(CLAV / D).toFixed(2)}));
