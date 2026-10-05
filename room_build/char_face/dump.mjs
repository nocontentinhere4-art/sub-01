// node dump.mjs <glb> <outdir> : raw arrays of the first primitive + its textures, for the Python bake
import {NodeIO} from '@gltf-transform/core';
import fs from 'fs';
const [glb, out] = process.argv.slice(2); fs.mkdirSync(out, {recursive: true});
const d = await new NodeIO().read(glb);
const p = d.getRoot().listMeshes()[0].listPrimitives()[0];
for (const [k, n] of [['POSITION','pos'],['NORMAL','nrm'],['TEXCOORD_0','uv']]) fs.writeFileSync(`${out}/${n}.f32`, Buffer.from(p.getAttribute(k).getArray().buffer));
fs.writeFileSync(`${out}/idx.u32`, Buffer.from(new Uint32Array(p.getIndices().getArray()).buffer));
const m = p.getMaterial();
for (const [n, t] of [['base', m.getBaseColorTexture()], ['normal', m.getNormalTexture()], ['orm', m.getMetallicRoughnessTexture()]])
  fs.writeFileSync(`${out}/${n}.${t.getMimeType().split('/')[1]}`, Buffer.from(t.getImage()));
console.log(JSON.stringify({rough: m.getRoughnessFactor(), metal: m.getMetallicFactor(), base: m.getBaseColorFactor()}));
