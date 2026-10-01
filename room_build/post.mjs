// node post.mjs in.glb ao.png out.glb : AO lightmap as occlusion (texCoord 1), WebP textures, meshopt; prints a report
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, prune, flatten, join, weld, meshopt, textureCompress, resample } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";
const [,, IN, AO, OUT] = process.argv;
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const doc = await io.read(IN);
const root = doc.getRoot();

// --- the baked AO goes on every material of the static room mesh, read through the second UV set
const staticMesh = root.listNodes().find(n => n.getName() === "room_static").getMesh();
staticMesh.setName("room_static");
// marker nodes (SURF_*) are empty: flatten/prune would drop them, so keep their world transforms and re-add them at the end
const markers = root.listNodes().filter(n => n.getName().startsWith("SURF_")).map(n => ({name: n.getName(), m: n.getWorldMatrix(), extras: n.getExtras()}));
if (AO && fs.existsSync(AO)) {
  const {width: W} = await sharp(AO).metadata(), c = Math.ceil(W * 0.014);   // the tiny parts read a white corner
  const flat = await sharp(AO).composite([{input: {create: {width: c, height: c, channels: 3, background: "#ffffff"}}, left: W - c, top: 0}]).png().toBuffer();
  const png = await sharp(flat).greyscale().blur(0.9).toColourspace("b-w").png().toBuffer();
  const tex = doc.createTexture("room_ao").setImage(png).setMimeType("image/png").setURI("room_ao.png");
  for (const p of staticMesh.listPrimitives()) {
    const m = p.getMaterial(); if (!m) continue;
    m.setOcclusionTexture(tex); m.getOcclusionTextureInfo().setTexCoord(1); m.setOcclusionStrength(1.0);
  }
}
// the clocks' glass uses transmission, which costs three.js a whole extra render pass: plain alpha-blended glass instead
for (const m of root.listMaterials()) {
  const t = m.getExtension("KHR_materials_transmission");
  if (t) { m.setExtension("KHR_materials_transmission", null); t.dispose();
    const c = m.getBaseColorFactor(); m.setBaseColorFactor([c[0], c[1], c[2], 0.12]).setAlphaMode("BLEND").setRoughnessFactor(0.05).setMetallicFactor(0); }
}
for (const e of root.listExtensionsUsed()) if (e.extensionName === "KHR_materials_transmission") e.dispose();
// name textures after their first material slot, so that the resize rules below can target them
for (const t of root.listTextures()) if (!t.getName()) t.setName((t.getURI() || "tex").replace(/\.[a-z]+$/, ""));
const isProp = t => /desk_lamp|potted|wall_clock|alarm|cardboard|notepad/i.test(t.getName() + t.getURI());
console.log("textures:", root.listTextures().map(t => `${t.getName()} ${t.getImage().byteLength >> 10}K`).join(", "));

await doc.transform(
  dedup(), flatten(), join({keepNamed: false}), weld(), resample(),
  // big room surfaces keep detail, props and fabrics are small on screen
  // normal maps keep more quality (their relief is subtle); each texture is encoded once (later passes skip WebP)
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, slots: /normalTexture/, resize: [1024, 1024], quality: 92}),
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, pattern: /floor_diff/, resize: [2048, 2048], quality: 84}),
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, pattern: /room_ao/, quality: 88}),
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, resize: [1024, 1024], quality: 84}),
  prune({keepLeaves: true, keepAttributes: false}),
  meshopt({encoder: MeshoptEncoder, level: "medium"}),
);
// props: shrink their textures further
for (const t of root.listTextures()) {
  if (isProp(t)) {
    const im = await sharp(t.getImage()).resize(512, 512, {fit: "inside"}).webp({quality: 80}).toBuffer();
    t.setImage(im).setMimeType("image/webp");
  }
}
const scene = root.listScenes()[0];
for (const k of markers) { const n = doc.createNode(k.name).setMatrix(k.m).setExtras(k.extras); scene.addChild(n); }
await io.write(OUT, doc);
const sz = fs.statSync(OUT).size;
let prims = 0, tris = 0;
for (const n of root.listNodes()) { const m = n.getMesh(); if (!m) continue; for (const p of m.listPrimitives()) { prims++; const i = p.getIndices(); tris += (i ? i.getCount() : p.getAttribute("POSITION").getCount()) / 3; } }
console.log(`out ${OUT}: ${(sz / 1048576).toFixed(2)} MB, ${prims} primitives (draw calls), ${Math.round(tris)} triangles`);
console.log("textures:", root.listTextures().map(t => `${t.getName()} ${t.getImage().byteLength >> 10}K`).join(", "));
console.log("nodes:", root.listNodes().filter(n => !n.getMesh()).map(n => n.getName()).join(", "));
