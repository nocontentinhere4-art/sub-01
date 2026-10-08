// node room_tris.mjs <room_clean.glb> <out.bin> <out.json> : every mesh's triangles in world space (float32 x 9 per
// triangle, dequantized), and per node its name and triangle range, for the room-side bed tests in Python
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { MeshoptDecoder } from "meshoptimizer";
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.decoder": MeshoptDecoder});
const doc = await io.read(process.argv[2]);
const out = [], meta = []; let n = 0; const v = [0, 0, 0];
for (const node of doc.getRoot().listNodes()) {
  const mesh = node.getMesh(); if (!mesh) continue; const W = node.getWorldMatrix(); const t0 = n;
  for (const p of mesh.listPrimitives()) {
    const a = p.getAttribute("POSITION"), idx = p.getIndices(); if (!a) continue;
    const P = []; for (let i = 0; i < a.getCount(); i++) { a.getElement(i, v);
      P.push([W[0]*v[0]+W[4]*v[1]+W[8]*v[2]+W[12], W[1]*v[0]+W[5]*v[1]+W[9]*v[2]+W[13], W[2]*v[0]+W[6]*v[1]+W[10]*v[2]+W[14]]); }
    const I = idx ? idx.getArray() : Array.from({length: a.getCount()}, (_, i) => i);
    for (let k = 0; k + 2 < I.length; k += 3) { for (const j of [I[k], I[k+1], I[k+2]]) out.push(...P[j]); n++; }
  }
  meta.push({name: node.getName(), t0, t1: n});
}
fs.writeFileSync(process.argv[3], Buffer.from(new Float32Array(out).buffer)); fs.writeFileSync(process.argv[4], JSON.stringify(meta));
console.log(n, "triangles", meta.length, "meshes");
