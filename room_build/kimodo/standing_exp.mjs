// node standing_exp.mjs <glb> <out.json> : as kimodo_g12/exp.mjs (nodes with parent and rest TRS, the skin's joints and
// inverse bind matrices, every animation's keyframes), but with EVERY mesh bound to that skin (char_mixamo.glb carries
// its slides as a second skinned mesh: the soles are the slides' undersides, so the floor fit must see them)
import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS} from '@gltf-transform/extensions';
import {MeshoptDecoder} from 'meshoptimizer'; import fs from 'fs';
await MeshoptDecoder.ready;
const d = await new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder}).read(process.argv[2]);
const r = d.getRoot(), nodes = r.listNodes(), ix = new Map(nodes.map((n, i) => [n, i]));
const parent = nodes.map(() => -1); nodes.forEach((n, i) => n.listChildren().forEach(c => parent[ix.get(c)] = i));
const out = {nodes: nodes.map((n, i) => ({name: n.getName(), parent: parent[i], t: n.getTranslation(), r: n.getRotation(), s: n.getScale()})), anims: []};
const sk = r.listSkins()[0];
if (sk) {
  out.skin = {joints: sk.listJoints().map(j => ix.get(j)), ibm: Array.from(sk.getInverseBindMatrices().getArray())};
  out.mesh = [];
  for (const mn of nodes.filter(n => n.getMesh() && n.getSkin() === sk))
    for (const p of mn.getMesh().listPrimitives()) {
      const P = p.getAttribute('POSITION');
      out.mesh.push({node: mn.getName(), pos: Array.from(P.getArray()), j: Array.from(p.getAttribute('JOINTS_0').getArray()),
        w: Array.from(p.getAttribute('WEIGHTS_0').getArray()), norm: P.getNormalized ? P.getNormalized() : false});
    }
}
for (const a of r.listAnimations()) out.anims.push({name: a.getName(), ch: a.listChannels().map(c => ({node: ix.get(c.getTargetNode()), path: c.getTargetPath(),
  interp: c.getSampler().getInterpolation(), t: Array.from(c.getSampler().getInput().getArray()), v: Array.from(c.getSampler().getOutput().getArray())}))});
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.log(process.argv[2].split('/').pop(), nodes.length, 'nodes', sk ? sk.listJoints().length + ' joints' : '', out.mesh ? out.mesh.map(m => m.node + ':' + m.pos.length / 3).join(' + ') + ' verts' : '', out.anims.map(a => a.name).join(','));
