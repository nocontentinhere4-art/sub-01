// node bed_exp.mjs <character.glb> <out.json> [--skip name,name] : the character for the bed fit (kimodo_g12/bed_clip.py,
// bed_turn.py) in exp.mjs's json shape, but with EVERY skinned part (v5 since b2593d7 is the body plus "socks",
// "hood_lining", "hood_patches" and "slides": exp.mjs takes only the first, so his feet were missing), each part's joints
// on one list (a part's own slots). --skip leaves parts out (default: slides - in bed they are parked by it, not on him).
import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {MeshoptDecoder} from 'meshoptimizer'; import fs from 'fs';
await MeshoptDecoder.ready;
const args = process.argv.slice(2), SKIP = new Set((args.includes('--skip') ? args[args.indexOf('--skip') + 1] : 'slides').split(',').filter(Boolean));
const d = await new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder}).read(args[0]);
const r = d.getRoot(), nodes = r.listNodes(), ix = new Map(nodes.map((n, i) => [n, i]));
const parent = nodes.map(() => -1); nodes.forEach((n, i) => n.listChildren().forEach(c => parent[ix.get(c)] = i));
const out = {nodes: nodes.map((n, i) => ({name: n.getName(), parent: parent[i], t: n.getTranslation(), r: n.getRotation(), s: n.getScale()})), anims: [], parts: []};
const J = [], ibm = []; out.mesh = [];
for (const n of nodes) { const sk = n.getSkin(), m = n.getMesh(); if (!sk || !m || SKIP.has(n.getName())) continue;
  // (each part its own joint slots: gltfpack folds a part's dequantization into its own inverse bind matrices)
  const js = sk.listJoints(), IB = sk.getInverseBindMatrices().getArray(), local = js.map((j, k) => {
    J.push(ix.get(j)); ibm.push(...IB.slice(16 * k, 16 * k + 16)); return J.length - 1; });
  for (const p of m.listPrimitives()) { const P = p.getAttribute('POSITION'), JA = Array.from(p.getAttribute('JOINTS_0').getArray());
    out.mesh.push({part: n.getName(), mat: p.getMaterial() ? p.getMaterial().getName() : '', pos: Array.from(P.getArray()), j: JA.map(k => local[k]), w: Array.from(p.getAttribute('WEIGHTS_0').getArray()), norm: P.getNormalized ? P.getNormalized() : false}); }
  out.parts.push(n.getName()); }
out.skin = {joints: J, ibm};
fs.writeFileSync(args[1], JSON.stringify(out));
console.log(args[0].split('/').pop(), 'parts', out.parts.join(', '), J.length, 'joints', out.mesh.map(m => m.pos.length / 3).join('+'), 'verts');
