// node splitslides.mjs in.glb workdir out.glb [noslides] : move the slide triangles (slide_tris.bin) of the body into
// their own skinned mesh "slides" (compact vertex set, same skin, same material); the body keeps the rest plus the
// foot closure triangles (footfill_*.bin, appended vertices with their own skin weights).
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, IN, WD, OUT, NOSL] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(IN); const root = doc.getRoot(); const buf = root.listBuffers()[0];
const rd = (f, T) => { const b = fs.readFileSync(`${WD}/${f}`); return new T(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
const bodyNode = root.listNodes().find(n => n.getMesh() && n.getMesh().listPrimitives().length > 1) || root.listNodes().find(n => n.getMesh());
const body = bodyNode.getMesh().listPrimitives()[0];
const idx = body.getIndices().getArray(); const sl = rd("slide_tris.bin", Uint32Array);
const isSl = new Uint8Array(idx.length / 3); for (const t of sl) isSl[t] = 1;
const keep = [], slv = [];
for (let t = 0; t < idx.length / 3; t++) (isSl[t] ? slv : keep).push(idx[3*t], idx[3*t+1], idx[3*t+2]);
const A = n => body.getAttribute(n), sem = ["POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"];
// foot closure: extra vertices appended to the body's attributes
let nb = A("POSITION").getCount();
if (fs.existsSync(`${WD}/footfill_pos.bin`)) {
  const add = {POSITION: rd("footfill_pos.bin", Float32Array), NORMAL: rd("footfill_nrm.bin", Float32Array), TEXCOORD_0: rd("footfill_uv.bin", Float32Array),
               JOINTS_0: rd("footfill_j.bin", Uint16Array), WEIGHTS_0: rd("footfill_w.bin", Float32Array)};
  for (const s of sem) { const a = A(s), old = a.getArray(), C = old.constructor, n = new C(old.length + add[s].length); n.set(old); n.set(C.from(add[s]), old.length);
    body.setAttribute(s, doc.createAccessor().setType(a.getType()).setArray(n).setBuffer(buf).setNormalized(a.getNormalized())); }
  for (const v of rd("footfill_idx.bin", Uint32Array)) keep.push(v + nb);
}
body.setIndices(doc.createAccessor().setType("SCALAR").setArray(new Uint32Array(keep)).setBuffer(buf));
if (!NOSL) {
  const uniq = [...new Set(slv)]; const remap = new Map(uniq.map((v, i) => [v, i]));
  const sp = doc.createPrimitive().setMaterial(body.getMaterial());
  for (const s of sem) { const a = A(s), old = a.getArray(), k = a.getElementSize(), C = old.constructor, n = new C(uniq.length * k);
    uniq.forEach((v, i) => { for (let j = 0; j < k; j++) n[i*k+j] = old[v*k+j]; });
    sp.setAttribute(s, doc.createAccessor().setType(a.getType()).setArray(n).setBuffer(buf).setNormalized(a.getNormalized())); }
  sp.setIndices(doc.createAccessor().setType("SCALAR").setArray(new Uint32Array(slv.map(v => remap.get(v)))).setBuffer(buf));
  const mesh = doc.createMesh("slides").addPrimitive(sp);
  const node = doc.createNode("slides").setMesh(mesh).setSkin(bodyNode.getSkin());
  const par = root.listNodes().find(n => n.listChildren().includes(bodyNode));
  if (par) par.addChild(node); else root.listScenes()[0].addChild(node);
  console.log("slides verts", uniq.length, "tris", slv.length / 3);
}
await io.write(OUT, doc); console.log(OUT, "body tris", keep.length / 3);
