// node build_chair_owner.mjs <repaired.ply> ../web/room/chair_owner.glb [textures folder]
// The office chair the owner made on Tripo (docs/design/chair-tripo/chair_owner_raw.fbx; AI-generated under Tripo's terms),
// its letter-shaped holes repaired by chair_owner_repair.py, put into the frame of the room's "chair" node (web/room.html
// CHAIR: the pivot on the floor, y up, the sitter facing -z): scaled so the seat cushion's top under him is 0.52 m (the
// model's 0.407 -> x 1.278: 1.25 m tall with the headrest), turned half round (Tripo's faces +z), its gas lift on the pivot
// and then moved 5 cm back (his reclined back and head in the seated clips clear the backrest that way), welded and
// simplified a little (meshoptimizer; the texture seams kept). Without its textures it gets a plain dark material.
import fs from "node:fs";
import { Document, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, EXTMeshoptCompression } from "@gltf-transform/extensions";
import { weld, simplify, dedup, prune, reorder, quantize } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";

export const OWNER = {scale: 0.52 / 0.407, lift: [0.0, -0.013], back: 0.05};
const [src, out, tex] = process.argv.slice(2);
await MeshoptEncoder.ready; await MeshoptSimplifier.ready;
// the repaired PLY: per corner x y z nx ny nz s t (float32), faces of three
const buf = fs.readFileSync(src), hEnd = buf.indexOf("end_header\n") + 11, head = buf.subarray(0, hEnd).toString();
const nv = +head.match(/element vertex (\d+)/)[1];
const V = new Float32Array(buf.buffer.slice(buf.byteOffset + hEnd, buf.byteOffset + hEnd + nv * 32));
const pos = new Float32Array(nv * 3), nor = new Float32Array(nv * 3), uv = new Float32Array(nv * 2), S = OWNER.scale;
for (let i = 0; i < nv; i++) {
  const x = V[8 * i], y = V[8 * i + 1], z = V[8 * i + 2];
  pos.set([-(x - OWNER.lift[0]) * S, y * S, -(z - OWNER.lift[1]) * S + OWNER.back], 3 * i);   // (half a turn about y)
  nor.set([-V[8 * i + 3], V[8 * i + 4], -V[8 * i + 5]], 3 * i);
  uv.set([V[8 * i + 6], 1 - V[8 * i + 7]], 2 * i);                                             // (FBX's v up, glTF's down)
}
const doc = new Document(), b = doc.createBuffer(), sc = doc.createScene();
const acc = (t, a) => doc.createAccessor().setType(t).setArray(a).setBuffer(b);
const mat = doc.createMaterial("chair_owner").setBaseColorFactor([0.045, 0.045, 0.05, 1]).setRoughnessFactor(0.75).setMetallicFactor(0);
if (tex && fs.existsSync(tex)) {                                  // (the textures, when they come: base colour, normal, roughness)
  const T = n => fs.existsSync(`${tex}/${n}`) ? doc.createTexture(n).setImage(fs.readFileSync(`${tex}/${n}`)).setMimeType(n.endsWith(".png") ? "image/png" : n.endsWith(".webp") ? "image/webp" : "image/jpeg") : null;
  const bc = T("base.png") || T("base.jpg") || T("base.webp"); if (bc) mat.setBaseColorTexture(bc).setBaseColorFactor([1, 1, 1, 1]);
  const nm = T("normal.png") || T("normal.jpg") || T("normal.webp"); if (nm) mat.setNormalTexture(nm);
  const mr = T("mr.png") || T("mr.jpg") || T("mr.webp"); if (mr) mat.setMetallicRoughnessTexture(mr).setRoughnessFactor(1).setMetallicFactor(1);
}
const prim = doc.createPrimitive().setAttribute("POSITION", acc("VEC3", pos)).setAttribute("NORMAL", acc("VEC3", nor)).setAttribute("TEXCOORD_0", acc("VEC2", uv)).setMaterial(mat);
const node = doc.createNode("chair_owner").setMesh(doc.createMesh("chair_owner").addPrimitive(prim));
node.setExtras({seatTop: 0.52, scale: +S.toFixed(4), back: OWNER.back, source: "Tripo (owner), repaired"}); sc.addChild(node);
await doc.transform(weld({tolerance: 1e-5}), simplify({simplifier: MeshoptSimplifier, ratio: +(process.env.RATIO || 0.55), error: 0.0006}),
  dedup(), prune(), reorder({encoder: MeshoptEncoder}), quantize());
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method: EXTMeshoptCompression.EncoderMethod.QUANTIZE});
await new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder}).write(out, doc);
const p = doc.getRoot().listMeshes()[0].listPrimitives()[0];
console.log(out, p.getIndices().getCount() / 3, "triangles,", p.getAttribute("POSITION").getCount(), "vertices,", (fs.statSync(out).size / 1024).toFixed(0), "KB");
