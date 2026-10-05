// node graft.mjs body.glb head.glb workdir out.glb : body indices <- workdir/body_keep_idx.bin; head skin <- workdir/headlo_j.bin, headlo_w.bin
import { NodeIO } from "@gltf-transform/core"; import { ALL_EXTENSIONS } from "@gltf-transform/extensions"; import fs from "fs";
const [,, BODY, HEAD, WD, OUT] = process.argv; const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(BODY), hd = await io.read(HEAD);
const root = doc.getRoot(), buf = root.listBuffers()[0], mesh = root.listMeshes()[0], bp = mesh.listPrimitives()[0];
const rd = (f, T) => { const b = fs.readFileSync(`${WD}/${f}`); return new T(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
bp.setIndices(doc.createAccessor().setType("SCALAR").setArray(rd("body_keep_idx.bin", Uint32Array)).setBuffer(buf));
const nb = `${WD}/body_base_neck.jpeg`;
if (fs.existsSync(nb)) bp.getMaterial().getBaseColorTexture().setImage(fs.readFileSync(nb)).setMimeType("image/jpeg");
const hp = hd.getRoot().listMeshes()[0].listPrimitives()[0];
const acc = (a, t) => doc.createAccessor().setType(t).setArray(a.slice()).setBuffer(buf);
const np = doc.createPrimitive()
  .setAttribute("POSITION", acc(hp.getAttribute("POSITION").getArray(), "VEC3"))
  .setAttribute("NORMAL", acc(hp.getAttribute("NORMAL").getArray(), "VEC3"))
  .setAttribute("TEXCOORD_0", acc(hp.getAttribute("TEXCOORD_0").getArray(), "VEC2"))
  .setAttribute("JOINTS_0", acc(rd("headlo_j.bin", Uint16Array), "VEC4"))
  .setAttribute("WEIGHTS_0", acc(rd("headlo_w.bin", Float32Array), "VEC4"))
  .setIndices(doc.createAccessor().setType("SCALAR").setArray(Uint32Array.from(hp.getIndices().getArray())).setBuffer(buf));
const hm = hp.getMaterial(), mat = doc.createMaterial("owner_head").setRoughnessFactor(0.8).setMetallicFactor(0);
const tex = (t, n) => t && doc.createTexture(n).setImage(t.getImage()).setMimeType(t.getMimeType());
mat.setBaseColorTexture(tex(hm.getBaseColorTexture(), "head_base"));
const nrmFile = `${WD}/head_normal_baked.png`;
if (hm.getNormalTexture()) mat.setNormalTexture(tex(hm.getNormalTexture(), "head_normal"));
else if (fs.existsSync(nrmFile)) mat.setNormalTexture(doc.createTexture("head_normal").setImage(fs.readFileSync(nrmFile)).setMimeType("image/png"));
np.setMaterial(mat); mesh.addPrimitive(np);
await io.write(OUT, doc); console.log(OUT);
