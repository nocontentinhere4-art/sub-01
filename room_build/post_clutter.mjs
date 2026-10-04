// node post_clutter.mjs out/props_clutter_raw.glb ../web/room/props_clutter.glb : WebP textures (512 px: these are small
// things, a few centimetres on screen), meshopt; the props joined by material (one draw call per material: the page
// reads only "bottle" by name, which keeps its own node; each prop's triangles are in out/clutter_sweep.txt). Prints a report.
import fs from "node:fs";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRMaterialsVolume } from "@gltf-transform/extensions";
import { dedup, prune, weld, meshopt, textureCompress, join } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";
const [,, IN, OUT] = process.argv;
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({"meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder});
const doc = await io.read(IN), root = doc.getRoot();
for (const t of root.listTextures()) if (!t.getName()) t.setName((t.getURI() || "tex").replace(/\.[a-z]+$/, ""));
await doc.transform(
  dedup(), weld(),
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, slots: /normalTexture/, resize: [512, 512], quality: 90}),
  textureCompress({encoder: sharp, targetFormat: "webp", formats: /png|jpeg/, resize: [512, 512], quality: 84}),
  prune({keepLeaves: true}),
);
// the glass: a volume, so three.js refracts a little through it and tints its thick base and rim
const glassMat = root.listMaterials().find(m => m.getName() === "glass");
if (glassMat) { const ext = doc.createExtension(KHRMaterialsVolume);
  glassMat.setExtension("KHR_materials_volume", ext.createVolume().setThicknessFactor(0.004).setAttenuationColor([0.86, 0.95, 0.91]).setAttenuationDistance(0.06)); }
// quantisation folds a scale into each mesh node: so that "bottle" keeps its origin (the base centre the page sets at
// PROP.bottle's y -0.08), its mesh goes into a child node
const b = root.listNodes().find(n => n.getName() === "bottle");
if (b && b.getMesh()) { const m = b.getMesh(); b.setMesh(null); b.addChild(doc.createNode("bottle_mesh").setMesh(m)); }
// the other props are siblings at the scene's root with identity transforms (Blender applied them): join them by material
const per0 = root.listNodes().filter(n => n.getMesh()).map(n => n.getName());
await doc.transform(join({keepNamed: false}), prune({keepLeaves: false}));
console.log(`joined ${per0.length} prop nodes into`, root.listNodes().filter(n => n.getMesh()).map(n => n.getName()).join(", "));
await doc.transform(meshopt({encoder: MeshoptEncoder, level: "medium"}));
await io.write(OUT, doc);
let prims = 0, tris = 0; const per = [];
for (const n of root.listNodes()) { const m = n.getMesh(); if (!m) continue; let t = 0;
  for (const p of m.listPrimitives()) { prims++; const i = p.getIndices(); t += (i ? i.getCount() : p.getAttribute("POSITION").getCount()) / 3; }
  tris += t; per.push(`${n.getName()} ${Math.round(t)}`); }
console.log(`out ${OUT}: ${(fs.statSync(OUT).size / 1048576).toFixed(2)} MB, ${prims} primitives (draw calls), ${Math.round(tris)} triangles`);
console.log("per node:", per.join(", "));
console.log("textures:", root.listTextures().map(t => `${t.getName()} ${t.getSize()} ${t.getImage().byteLength >> 10}K`).join(", "));
