import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, IN, OUT] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const d = await io.read(IN); const r=d.getRoot(); const sk=r.listSkins()[0]; const J=sk.listJoints();
const p = r.listMeshes()[0].listPrimitives()[0];   // body
const w = (n, a) => fs.writeFileSync(`${OUT}_${n}.bin`, Buffer.from(a.buffer, a.byteOffset, a.byteLength));
w("pos", p.getAttribute("POSITION").getArray()); w("idx", Uint32Array.from(p.getIndices().getArray()));
w("j", Uint16Array.from(p.getAttribute("JOINTS_0").getArray())); w("w", Float32Array.from(p.getAttribute("WEIGHTS_0").getArray()));
fs.writeFileSync(`${OUT}_skin.json`, JSON.stringify({joints:J.map(j=>j.getName()), ibm:Array.from(sk.getInverseBindMatrices().getArray()),
  world:J.map(j=>j.getWorldMatrix()), prims:r.listMeshes()[0].listPrimitives().length}));
console.log(J.length, p.getAttribute("POSITION").getCount());
