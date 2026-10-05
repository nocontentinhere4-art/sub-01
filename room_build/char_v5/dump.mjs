import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, IN, OUT] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const d = await io.read(IN); const p = d.getRoot().listMeshes()[0].listPrimitives()[0];
const w = (n, a) => a && fs.writeFileSync(`${OUT}_${n}.bin`, Buffer.from(a.buffer, a.byteOffset, a.byteLength));
w("pos", p.getAttribute("POSITION").getArray()); w("uv", p.getAttribute("TEXCOORD_0").getArray()); w("idx", Uint32Array.from(p.getIndices().getArray()));
w("nrm", p.getAttribute("NORMAL").getArray());
const m = p.getMaterial(); const save = (t, n) => t && fs.writeFileSync(`${OUT}_${n}.${t.getMimeType().split("/")[1]}`, t.getImage());
save(m.getBaseColorTexture(), "base");
console.log(IN, p.getAttribute("POSITION").getCount());
