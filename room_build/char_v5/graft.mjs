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
const X = fs.existsSync(`${WD}/headx_pos.bin`);            // extended neck (extrude.py) replaces the GLB's geometry
const hpos = X ? rd("headx_pos.bin", Float32Array) : hp.getAttribute("POSITION").getArray();
const hnrm = X ? rd("headx_nrm.bin", Float32Array) : hp.getAttribute("NORMAL").getArray();
const huv = X ? rd("headx_uv.bin", Float32Array) : hp.getAttribute("TEXCOORD_0").getArray();
const hidx = X ? rd("headx_idx.bin", Uint32Array) : Uint32Array.from(hp.getIndices().getArray());
const acc = (a, t) => doc.createAccessor().setType(t).setArray(a.slice()).setBuffer(buf);
const np = doc.createPrimitive()
  .setAttribute("POSITION", acc(hpos, "VEC3"))
  .setAttribute("NORMAL", acc(hnrm, "VEC3"))
  .setAttribute("TEXCOORD_0", acc(huv, "VEC2"))
  .setAttribute("JOINTS_0", acc(rd("headlo_j.bin", Uint16Array), "VEC4"))
  .setAttribute("WEIGHTS_0", acc(rd("headlo_w.bin", Float32Array), "VEC4"))
  .setIndices(doc.createAccessor().setType("SCALAR").setArray(hidx).setBuffer(buf));
const hm = hp.getMaterial(), mat = doc.createMaterial("owner_head").setRoughnessFactor(0.8).setMetallicFactor(0);
const tex = (t, n) => t && doc.createTexture(n).setImage(t.getImage()).setMimeType(t.getMimeType());
mat.setBaseColorTexture(tex(hm.getBaseColorTexture(), "head_base"));
const nrmFile = `${WD}/head_normal_baked.png`;
if (hm.getNormalTexture()) mat.setNormalTexture(tex(hm.getNormalTexture(), "head_normal"));
else if (fs.existsSync(nrmFile)) mat.setNormalTexture(doc.createTexture("head_normal").setImage(fs.readFileSync(nrmFile)).setMimeType("image/png"));
mat.setDoubleSided(true); np.setMaterial(mat); mesh.addPrimitive(np);
if (fs.existsSync(`${WD}/neck2_pos.bin`) && !process.env.NONECK2) {     // the neck from the Tripo bust, its own toned texture
  const m2 = doc.createMaterial("bust_neck").setRoughnessFactor(0.8).setMetallicFactor(0).setDoubleSided(true)
    .setBaseColorTexture(doc.createTexture("neck_base").setImage(fs.readFileSync(`${WD}/neck2_base.jpeg`)).setMimeType("image/jpeg"));
  mesh.addPrimitive(doc.createPrimitive().setMaterial(m2)
    .setAttribute("POSITION", acc(rd("neck2_pos.bin", Float32Array), "VEC3")).setAttribute("NORMAL", acc(rd("neck2_nrm.bin", Float32Array), "VEC3"))
    .setAttribute("TEXCOORD_0", acc(rd("neck2_uv.bin", Float32Array), "VEC2"))
    .setAttribute("JOINTS_0", acc(rd("neck2_j.bin", Uint16Array), "VEC4")).setAttribute("WEIGHTS_0", acc(rd("neck2_w.bin", Float32Array), "VEC4"))
    .setIndices(doc.createAccessor().setType("SCALAR").setArray(rd("neck2_idx.bin", Uint32Array)).setBuffer(buf)));
}
await io.write(OUT, doc); console.log(OUT);
